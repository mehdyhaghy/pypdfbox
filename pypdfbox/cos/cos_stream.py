from __future__ import annotations

import io
import logging
from collections.abc import Iterable, Sequence
from typing import Any, BinaryIO

from pypdfbox.io import ScratchFile, ScratchFileBuffer

from .cos_array import COSArray
from .cos_base import COSBase
from .cos_dictionary import COSDictionary
from .cos_integer import COSInteger
from .cos_name import COSName
from .i_cos_visitor import ICOSVisitor

_LOG = logging.getLogger(__name__)

_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_LENGTH: COSName = COSName.LENGTH  # type: ignore[attr-defined]
_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")
_DP = COSName.get_pdf_name("DP")
_FILTER_NAME_ALIASES: dict[str, str] = {
    "AHx": "ASCIIHexDecode",
    "A85": "ASCII85Decode",
    "LZW": "LZWDecode",
    "Fl": "FlateDecode",
    "RL": "RunLengthDecode",
    "CCF": "CCITTFaxDecode",
    "DCT": "DCTDecode",
    "JPX": "JPXDecode",
}


class _CommittingOutputStream(io.BytesIO):
    """``BytesIO`` subclass whose ``close()`` commits the buffered bytes
    back into the owning ``COSStream``. Mirrors the inner anonymous
    ``FilterOutputStream`` upstream returns from
    ``createRawOutputStream``: on ``close()`` it syncs ``/Length`` and
    clears the owner's writing flag (parity for ``isWriting``)."""

    def __init__(self, owner: COSStream) -> None:
        super().__init__()
        self._owner = owner
        self._committed = False

    def close(self) -> None:
        if not self._committed:
            self._committed = True
            self._owner._set_raw_data_internal(self.getvalue())
            self._owner._is_writing = False
            self._owner._sync_length_entry()
        super().close()


class _EncodingOutputStream(io.BytesIO):
    """``BytesIO`` subclass whose ``close()`` runs the buffered raw bytes
    through a filter chain (in reverse: rightmost filter first, as
    decoders are applied left-to-right) and commits the encoded result
    back into the owning ``COSStream``. The ``/Filter`` entry is set on
    the owner so subsequent decode chains can recover the raw bytes."""

    def __init__(self, owner: COSStream, filters: Sequence[COSName]) -> None:
        super().__init__()
        self._owner = owner
        self._filters: list[COSName] = list(filters)
        self._committed = False

    def close(self) -> None:
        if not self._committed:
            self._committed = True
            # Local import to avoid a hard cos→filter dependency at
            # module import time (filter imports COSDictionary etc.).
            from pypdfbox.filter import FilterFactory  # noqa: PLC0415

            data = self.getvalue()
            # PDF filter chain reads left-to-right when *decoding*; when
            # *encoding* we must apply them in reverse so the rightmost
            # decoder undoes the first encoder, etc.
            for name in reversed(self._filters):
                f = FilterFactory.get(name)
                src = io.BytesIO(data)
                dst = io.BytesIO()
                f.encode(src, dst, self._owner)
                data = dst.getvalue()
            self._owner._set_raw_data_internal(data)
            # Record the filter chain on /Filter so future readers can
            # decode the bytes we just wrote.
            self._owner.set_filters(self._filters)
            self._owner._is_writing = False
            self._owner._sync_length_entry()
        super().close()


class COSStream(COSDictionary):
    """
    PDF stream — a dictionary plus a binary content body. Inherits
    ``COSDictionary`` per upstream (``COSStream extends COSDictionary``);
    overrides ``accept`` to dispatch ``visit_from_stream``.

    Body bytes are stored in a ``ScratchFile`` buffer (which spills to
    disk per the document's ``MemoryUsageSetting``). Filter encoding /
    decoding is delegated to ``pypdfbox.filter`` via ``FilterFactory``:
    :meth:`create_input_stream` decodes through the ``/Filter`` chain
    and :meth:`create_output_stream` accepts an optional filter chain
    that is encoded on close. Security-handler decryption is applied
    lazily before filters when a handler is attached. Image-flow
    predictor handling on encode remains delegated to the concrete
    filters.
    """

    def __init__(
        self,
        scratch_file: ScratchFile | None = None,
        items: Iterable[tuple[COSName | str, COSBase]] | None = None,
    ) -> None:
        super().__init__(items)
        if scratch_file is None:
            self._scratch = ScratchFile()
            self._owns_scratch = True
        else:
            self._scratch = scratch_file
            self._owns_scratch = False
        self._buffer: ScratchFileBuffer | None = None
        self._closed = False
        # Mirrors upstream ``isWriting``: while an output stream returned
        # by ``create_*output_stream`` is open, reading/length queries and
        # opening additional writers must raise. The committing close
        # callbacks on the inner output streams clear this back to False.
        self._is_writing = False
        # Encryption-aware decode: when populated, ``create_input_stream``
        # passes the raw bytes through ``handler.decrypt_stream`` BEFORE
        # running the /Filter chain. Mirrors PDFBox where the security
        # handler decrypts the on-disk bytes during parse, then the filter
        # chain decompresses the cleartext payload.
        self._security_handler: Any | None = None
        self._object_number: int = 0
        self._generation_number: int = 0
        self._decrypted: bool = False
        # Skip-encryption marker for spec-exempt streams. Per ISO 32000-2
        # §7.6.2 cross-reference streams (``/Type /XRef``) and the body
        # of the /Encrypt object itself are NEVER encrypted, even in an
        # encrypted document. Parser code sets this flag on those streams
        # so the document-level handler walk in ``PDDocument.decrypt``
        # — which attaches a handler to every stream in the pool — does
        # not double-decipher (or, worse, decipher already-plaintext
        # bytes as if they were ciphertext).
        self._skip_encryption: bool = False

    # ---------- raw bytes I/O ----------

    def check_closed(self) -> None:
        """Raise ``OSError`` if this stream's backing scratch file has
        been closed. Mirrors upstream ``checkClosed()`` (lines 105–114 of
        ``COSStream.java``): catches the case where a caller holds onto a
        ``COSStream`` whose enclosing ``PDDocument`` was closed.
        """
        if self._closed or (self._owns_scratch and self._scratch.is_closed()):
            raise OSError(
                "COSStream has been closed and cannot be read. "
                "Perhaps its enclosing PDDocument has been closed?"
            )

    def get_stream_cache(self) -> ScratchFile:
        """Return the ``ScratchFile`` backing this stream's body bytes.

        Mirrors upstream ``getStreamCache()`` (lines 116–124 of
        ``COSStream.java``) which lazily materialises a memory-only cache
        the first time a writer is opened. In pypdfbox the cache is
        attached at construction (either supplied by the caller via
        ``scratch_file=`` or created internally), so this is a thin
        accessor — but the contract matches: the return value is the
        same ``ScratchFile`` instance used by every subsequent
        ``create_*output_stream``/``set_raw_data`` call, and it lives
        until :meth:`close` runs.
        """
        return self._scratch

    def has_data(self) -> bool:
        return self._buffer is not None

    def get_length(self) -> int:
        """Return the value of the ``/Length`` dictionary entry (0 when absent).

        Mirrors upstream ``COSStream.getLength()`` (PDFBox 3.0.7), which returns
        ``getInt(COSName.LENGTH, 0)`` — the **dictionary** entry, NOT the live
        body-buffer length. On the normal write path the two agree because the
        output-stream ``close()`` callbacks sync ``/Length`` to the encoded body
        (:meth:`_sync_length_entry`). They diverge only when a producer plants a
        ``/Length`` that disagrees with the body (e.g. a corrupt PDF, or a manual
        ``set_item(/Length, ...)``): upstream trusts the declared entry, so we do
        too. Use ``get_raw_data()`` / ``create_raw_input_stream()`` for the true
        body length.
        """
        if self._is_writing:
            raise RuntimeError(
                "There is an open OutputStream associated with this COSStream. "
                "It must be closed before querying the length of this COSStream."
            )
        return self.get_int(_LENGTH, 0)

    def _sync_length_entry(self) -> None:
        """Write the current body length into the ``/Length`` dict entry.
        Called by the inner output-stream ``close()`` callbacks so the
        dictionary stays consistent with the body, matching upstream
        ``setInt(COSName.LENGTH, randomAccess.length())``. Uses the
        cached ``COSInteger.get`` factory so small values (notably 0)
        share the singleton instance — matches what
        ``COSDictionary.set_int`` does upstream."""
        length = self._buffer.length() if self._buffer is not None else 0
        super().set_item(_LENGTH, COSInteger.get(length))

    def get_raw_data(self) -> bytes:
        """Snapshot of the current raw (encoded) bytes."""
        if self._buffer is None:
            return b""
        cur = self._buffer.get_position()
        self._buffer.seek(0)
        out = bytearray(self._buffer.length())
        n = self._buffer.read_into(out)
        self._buffer.seek(cur)
        return bytes(out[:n] if n > 0 else b"")

    def set_raw_data(self, data: bytes | bytearray | memoryview) -> None:
        """Replace the raw body with ``data`` and sync the ``/Length`` entry.

        ``/Length`` is updated to ``len(data)`` so :meth:`get_length` (which
        mirrors upstream by reading the dictionary entry) stays consistent with
        the body — exactly as the output-stream ``close()`` callbacks do for the
        ``create_*output_stream`` path."""
        self._set_raw_data_internal(bytes(data))
        self._sync_length_entry()

    def _set_raw_data_internal(self, data: bytes) -> None:
        self.check_closed()
        if self._buffer is None:
            self._buffer = self._scratch.create_buffer()
        else:
            self._buffer.clear()
        self._buffer.write_bytes(data)
        self._buffer.seek(0)

    def create_raw_input_stream(self) -> BinaryIO:
        """Return a fresh ``BytesIO`` snapshot of the current raw bytes.

        Raises ``OSError`` if the stream has no data (PDFBox parity).
        Raises ``RuntimeError`` while an output stream is open on this
        COSStream — mirrors upstream ``IllegalStateException`` from the
        ``isWriting`` guard in ``createRawInputStream``.
        """
        self.check_closed()
        if self._is_writing:
            raise RuntimeError("Cannot read while there is an open stream writer")
        if self._buffer is None:
            raise OSError("stream has no data")
        return io.BytesIO(self.get_raw_data())

    def ensure_decrypted(self) -> None:
        """Materialise the decrypted raw body when a security handler is
        attached and the on-disk bytes are still ciphertext.

        Mirrors PDFBox semantics where the security handler decrypts a
        stream's bytes on first access so that any later consumer — the
        filter decode path *or the writer* — sees plaintext. pypdfbox
        decrypts lazily (``create_input_stream`` undoes the cipher just
        before the /Filter chain runs), which means a stream that was
        loaded encrypted but never decoded still holds ciphertext in its
        ``_buffer``. The writer must call this before re-enciphering on
        save, otherwise it would encipher already-encrypted bytes a
        second time (double encryption → FlateDecode garbage on reload).

        Idempotent: ``_decrypted`` guards against a second undo, and the
        no-handler / skip-encryption cases are no-ops."""
        if self._security_handler is None or self._decrypted:
            return
        if self._buffer is None:
            self._decrypted = True
            return
        raw = self.get_raw_data()
        plain = self._security_handler.decrypt_stream(
            raw, self._object_number, self._generation_number
        )
        self._set_raw_data_internal(plain)
        self._decrypted = True

    def create_raw_output_stream(self) -> BinaryIO:
        """Return a writable stream; on ``close()`` its contents replace
        this stream's raw body. Raises ``RuntimeError`` if another writer
        is already open (mirrors upstream ``isWriting`` guard)."""
        self.check_closed()
        if self._is_writing:
            raise RuntimeError("Cannot have more than one open stream writer.")
        self._is_writing = True
        return _CommittingOutputStream(self)

    def set_security_handler(
        self,
        handler: Any | None,
        obj_num: int,
        gen_num: int,
    ) -> None:
        """Attach the document's security handler plus this stream's
        ``(obj_num, gen_num)`` so :meth:`create_input_stream` can call
        ``handler.decrypt_stream(raw, obj_num, gen_num)`` lazily on the
        first decode. ``PDDocument.decrypt`` walks the object pool and
        calls this on every ``COSStream``.

        No-op when :meth:`set_skip_encryption` has marked this stream as
        spec-exempt (xref streams, /Encrypt body, etc.) — those bodies
        are guaranteed plaintext on disk and must not be deciphered.
        Also auto-skips when ``/Type /XRef`` is present in the dict: the
        parser builds one COSStream during ``_handle_xref_stream_at`` and
        marks it, but lazy loaders on the indirect pool entry can later
        materialise a *different* COSStream from disk. Re-discovering
        the xref-stream identity here closes that gap so a stray decrypt
        walk doesn't garble the body of the second instance."""
        if self._skip_encryption:
            return
        type_name = self.get_dictionary_object(_TYPE)
        if isinstance(type_name, COSName) and type_name.name == "XRef":
            self._skip_encryption = True
            return
        # /Type /Metadata streams stay cleartext when the active handler has
        # /EncryptMetadata=false. Mirrors the write-side exemption in
        # ``COSWriter.visit_from_stream`` (wave 1367) so the bytes that
        # landed on disk un-ciphered are read back without an undo pass.
        if (
            isinstance(type_name, COSName)
            and type_name.name == "Metadata"
            and handler is not None
            and not bool(
                getattr(handler, "is_encrypt_metadata", lambda: True)()
            )
        ):
            self._skip_encryption = True
            return
        # PDFBOX-3173 / PDFBOX-2603: a /Type /Metadata stream whose raw bytes
        # already begin with the cleartext XMP marker ``<?xpacket`` is not
        # actually encrypted — some producers emit cleartext metadata while
        # still declaring /EncryptMetadata true. Upstream ``decryptStream``
        # detects this, warns, and leaves the bytes untouched; mirror it so we
        # don't corrupt the metadata by deciphering plaintext. Only applies
        # when metadata decrypt is in effect (the /EncryptMetadata=false case
        # already returned above).
        if (
            isinstance(type_name, COSName)
            and type_name.name == "Metadata"
            and self._buffer is not None
        ):
            try:
                head = bytes(self.get_raw_data()[:9])
            except Exception:  # noqa: BLE001 — defensive; fall through to decrypt
                head = b""
            if head == b"<?xpacket":
                _LOG.warning(
                    "Metadata is not encrypted, but was expected to be; read "
                    "PDF specification about EncryptMetadata (default value: "
                    "true)"
                )
                self._skip_encryption = True
                return
        self._security_handler = handler
        self._object_number = int(obj_num)
        self._generation_number = int(gen_num)
        # Fresh handler attachment — clear the "already-decrypted" flag so
        # the next read deciphers the on-disk bytes once.
        self._decrypted = False

    def set_skip_encryption(self, skip: bool) -> None:
        """Mark this stream as exempt from the security-handler decode
        pass. ISO 32000-2 §7.6.2 mandates that cross-reference streams
        and the /Encrypt object itself are never encrypted; the parser
        sets this on those streams so the later document-level
        ``PDDocument.decrypt`` walk doesn't attach a handler that would
        garble the already-plaintext body. Idempotent."""
        self._skip_encryption = bool(skip)
        if self._skip_encryption:
            # Defensive: if a handler had already been attached (e.g. by
            # a prior decrypt walk that ran before the parser flagged the
            # stream), drop it so no future ``create_input_stream`` call
            # tries to undo a cipher that was never applied.
            self._security_handler = None
            self._decrypted = False

    def is_skip_encryption(self) -> bool:
        return self._skip_encryption

    def create_input_stream(
        self,
        stop_filters: Sequence[str | COSName] | str | COSName | None = None,
    ) -> BinaryIO:
        """Return a stream over the **decoded** body.

        Without ``/Filter`` this is equivalent to
        :meth:`create_raw_input_stream`. With ``/Filter`` set, each filter
        in the chain is resolved through ``FilterFactory`` and applied in
        order. ``stop_filters`` (a sequence of filter names) lets callers
        halt decoding early — e.g. image XObjects stop before
        ``/DCTDecode`` so the JPEG bytes are preserved verbatim. Mirrors
        upstream ``COSStream.createInputStream(List<String>)``.

        When a security handler has been attached via
        :meth:`set_security_handler`, the raw bytes are first decrypted
        in-place (and re-stored as the new raw body) so subsequent calls
        skip the cipher pass — ``_decrypted`` guards against double-undo.
        """
        self.check_closed()
        if self._is_writing:
            raise RuntimeError("Cannot read while there is an open stream writer")
        if self._buffer is None:
            raise OSError("stream has no data")

        # Encryption-aware decode: undo the cipher pass exactly once,
        # before the /Filter chain runs.
        if self._security_handler is not None and not self._decrypted:
            raw = self.get_raw_data()
            plain = self._security_handler.decrypt_stream(
                raw, self._object_number, self._generation_number
            )
            self._set_raw_data_internal(plain)
            self._decrypted = True

        chain = _dedupe_filter_chain(self.get_filter_list())
        if not chain:
            return self.create_raw_input_stream()

        # Local import to keep cos free of a static filter dep.
        from pypdfbox.filter import FilterFactory  # noqa: PLC0415

        stop_set = _coerce_stop_filter_names(stop_filters)

        data = self.get_raw_data()
        for index, name in enumerate(chain):
            if _canonical_filter_name(name.name) in stop_set:
                break
            try:
                f = FilterFactory.get(name)
            except KeyError as exc:
                # Untrusted /Filter naming an unregistered (or corrupted)
                # filter must fail with an I/O-level error, not leak the
                # registry's KeyError to the caller. Mirrors upstream
                # ``FilterFactory.getFilter`` which throws
                # ``IOException("Invalid filter: ...")`` during decode.
                raise OSError(f"Invalid filter: {name.name}") from exc
            src = io.BytesIO(data)
            dst = io.BytesIO()
            f.decode(src, dst, self, index)
            data = dst.getvalue()
        return io.BytesIO(data)

    def create_output_stream(
        self,
        filters: COSBase | Sequence[COSName | str] | str | None = None,
    ) -> BinaryIO:
        """Return a writable stream that on ``close()`` becomes the body.

        - ``filters=None`` → the bytes you write are stored verbatim
          (raw / unencoded). Any existing ``/Filter`` entry is removed
          so future decoded reads do not apply a stale filter.
        - ``filters`` is a single ``COSName`` → wraps in a one-element
          chain.
        - ``filters`` is a ``COSArray`` of names *or* a Python sequence
          of ``COSName`` / ``str`` → each filter is applied in reverse on
          ``close()`` so reading back through ``create_input_stream``
          recovers the bytes you wrote. ``/Filter`` is set accordingly.

        Raises ``RuntimeError`` if another writer is already open."""
        self.check_closed()
        if self._is_writing:
            raise RuntimeError("Cannot have more than one open stream writer.")
        if filters is None:
            self.clear_filters()
            return self.create_raw_output_stream()

        names = _coerce_filter_chain(filters)
        self._is_writing = True
        return _EncodingOutputStream(self, names)

    def create_view(self) -> Any:
        """Return a ``RandomAccessRead`` over the **decoded** stream body.

        Mirrors upstream ``COSStream.createView()`` (line 181 of
        ``COSStream.java``): when ``/Filter`` is empty the returned view
        is a buffer over the raw bytes; when filters are present the
        chain is decoded fully into memory and wrapped in a
        ``RandomAccessReadBuffer``. Per upstream the result is seekable
        and length-queryable, suitable for image XObjects and embedded
        fonts that need random access to the decoded payload.

        Raises ``OSError`` if the stream has no body — matches the
        ``createRawInputStream`` precondition that upstream enforces
        through ``createView`` when no filters are present."""
        # Local import to keep cos free of a static io dep at module-load.
        from pypdfbox.io import RandomAccessReadBuffer  # noqa: PLC0415

        if self._buffer is None:
            raise OSError("stream has no data")
        # Encryption-aware path: reuse ``create_input_stream`` so the
        # security-handler cipher pass runs exactly once before any
        # filter chain is applied. This also lets ``create_view`` honour
        # ``/Filter`` chains identically to ``create_input_stream``.
        with self.create_input_stream() as src:
            return RandomAccessReadBuffer(src.read())

    # ---------- decoded / raw bytes convenience ----------

    def to_byte_array(self) -> bytes:
        """All decoded bytes as a ``bytes``. Returns ``b""`` for an
        empty stream (no body set). Mirrors upstream ``toByteArray()``."""
        if self._buffer is None or self._buffer.length() == 0:
            return b""
        with self.create_input_stream() as src:
            return src.read()

    def to_raw_byte_array(self) -> bytes:
        """All raw (still-encoded) bytes as a ``bytes``. Returns ``b""``
        for an empty stream."""
        return self.get_raw_data()

    def set_data(
        self,
        data: bytes | bytearray | memoryview,
        filters: Sequence[COSName | str] | COSName | str | None = None,
    ) -> None:
        """Convenience setter — write ``data`` (raw, unencoded) through
        the supplied filter chain. With ``filters=None`` the bytes are
        stored verbatim and any existing ``/Filter`` is removed.
        With a filter chain, ``data`` is treated as the decoded payload
        and is encoded on the way in (and ``/Filter`` is set)."""
        with self.create_output_stream(filters) as out:
            out.write(bytes(data))

    # ---------- /Filter introspection ----------

    def get_filters(self) -> COSBase | None:
        """Return the raw ``/Filter`` value as stored on the dictionary.

        Per ISO 32000-2 §7.4.2 the entry is one of:
        - absent → ``None``
        - a single ``COSName``
        - a ``COSArray`` of ``COSName``

        Mirrors upstream ``COSStream.getFilters()``. Use
        :meth:`get_filter_list` to receive a normalized list of names."""
        return self.get_dictionary_object(_FILTER)

    def set_filters(
        self,
        filters: COSBase | Sequence[COSName | str] | str | None,
    ) -> None:
        """Replace the ``/Filter`` entry.

        ``None`` removes the entry. A single name is stored in PDF's
        compact single-name form; multiple names are stored as a
        ``COSArray``. Empty sequences are preserved as an empty array so
        malformed or intentionally empty producer data can round-trip.
        """
        if filters is None:
            self.clear_filters()
            return
        names = _coerce_filter_chain(filters)
        if len(names) == 1:
            self.set_item(_FILTER, names[0])
        else:
            self.set_item(_FILTER, COSArray(list(names)))

    def has_filters(self) -> bool:
        """Return ``True`` when ``/Filter`` contains at least one name."""
        return bool(self.get_filter_list())

    def has_filter(self, name: COSName | str) -> bool:
        """Return ``True`` when ``name`` appears in the ``/Filter`` chain."""
        return _coerce_filter_name(name) in self.get_filter_list()

    def get_first_filter(self) -> COSName | None:
        """Return the first filter in the chain, or ``None`` when absent."""
        filters = self.get_filter_list()
        return filters[0] if filters else None

    def get_filters_as_strings(self) -> list[str]:
        """Return the ``/Filter`` chain as plain names without leading slash."""
        return [name.name for name in self.get_filter_list()]

    def clear_filters(self) -> None:
        """Remove the ``/Filter`` entry."""
        self.remove_item(_FILTER)

    def get_decode_parms(self) -> COSBase | None:
        """Return the raw ``/DecodeParms`` value, falling back to ``/DP``."""
        return self.get_dictionary_object(_DECODE_PARMS, _DP)

    def has_decode_parms(self) -> bool:
        """Return ``True`` when ``/DecodeParms`` or short-form ``/DP`` is present."""
        return self.get_decode_parms() is not None

    def clear_decode_parms(self) -> None:
        """Remove both ``/DecodeParms`` and short-form ``/DP`` entries."""
        self.remove_item(_DECODE_PARMS)
        self.remove_item(_DP)

    def get_filter_list(self) -> list[COSName]:
        """Return the ``/Filter`` chain as a list of ``COSName``.

        Per PDF spec, ``/Filter`` may be absent, a single name, or an
        array of names. Returns ``[]`` when absent.

        Mirrors upstream ``COSStream.getFilterList()`` exactly:

        * a single ``COSName`` → a one-element list;
        * a ``COSArray`` → each element must be a ``COSName``; a non-name
          element raises ``OSError`` ("Forbidden type in filter array: ...",
          upstream ``IOException``);
        * any other value (a non-name scalar such as ``COSString`` /
          ``COSInteger`` / ``COSBoolean``) is treated leniently as "no
          filters" and yields an empty list — upstream falls through to the
          ``new ArrayList<>()`` branch, so the body is passed through
          verbatim (decoded == raw)."""
        f = self.get_filters()
        if isinstance(f, COSName):
            return [f]
        if isinstance(f, COSArray):
            out: list[COSName] = []
            for entry in f:
                if isinstance(entry, COSName):
                    out.append(entry)
                else:
                    type_name = "null" if entry is None else type(entry).__name__
                    raise OSError(f"Forbidden type in filter array: {type_name}")
            return out
        # Absent or a non-name scalar (COSString / COSInteger / COSBoolean):
        # upstream returns an empty list, so no filtering is applied.
        return []

    # ---------- text-string convenience ----------

    def to_text_string(self) -> str:
        """Return the decoded body interpreted as a PDF text string.

        Mirrors upstream ``COSStream.toTextString``: decode the body
        through the ``/Filter`` chain, wrap the result in a ``COSString``,
        and return its text-string representation (UTF-16BE BOM,
        UTF-8 BOM, or PDFDocEncoding fallback). Returns ``""`` when the
        body cannot be read for any reason — matches the upstream
        swallow-and-log behavior."""
        # Local import to avoid a static cycle (COSString lives next door
        # but importing eagerly would tighten module-load ordering).
        from .cos_string import COSString  # noqa: PLC0415

        try:
            with self.create_input_stream() as src:
                data = src.read()
        except (OSError, ValueError):
            return ""
        return COSString(data).get_string()

    # ---------- bulk output ----------

    def write(self, output: BinaryIO) -> int:
        """Write the raw (encoded) body to ``output`` and return the
        number of bytes written.

        pypdfbox addition — upstream's ``COSStream`` has no public
        ``write`` method; ``COSWriter`` instead opens
        :meth:`create_raw_input_stream` and copies through. Surfacing
        the bulk-copy helper here lets callers serialise a stream's
        body without juggling the input-stream resource themselves and
        keeps the call site a one-liner: ``stream.write(out_target)``.

        Honours the ``isWriting`` guard for parity with the rest of the
        I/O surface — a concurrent open writer would let the read race
        with an unflushed encode.
        """
        self.check_closed()
        if self._is_writing:
            raise RuntimeError("Cannot read while there is an open stream writer")
        data = self.get_raw_data()
        output.write(data)
        return len(data)

    # ---------- lifecycle ----------

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
        if self._owns_scratch:
            self._scratch.close()

    def is_closed(self) -> bool:
        return self._closed

    # ---------- visitor ----------

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_stream(self)

    def __enter__(self) -> COSStream:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"COSStream(dict_size={self.size()}, body_len={self.get_length()})"


def _coerce_filter_chain(
    filters: COSBase | Sequence[COSName | str] | str,
) -> list[COSName]:
    """Normalize the many shapes ``filters`` may take into a list of
    ``COSName``. Accepts a single ``COSName``, a ``COSArray`` of names,
    a single ``str``, or any sequence of ``COSName`` / ``str``."""
    if isinstance(filters, COSName):
        return [filters]
    if isinstance(filters, COSArray):
        array_names: list[COSName] = []
        for entry in filters:
            if isinstance(entry, COSName):
                array_names.append(entry)
            else:
                raise TypeError(
                    f"non-name entry in /Filter array: {type(entry).__name__}"
                )
        return array_names
    if isinstance(filters, str):
        return [COSName.get_pdf_name(filters)]
    if isinstance(filters, COSBase):
        raise TypeError(f"unexpected /Filter type: {type(filters).__name__}")
    # Treat as a generic sequence of name-or-string.
    sequence_names: list[COSName] = []
    for filter_entry in filters:
        if isinstance(filter_entry, COSName):
            sequence_names.append(filter_entry)
        elif isinstance(filter_entry, str):
            sequence_names.append(COSName.get_pdf_name(filter_entry))
        else:
            raise TypeError(
                f"filter entry must be COSName or str, got {type(filter_entry).__name__}"
            )
    return sequence_names


def _coerce_filter_name(name: COSName | str) -> COSName:
    if isinstance(name, COSName):
        return name
    return COSName.get_pdf_name(name)


def _coerce_stop_filter_names(
    stop_filters: Sequence[str | COSName] | str | COSName | None,
) -> set[str]:
    if stop_filters is None:
        return set()
    if isinstance(stop_filters, COSName):
        return {_canonical_filter_name(stop_filters.name)}
    if isinstance(stop_filters, str):
        return {_canonical_filter_name(stop_filters)}
    return {
        _canonical_filter_name(entry.name if isinstance(entry, COSName) else entry)
        for entry in stop_filters
    }


def _canonical_filter_name(name: str) -> str:
    return _FILTER_NAME_ALIASES.get(name, name)


def _dedupe_filter_chain(chain: list[COSName]) -> list[COSName]:
    """Remove duplicate filter entries, keeping the first occurrence.

    Mirrors upstream ``Filter.decode``: when a ``/Filter`` chain of length
    > 1 resolves to fewer distinct filters than entries (a ``HashSet`` of
    the resolved ``Filter`` instances is smaller than the list), it rebuilds
    the list keeping only the first occurrence of each and logs "Removed
    duplicated filter entries". Because abbreviated names (``Fl``) resolve to
    the *same* ``Filter`` instance as their long form (``FlateDecode``),
    dedup is keyed on the canonical filter name, not the raw entry — so
    ``[Fl, FlateDecode]`` collapses to a single decode just as it does
    upstream."""
    if len(chain) <= 1:
        return chain
    seen: set[str] = set()
    deduped: list[COSName] = []
    for name in chain:
        key = _canonical_filter_name(name.name)
        if key not in seen:
            seen.add(key)
            deduped.append(name)
    if len(deduped) != len(chain):
        _LOG.warning("Removed duplicated filter entries")
    return deduped
