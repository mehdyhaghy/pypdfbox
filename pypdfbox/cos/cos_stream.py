from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from typing import Any, BinaryIO

from pypdfbox.io import ScratchFile, ScratchFileBuffer

from .cos_array import COSArray
from .cos_base import COSBase
from .cos_dictionary import COSDictionary
from .cos_name import COSName
from .i_cos_visitor import ICOSVisitor


class _CommittingOutputStream(io.BytesIO):
    """``BytesIO`` subclass whose ``close()`` commits the buffered bytes
    back into the owning ``COSStream``."""

    def __init__(self, owner: COSStream) -> None:
        super().__init__()
        self._owner = owner
        self._committed = False

    def close(self) -> None:
        if not self._committed:
            self._committed = True
            self._owner._set_raw_data_internal(self.getvalue())
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
            if len(self._filters) == 1:
                self._owner.set_item(COSName.FILTER, self._filters[0])  # type: ignore[attr-defined]
            else:
                self._owner.set_item(COSName.FILTER, COSArray(list(self._filters)))  # type: ignore[attr-defined]
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
    that is encoded on close. Encryption-aware streams and image-flow
    predictor handling on encode remain deferred (see ``CHANGES.md``).
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

    def has_data(self) -> bool:
        return self._buffer is not None and self._buffer.length() > 0

    def get_length(self) -> int:
        return self._buffer.length() if self._buffer is not None else 0

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
        """Replace the raw body with ``data``."""
        self._set_raw_data_internal(bytes(data))

    def _set_raw_data_internal(self, data: bytes) -> None:
        if self._closed:
            raise ValueError("operation on closed COSStream")
        if self._buffer is None:
            self._buffer = self._scratch.create_buffer()
        else:
            self._buffer.clear()
        self._buffer.write_bytes(data)
        self._buffer.seek(0)

    def create_raw_input_stream(self) -> BinaryIO:
        """Return a fresh ``BytesIO`` snapshot of the current raw bytes.

        Raises ``OSError`` if the stream has no data (PDFBox parity)."""
        if self._buffer is None:
            raise OSError("stream has no data")
        return io.BytesIO(self.get_raw_data())

    def create_raw_output_stream(self) -> BinaryIO:
        """Return a writable stream; on ``close()`` its contents replace
        this stream's raw body."""
        if self._closed:
            raise ValueError("operation on closed COSStream")
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
        type_name = self.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
        if isinstance(type_name, COSName) and type_name.name == "XRef":
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
        stop_filters: Sequence[str | COSName] | None = None,
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

        chain = self.get_filter_list()
        if not chain:
            return self.create_raw_input_stream()

        # Local import to keep cos free of a static filter dep.
        from pypdfbox.filter import FilterFactory  # noqa: PLC0415

        stop_set: set[str] = set()
        if stop_filters is not None:
            for s in stop_filters:
                stop_set.add(s.name if isinstance(s, COSName) else s)

        data = self.get_raw_data()
        for index, name in enumerate(chain):
            if name.name in stop_set:
                break
            f = FilterFactory.get(name)
            src = io.BytesIO(data)
            dst = io.BytesIO()
            f.decode(src, dst, self, index)
            data = dst.getvalue()
        return io.BytesIO(data)

    def create_output_stream(
        self,
        filters: COSBase | Sequence[COSName | str] | None = None,
    ) -> BinaryIO:
        """Return a writable stream that on ``close()`` becomes the body.

        - ``filters=None`` → the bytes you write are stored verbatim
          (raw / unencoded). The stream's existing ``/Filter`` entry is
          left untouched.
        - ``filters`` is a single ``COSName`` → wraps in a one-element
          chain.
        - ``filters`` is a ``COSArray`` of names *or* a Python sequence
          of ``COSName`` / ``str`` → each filter is applied in reverse on
          ``close()`` so reading back through ``create_input_stream``
          recovers the bytes you wrote. ``/Filter`` is set accordingly."""
        if self._closed:
            raise ValueError("operation on closed COSStream")
        if filters is None:
            return self.create_raw_output_stream()

        names = _coerce_filter_chain(filters)
        return _EncodingOutputStream(self, names)

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
        stored verbatim and any existing ``/Filter`` is left untouched.
        With a filter chain, ``data`` is treated as the decoded payload
        and is encoded on the way in (and ``/Filter`` is set)."""
        with self.create_output_stream(filters) as out:
            out.write(bytes(data))

    # ---------- /Filter introspection ----------

    def get_filter_list(self) -> list[COSName]:
        """Return the ``/Filter`` chain as a list of ``COSName``.

        Per PDF spec, ``/Filter`` may be absent, a single name, or an
        array of names. Returns ``[]`` when absent."""
        f = self.get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
        if f is None:
            return []
        if isinstance(f, COSName):
            return [f]
        if isinstance(f, COSArray):
            out: list[COSName] = []
            for entry in f:
                if isinstance(entry, COSName):
                    out.append(entry)
                else:
                    raise TypeError(f"non-name entry in /Filter array: {entry!r}")
            return out
        raise TypeError(f"unexpected /Filter type: {type(f).__name__}")

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
        out: list[COSName] = []
        for entry in filters:
            if isinstance(entry, COSName):
                out.append(entry)
            else:
                raise TypeError(
                    f"non-name entry in /Filter array: {type(entry).__name__}"
                )
        return out
    if isinstance(filters, str):
        return [COSName.get_pdf_name(filters)]
    # Treat as a generic sequence of name-or-string.
    out = []
    for entry in filters:
        if isinstance(entry, COSName):
            out.append(entry)
        elif isinstance(entry, str):
            out.append(COSName.get_pdf_name(entry))
        else:
            raise TypeError(
                f"filter entry must be COSName or str, got {type(entry).__name__}"
            )
    return out
