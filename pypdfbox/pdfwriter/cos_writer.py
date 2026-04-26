from __future__ import annotations

import hashlib
import io
import logging
import secrets
import time
from collections import deque
from typing import Any, BinaryIO

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
    ICOSVisitor,
)
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

# Sentinel name objects used to filter the /Encrypt and /ID entries out of the
# encryption pipeline. Hoisted to module scope so we don't recompute on every
# leaf visit. ISO 32000-1 §7.6.1: the /Encrypt dictionary itself is never
# encrypted (would be circular), and the file identifier /ID array is the
# trailer-level handle the handler keys off of — encrypting it would make the
# document undecryptable.
_ID_NAME: COSName = COSName.get_pdf_name("ID")

from .cos_standard_output_stream import COSStandardOutputStream
from .cos_writer_xref_entry import COSWriterXRefEntry

_logger = logging.getLogger(__name__)


# ---- byte-literal tokens (mirror PDFBox COSWriter constants) -----------------

DICT_OPEN: bytes = b"<<"
DICT_CLOSE: bytes = b">>"
SPACE: bytes = b" "
COMMENT: bytes = b"%"
EOF: bytes = b"%%EOF"
REFERENCE: bytes = b"R"
XREF: bytes = b"xref"
XREF_FREE: bytes = b"f"
XREF_USED: bytes = b"n"
TRAILER: bytes = b"trailer"
STARTXREF: bytes = b"startxref"
OBJ: bytes = b"obj"
ENDOBJ: bytes = b"endobj"
ARRAY_OPEN: bytes = b"["
ARRAY_CLOSE: bytes = b"]"
STREAM: bytes = b"stream"
ENDSTREAM: bytes = b"endstream"
# Binary-marker bytes for the header comment. Identical to upstream
# ``COSWriter.GARBAGE`` so the emitted file is byte-identical to what
# PDFBox produces (ISO 32000-1 §7.5.2 only requires any 4 bytes ≥ 0x80).
GARBAGE: bytes = b"\xf6\xe4\xfc\xdf"


# Bytes that must be ``#xx``-escaped inside a name (anything outside the
# PDFBox-style printable allowlist). Match upstream ``COSName.writePDF``.
def _is_printable_name_byte(b: int) -> bool:
    return (
        (0x41 <= b <= 0x5A)  # A-Z
        or (0x61 <= b <= 0x7A)  # a-z
        or (0x30 <= b <= 0x39)  # 0-9
        or b in (0x2B, 0x2D, 0x5F, 0x40, 0x2A, 0x24, 0x3B, 0x2E)
        # + - _ @ * $ ; .
    )


def _format_xref_offset(offset: int) -> bytes:
    """Zero-pad to 10 digits — matches upstream ``formatXrefOffset``."""
    return f"{offset:010d}".encode("ascii")


def _format_xref_generation(gen: int) -> bytes:
    """Zero-pad to 5 digits — matches upstream ``formatXrefGeneration``."""
    return f"{gen:05d}".encode("ascii")


# Adapter: ``COSStandardOutputStream`` accepts anything with ``write(bytes)``.
# A ``RandomAccessWrite`` exposes ``write_bytes(...)`` instead, so we wrap it.
class _RawSinkAdapter:
    """Tiny shim presenting ``write(bytes) -> int`` over a sink that may
    only expose ``write_bytes(...)`` (e.g. ``RandomAccessWrite``)."""

    def __init__(self, sink: Any) -> None:
        self._sink = sink

    def write(self, data: bytes, /) -> int:
        if isinstance(self._sink, RandomAccessWrite):
            self._sink.write_bytes(data)
        else:
            self._sink.write(data)
        return len(data)

    def flush(self) -> None:
        flush = getattr(self._sink, "flush", None)
        if callable(flush):
            flush()

    def close(self) -> None:
        close = getattr(self._sink, "close", None)
        if callable(close):
            close()


class COSWriter(ICOSVisitor):
    """
    Serialize a ``COSDocument`` back to bytes using the traditional xref
    full-save path.

    Mirrors ``org.apache.pdfbox.pdfwriter.COSWriter``. Cluster #1 stubs
    out incremental save, xref-stream output, object-stream packing,
    encryption, and signatures — see ``CHANGES.md`` for the full list.

    Typical usage::

        with open("out.pdf", "wb") as f, COSWriter(f) as writer:
            writer.write(document)
    """

    def __init__(
        self,
        output: BinaryIO | RandomAccessWrite,
        *,
        incremental: bool = False,
        incremental_input: RandomAccessRead | None = None,
    ) -> None:
        self._output = output
        self._incremental_update = incremental
        self._incremental_input = incremental_input
        # In incremental mode the body, xref, and trailer are accumulated in
        # an in-memory buffer; the final ``doWriteIncrement`` copies the
        # source bytes to the real output and then drains the buffer
        # (mirrors PDFBox's ByteArrayOutputStream → OutputStream pipeline).
        if incremental:
            self._increment_buffer: io.BytesIO | None = io.BytesIO()
            self._adapter = _RawSinkAdapter(self._increment_buffer)
            # ``position`` is seeded with the source length so xref offsets
            # are computed as if the increment were already concatenated to
            # the original file. Matches upstream's
            # ``new COSStandardOutputStream(output, inputData.length())``.
            self._standard_output = COSStandardOutputStream(
                self._adapter, position=0
            )
        else:
            self._increment_buffer = None
            self._adapter = _RawSinkAdapter(output)
            self._standard_output = COSStandardOutputStream(self._adapter)

        # writer state — mirrors private fields on the upstream class.
        self._startxref: int = 0
        self._number: int = 0
        # ``object_keys``: COSBase identity → assigned key. Identity-keyed
        # so two equal-but-distinct objects get separate keys (matches
        # upstream ``Map<COSBase, COSObjectKey>``). Implemented as a dict
        # keyed by ``id(obj)`` with a parallel strong-reference table.
        self._object_keys: dict[int, COSObjectKey] = {}
        self._key_holders: dict[int, COSBase] = {}
        # ``key_object``: COSObjectKey → COSBase (target of indirect ref).
        self._key_object: dict[COSObjectKey, COSBase] = {}
        self._xref_entries: list[COSWriterXRefEntry] = []
        # FIFO queue of objects awaiting their indirect-object frame.
        self._objects_to_write: deque[COSBase] = deque()
        # identity-set of objects already emitted.
        self._written_objects: set[int] = set()
        # identity-set of "actuals" (target of any COSObject in the queue).
        self._actuals_added: set[int] = set()
        self._current_object_key: COSObjectKey | None = None
        self._closed = False

        # ---- encryption pipeline state (security cluster integration) ----
        # ``_security_handler``: active handler used to encipher COSStream
        # bodies and COSString payloads inside indirect objects. Populated by
        # ``write(PDDocument)`` from either ``pd._security_handler`` (already
        # decrypted document being re-saved) or by calling
        # ``protection_policy``'s handler factory. ``None`` disables the
        # encryption pass entirely.
        self._security_handler: Any = None
        # Identity of the COSDictionary backing the trailer's ``/Encrypt``
        # entry (the dictionary, not its wrapping COSObject) so that strings
        # encountered while serialising the encryption dictionary itself are
        # NOT encrypted — would otherwise be circular per ISO 32000-1 §7.6.1.
        self._encrypt_dict_id: int | None = None
        # When walking the trailer (the outer ``visit_from_dictionary`` for
        # the trailer dict) ``_current_object_key`` is None and we must not
        # encrypt strings; the trailer is a top-level structure, not an
        # indirect object. Tracked explicitly because the trailer's /ID is
        # also the cleartext key the handler relied on.
        self._in_encrypt_subtree: bool = False

    # ---------- public API ----------

    def get_standard_output(self) -> COSStandardOutputStream:
        return self._standard_output

    def get_startxref(self) -> int:
        return self._startxref

    def get_xref_entries(self) -> list[COSWriterXRefEntry]:
        return self._xref_entries

    def write(self, document: Any) -> None:
        """Emit ``document`` end-to-end as a self-contained PDF.

        Accepts either a ``COSDocument`` (low-level, no encryption support
        — mirrors PDFBox's ``write(COSDocument)`` overload) or a
        ``PDDocument`` (high-level, drives the encryption pipeline when
        the document carries an active ``_protection_policy`` or
        ``_security_handler``). The PDDocument overload mirrors upstream's
        ``write(PDDocument)``.
        """
        if self._closed:
            raise ValueError("operation on closed COSWriter")

        # Accept PDDocument → unwrap to COSDocument and stage encryption.
        # Avoid a hard dependency on pdmodel by duck-typing the wrapper.
        pd_document: Any = None
        if isinstance(document, COSDocument):
            cos_document = document
        elif hasattr(document, "get_document") and hasattr(document, "is_encrypted"):
            pd_document = document
            cos_document = document.get_document()
            if not isinstance(cos_document, COSDocument):
                raise TypeError(
                    "PDDocument.get_document() did not return a COSDocument"
                )
        else:
            raise TypeError(
                f"COSWriter.write expects a COSDocument or PDDocument; got "
                f"{type(document).__name__}"
            )

        # Stage the encryption handler BEFORE numbering / serialisation so
        # that ``prepare_document`` has a chance to mutate the trailer
        # (it may add an /Encrypt indirect entry whose object number must
        # be reflected in ``self._number``).
        if pd_document is not None and not self._incremental_update:
            self._stage_encryption(pd_document, cos_document)

        # Seed numbering from the highest existing object number so we
        # don't reuse keys when the parser already loaded them.
        existing_keys = cos_document.get_object_keys()
        self._number = max((k.object_number for k in existing_keys), default=0)

        if self._incremental_update:
            # Auto-pull the input source from the document if the caller
            # did not pass one explicitly (matches the convenience wiring
            # PDDocument provides upstream).
            if self._incremental_input is None:
                self._incremental_input = cos_document.get_source()
            if self._incremental_input is None:
                raise ValueError(
                    "incremental save requires either incremental_input= or "
                    "a COSDocument carrying a source (Loader.load_pdf populates this)"
                )
            self._reject_signed_with_byterange_placeholder(cos_document)
            # /ID synthesis: skip in incremental mode — the trailer must
            # preserve the source's /ID array verbatim (PDF 32000-1 §14.4).
            self._do_write_increment(cos_document)
            return

        self._ensure_document_id(cos_document)
        # Refresh the encryption-dict identity AFTER ``_ensure_document_id``
        # in case ``prepare_document`` ran first (it did, above) — the dict
        # may have been wrapped in an indirect since.
        self._refresh_encrypt_dict_id(cos_document)
        cos_document.accept(self)

    # ---------- encryption staging ----------

    def _stage_encryption(self, pd_document: Any, cos_document: COSDocument) -> None:
        """Wire ``self._security_handler`` from the PDDocument when the
        document should be saved encrypted.

        Two write paths land here:

        * **Fresh encryption** — ``protect()`` was called, so
          ``pd._protection_policy`` is populated. We instantiate the
          policy's standard handler, prime the trailer with a /ID array
          (the standard handler keys off /ID[0] for r2-r4 derivation),
          then call ``handler.prepare_document`` to populate /Encrypt.

        * **Re-save of an already-encrypted document** —
          ``pd._security_handler`` is set (from a prior ``decrypt`` call)
          and ``set_all_security_to_be_removed(False)``. We reuse the
          same handler so streams are re-encrypted with the same file
          key, preserving the /Encrypt entry as-is.

        When ``set_all_security_to_be_removed(True)`` is honoured by
        ``PDDocument.save`` (which strips /Encrypt before this point),
        we never get here — the security_handler stays None and the
        plaintext path is taken.
        """
        # Path 1: caller wants to remove security on save → no-op.
        if pd_document.is_all_security_to_be_removed():
            return

        # Path 2: fresh ``protect()`` policy → derive a handler.
        protection_policy = getattr(pd_document, "_protection_policy", None)
        if protection_policy is not None:
            from pypdfbox.pdmodel.encryption.standard_protection_policy import (
                StandardProtectionPolicy,
            )
            from pypdfbox.pdmodel.encryption.standard_security_handler import (
                StandardSecurityHandler,
            )

            if not isinstance(protection_policy, StandardProtectionPolicy):
                raise NotImplementedError(
                    "COSWriter encryption: only StandardProtectionPolicy is "
                    "supported (public-key handler dispatch is deferred)"
                )
            # The standard handler derives the file-encryption key from
            # the file-id; ensure trailer carries one BEFORE prepare_document
            # synthesises /O, /U, etc. (otherwise it falls back to the
            # 16-zero-bytes fixture which won't survive a re-load).
            self._propagate_document_id(cos_document)
            handler = StandardSecurityHandler(protection_policy)
            handler.prepare_document(pd_document)
            # Cache the handler back on the PDDocument so subsequent
            # ``decrypt()`` / ``get_current_access_permission()`` calls see
            # an active handler immediately after save.
            pd_document._security_handler = handler  # noqa: SLF001
            self._security_handler = handler
            return

        # Path 3: re-save of an already-decrypted encrypted document.
        existing_handler = getattr(pd_document, "_security_handler", None)
        if existing_handler is not None and pd_document.is_encrypted():
            self._security_handler = existing_handler

    def _propagate_document_id(self, cos_document: COSDocument) -> None:
        """Ensure the trailer carries an /ID before the handler's key
        derivation runs. Fresh documents get a random 16-byte identifier;
        loaded documents keep their existing /ID intact."""
        trailer = cos_document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            cos_document.set_trailer(trailer)
        existing = trailer.get_dictionary_object(_ID_NAME)
        if isinstance(existing, COSArray) and existing.size() == 2:
            return
        # Generate a fresh 16-byte file identifier per ISO 32000-1 §14.4.
        # Both halves of the /ID array start identical for a brand-new
        # document — they only diverge when the file is later updated.
        id_bytes = secrets.token_bytes(16)
        first = COSString(id_bytes)
        first.set_force_hex_form(True)
        second = COSString(id_bytes)
        second.set_force_hex_form(True)
        new_arr = COSArray([first, second])
        new_arr.set_direct(True)
        trailer.set_item(_ID_NAME, new_arr)

    def _refresh_encrypt_dict_id(self, cos_document: COSDocument) -> None:
        """Capture the identity of the /Encrypt dictionary so that strings
        encountered while serialising it are skipped by the encryption
        pipeline (per ISO 32000-1 §7.6.1, /Encrypt itself isn't encrypted)."""
        if self._security_handler is None:
            self._encrypt_dict_id = None
            return
        trailer = cos_document.get_trailer()
        if trailer is None:
            self._encrypt_dict_id = None
            return
        enc = trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
        if isinstance(enc, COSDictionary):
            self._encrypt_dict_id = id(enc)
        else:
            self._encrypt_dict_id = None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._standard_output.flush()
        # Don't close the underlying sink — the caller passed it in and is
        # responsible for its lifecycle. Mirrors PDFBox's behavior.

    def __enter__(self) -> COSWriter:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    # ---------- visitor: top-level orchestration ----------

    def visit_from_document(self, doc: COSDocument) -> Any:
        self._do_write_header(doc)
        self._do_write_body(doc)
        self._do_write_xref_table()
        self._do_write_trailer(doc)

        # startxref + EOF
        out = self._standard_output
        out.write(STARTXREF)
        out.write_eol()
        out.write_int(self._startxref)
        out.write_eol()
        out.write(EOF)
        out.write_eol()
        return None

    # ---------- incremental save ----------

    def _reject_signed_with_byterange_placeholder(self, doc: COSDocument) -> None:
        """Refuse to re-save a signed document while the security cluster's
        digest computation is still stubbed out.

        ISO 32000-1 §12.8 reserves a ``/ByteRange [0 0 0 0]`` placeholder
        inside the signature dict; touching the file without recomputing
        the digest invalidates the signature. We raise here rather than
        silently corrupt the signature."""
        for cos_obj in doc.get_objects():
            resolved = cos_obj.get_object()
            if not isinstance(resolved, COSDictionary):
                continue
            type_name = resolved.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
            if not isinstance(type_name, COSName):
                continue
            if type_name.name not in ("Sig", "DocTimeStamp"):
                continue
            byte_range = resolved.get_dictionary_object(
                COSName.get_pdf_name("ByteRange")
            )
            if not isinstance(byte_range, COSArray) or byte_range.size() != 4:
                continue
            # Upstream sniffs for ``br[2] > inputData.length()`` to detect
            # the placeholder. The canonical placeholder is ``[0 0 0 0]``;
            # any 4-int byterange whose third entry doesn't actually point
            # past the (signed) source's end is also a no-go for us until
            # the security cluster ports the digest pipeline.
            raise NotImplementedError(
                "re-signing with PDFBox-style ByteRange placeholders requires "
                "the security cluster"
            )

    def _do_write_increment(self, doc: COSDocument) -> None:
        """Append-only path: copy original bytes verbatim, then emit only
        the dirty objects + a fresh xref section chained via ``/Prev``.

        Mirrors ``COSWriter.doWriteIncrement`` + ``prepareIncrement`` +
        ``doWriteXRefInc`` upstream.
        """
        assert self._incremental_input is not None
        assert self._increment_buffer is not None

        source_length = self._incremental_input.length()

        # 1. ``prepareIncrement`` — register every existing key/actual so
        # references emitted from the dirty graph reuse the source's keys.
        self._prepare_increment(doc)

        # 2. Walk the dirty graph. Every COSObject in the pool whose
        # resolved actual is dirty becomes a candidate; we then promote
        # any directly-referenced dirty actuals.
        self._enqueue_dirty_objects(doc)

        if not self._objects_to_write:
            # Nothing to write — match upstream: no extra bytes appended,
            # output is byte-for-byte identical to the source.
            self._copy_source_to_output()
            return

        # 2.5 Whitespace separator so the appended bytes are unambiguously
        # delimited from the source's trailing ``%%EOF``. Mirrors upstream's
        # ``getStandardOutput().writeCRLF()`` at the top of
        # ``visitFromDocument`` in incremental mode. Goes through the
        # buffered stream so byte offsets stay consistent.
        out = self._standard_output
        out.write_crlf()

        # 3. Emit each indirect object's body. Offsets recorded by
        # ``_do_write_object`` are relative to the increment buffer, so we
        # compensate when writing the xref to make them absolute.
        self._do_write_objects()

        # 4. Emit the new xref section. Must include only the changed
        # objects + the mandatory free-list head (object 0).
        self._do_write_xref_increment(source_length)

        # 5. Emit the trailer with /Prev pointing at the prior startxref.
        self._do_write_trailer_increment(doc)

        # 6. startxref + %%EOF (offsets are absolute = source_length + buffer pos).
        out.write(STARTXREF)
        out.write_eol()
        out.write_int(source_length + self._startxref)
        out.write_eol()
        out.write(EOF)
        out.write_eol()

        # 7. Drain: copy source, then append increment.
        self._copy_source_to_output()
        increment = self._increment_buffer.getvalue()
        if increment:
            self._write_to_output(increment)

    def _prepare_increment(self, doc: COSDocument) -> None:
        """Populate ``object_keys`` / ``key_object`` from the source's
        object pool so that references emitted from dirty objects resolve
        to existing keys instead of minting fresh ones."""
        for key in doc.get_object_keys():
            cos_obj = doc.get_object_from_pool(key)
            actual = cos_obj.get_object()
            if actual is None:
                continue
            self._object_keys[id(actual)] = key
            self._key_holders[id(actual)] = actual
            self._key_object[key] = actual
            # Record the COSObject wrapper too (so a dictionary holding
            # the wrapper as an indirect-reference value resolves cleanly).
            self._object_keys[id(cos_obj)] = key
            self._key_holders[id(cos_obj)] = cos_obj

    def _enqueue_dirty_objects(self, doc: COSDocument) -> None:
        """Queue every indirect object in the pool whose resolved value is
        marked ``needs_to_be_updated``."""
        for cos_obj in doc.get_objects():
            actual = cos_obj.get_object()
            if actual is None:
                continue
            if actual.is_needs_to_be_updated() or cos_obj.is_needs_to_be_updated():
                self._add_object_to_write(cos_obj)

    def _do_write_xref_increment(self, source_length: int) -> None:
        """Emit the new xref section. Subsections cover only the changed /
        new objects plus the mandatory free-list head."""
        out = self._standard_output

        # Always include the free-list head (object 0). Upstream calls this
        # ``addXRefEntry(FreeXReference.NULL_ENTRY)``.
        self._xref_entries.append(COSWriterXRefEntry.get_null_entry())

        entries = sorted(self._xref_entries)
        # Record startxref relative to the increment buffer (we add
        # source_length back when writing the trailer / startxref line).
        self._startxref = out.get_position()

        out.write(XREF)
        out.write_eol()

        for first, count in self._build_ranges(entries):
            self._write_xref_range(first, count)
            for entry in entries:
                if first <= entry.key.object_number < first + count:
                    self._write_xref_entry_incremental(entry, source_length)

    def _write_xref_entry_incremental(
        self, entry: COSWriterXRefEntry, source_length: int
    ) -> None:
        """Same wire format as the full-save xref entry, but offsets are
        rebased to absolute (= source_length + offset-in-buffer)."""
        out = self._standard_output
        absolute = entry.offset + source_length if not entry.free else entry.offset
        out.write(_format_xref_offset(absolute))
        out.write(SPACE)
        out.write(_format_xref_generation(entry.key.generation_number))
        out.write(SPACE)
        out.write(XREF_FREE if entry.free else XREF_USED)
        out.write_crlf()

    def _do_write_trailer_increment(self, doc: COSDocument) -> None:
        """Emit the appended trailer: copy source trailer, set /Prev to
        the previous startxref, set /Size to max_obj_num + 1, preserve /ID."""
        out = self._standard_output
        out.write(TRAILER)
        out.write_eol()

        source_trailer = doc.get_trailer()
        # Build a fresh trailer dict mirroring the source's keys but with
        # /Prev re-targeted and /Size updated. We mutate a copy so the
        # in-memory document is left untouched.
        trailer = COSDictionary()
        if source_trailer is not None:
            for k, v in source_trailer.entry_set():
                trailer.set_item(k, v)

        # /Prev → previous startxref. Defaults to 0 for synthesised
        # documents — matches upstream which still writes /Prev even if
        # the original document had none.
        trailer.set_int(COSName.PREV, doc.get_start_xref())  # type: ignore[attr-defined]

        # /Size = max(known_keys) + 1, accounting for both source keys and
        # any newly-minted keys for fresh objects.
        all_keys = set(doc.get_object_keys())
        all_keys.update(self._key_object.keys())
        highest = max((k.object_number for k in all_keys), default=0)
        trailer.set_int(COSName.SIZE, highest + 1)  # type: ignore[attr-defined]

        # /ID array stays direct (must round-trip inline per spec §14.4).
        id_arr = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if isinstance(id_arr, COSArray):
            id_arr.set_direct(True)

        # Other ephemeral keys upstream strips before re-emit.
        trailer.remove_item(COSName.get_pdf_name("DocChecksum"))
        trailer.remove_item(COSName.get_pdf_name("XRefStm"))

        trailer.accept(self)

    def _copy_source_to_output(self) -> None:
        """Stream the original file bytes through to the real output sink
        verbatim. Mirrors ``IOUtils.copy(input, incrementalOutput)``."""
        assert self._incremental_input is not None
        src = self._incremental_input
        src.seek(0)
        # Read in chunks to avoid materialising the entire source at once.
        chunk = bytearray(64 * 1024)
        while True:
            n = src.read_into(chunk, 0, len(chunk))
            if n <= 0:
                break
            self._write_to_output(bytes(chunk[:n]))

    def _write_to_output(self, data: bytes) -> None:
        """Write directly to the real output sink (bypasses the increment
        buffer). Used for streaming the source copy and the final flush."""
        if isinstance(self._output, RandomAccessWrite):
            self._output.write_bytes(data)
        else:
            self._output.write(data)

    # ---------- header ----------

    def _do_write_header(self, doc: COSDocument) -> None:
        out = self._standard_output
        version_text = self._format_version(doc.get_version())
        out.write(f"%PDF-{version_text}".encode("iso-8859-1"))
        out.write_eol()
        out.write(COMMENT)
        out.write(GARBAGE)
        out.write_eol()

    @staticmethod
    def _format_version(version: float) -> str:
        # Match upstream Java's ``Float.toString`` output for canonical PDF
        # versions: 1.4 → "1.4", 2.0 → "2.0". Avoid scientific notation.
        if version == int(version):
            return f"{int(version)}.0"
        # For typical PDF versions (1.0..2.0) one decimal place is enough.
        text = f"{version:.6g}"
        # ``%g`` may return "1.4" or "1.45" — both fine. Just strip any
        # accidental trailing zeros in the fraction beyond a single digit.
        return text

    # ---------- body ----------

    def _do_write_body(self, doc: COSDocument) -> None:
        trailer = doc.get_trailer()
        if trailer is not None:
            root = trailer.get_item(COSName.ROOT)  # type: ignore[attr-defined]
            info = trailer.get_item(COSName.INFO)  # type: ignore[attr-defined]
            encrypt = trailer.get_item(COSName.ENCRYPT)  # type: ignore[attr-defined]
            if root is not None:
                self._add_object_to_write(root)
            if info is not None:
                self._add_object_to_write(info)
            self._do_write_objects()
            if encrypt is not None:
                self._add_object_to_write(encrypt)
            self._do_write_objects()
        else:
            # No trailer — still drain any pre-seeded queue.
            self._do_write_objects()

    def _do_write_objects(self) -> None:
        while self._objects_to_write:
            obj = self._objects_to_write.popleft()
            self._do_write_object(obj)

    def _add_object_to_write(self, obj: COSBase) -> None:
        actual: COSBase | None = obj
        if isinstance(obj, COSObject):
            actual = obj.get_object()

        # Already written / already queued / its actual already accounted.
        if id(obj) in self._written_objects:
            return
        if actual is not None and id(actual) in self._actuals_added:
            return
        if any(o is obj for o in self._objects_to_write):
            return

        # In **incremental** mode upstream filters out un-dirtied objects
        # here so that traversal of a dirty dictionary doesn't drag every
        # transitively-referenced object back into the appended xref. The
        # check honours both ``obj`` and the resolved ``actual`` (matches
        # ``isNeedToBeUpdated(object) || isNeedToBeUpdated(cosBase)``).
        if self._incremental_update:
            obj_dirty = obj.is_needs_to_be_updated()
            actual_dirty = (
                actual is not None and actual.is_needs_to_be_updated()
            )
            if not (obj_dirty or actual_dirty):
                return
        else:
            # In full-save mode, an actual that already has a key has
            # already been queued under its first sighting — skip the
            # duplicate.
            if actual is not None and id(actual) in self._object_keys:
                return

        self._objects_to_write.append(obj)
        if actual is not None:
            self._actuals_added.add(id(actual))

    def _do_write_object(self, obj: COSBase) -> None:
        # Skip dangling references (matches upstream).
        if isinstance(obj, COSObject) and obj.get_object() is None:
            return
        self._written_objects.add(id(obj))
        key = self._get_object_key(obj)
        self._current_object_key = key
        # Detect whether this indirect object IS the /Encrypt dictionary so
        # the leaf visitors can suppress string encryption while we serialise
        # it (per ISO 32000-1 §7.6.1, the /Encrypt dict is never enciphered).
        actual = obj.get_object() if isinstance(obj, COSObject) else obj
        previous_in_encrypt = self._in_encrypt_subtree
        if (
            self._encrypt_dict_id is not None
            and actual is not None
            and id(actual) == self._encrypt_dict_id
        ):
            self._in_encrypt_subtree = True
        try:
            self._do_write_object_with_key(key, obj)
        finally:
            self._in_encrypt_subtree = previous_in_encrypt
            # Clear the current key once this indirect object is done so
            # any subsequent emit (xref, trailer) sees ``None`` and skips
            # the encryption pipeline. Otherwise stray strings in the
            # trailer (notably /ID) would be enciphered.
            self._current_object_key = None

    def _do_write_object_with_key(self, key: COSObjectKey, obj: COSBase) -> None:
        out = self._standard_output
        # Record the xref entry with this object's start offset.
        self._xref_entries.append(
            COSWriterXRefEntry(offset=out.get_position(), key=key, obj=obj, free=False)
        )

        out.write_int(key.object_number)
        out.write(SPACE)
        out.write_int(key.generation_number)
        out.write(SPACE)
        out.write(OBJ)
        out.write_eol()

        # Emit the value. If ``obj`` is a COSObject, dereference and emit
        # the target inline (the indirect frame is the object frame).
        target: COSBase | None = obj.get_object() if isinstance(obj, COSObject) else obj
        if target is None:
            COSNull.NULL.accept(self)
        else:
            target.accept(self)

        out.write_eol()
        out.write(ENDOBJ)
        out.write_eol()

    # ---------- key assignment ----------

    def _get_object_key(self, obj: COSBase) -> COSObjectKey:
        """Return (and lazily assign) the indirect-object key for ``obj``.

        For a ``COSObject`` we use its declared ``(num, gen)`` if present;
        otherwise we mint a new key. The resolved actual is also tracked
        so dictionaries that hold the same target reuse the same key.
        """
        actual: COSBase
        if isinstance(obj, COSObject):
            resolved = obj.get_object()
            if resolved is None:
                # Dangling reference; preserve the declared key.
                key = COSObjectKey(obj.get_object_number(), obj.get_generation_number())
                self._object_keys[id(obj)] = key
                self._key_holders[id(obj)] = obj
                return key
            actual = resolved
            declared_key = COSObjectKey(
                obj.get_object_number(), obj.get_generation_number()
            )
        else:
            actual = obj
            declared_key = None

        existing = self._object_keys.get(id(actual))
        if existing is not None:
            if isinstance(obj, COSObject):
                self._object_keys[id(obj)] = existing
                self._key_holders[id(obj)] = obj
            return existing

        if declared_key is not None and declared_key.object_number > 0:
            key = declared_key
        else:
            self._number += 1
            key = COSObjectKey(self._number, 0)

        # Avoid number collisions when minting fresh keys: bump if the
        # generated number is already in use under a different actual.
        while key in self._key_object and self._key_object[key] is not actual:
            self._number += 1
            key = COSObjectKey(self._number, 0)

        self._object_keys[id(actual)] = key
        self._key_holders[id(actual)] = actual
        self._key_object[key] = actual
        if isinstance(obj, COSObject):
            self._object_keys[id(obj)] = key
            self._key_holders[id(obj)] = obj
        return key

    # ---------- xref ----------

    def _do_write_xref_table(self) -> None:
        out = self._standard_output

        # Always include a free entry at object 0 (offset 0, gen 65535).
        # The upstream "fillGapsWithFreeEntries" path accounts for cases
        # where mid-numbers are missing; for cluster #1 we mirror its
        # simple branch (no normal entries with object 0 → emit NULL_ENTRY).
        self._fill_gaps_with_free_entries()

        entries = sorted(self._xref_entries)
        self._startxref = out.get_position()

        out.write(XREF)
        out.write_eol()

        for first, count in self._build_ranges(entries):
            self._write_xref_range(first, count)
            for entry in entries:
                if first <= entry.key.object_number < first + count:
                    self._write_xref_entry(entry)

    def _fill_gaps_with_free_entries(self) -> None:
        # Collect normal entries (matches upstream's ``NormalXReference``
        # filter — for cluster #1 every recorded entry is "normal").
        normals = sorted(
            (e for e in self._xref_entries if not e.free),
            key=lambda e: e.key.object_number,
        )
        last = 0
        free_numbers: list[int] = []
        for entry in normals:
            nr = entry.key.object_number
            if nr != last:
                for i in range(last, nr):
                    free_numbers.append(i)
            last = nr + 1
        if not free_numbers:
            self._xref_entries.append(COSWriterXRefEntry.get_null_entry())
            return
        for i in range(len(free_numbers) - 1):
            self._xref_entries.append(
                COSWriterXRefEntry(
                    offset=free_numbers[i + 1],
                    key=COSObjectKey(free_numbers[i], 65535),
                    obj=None,
                    free=True,
                )
            )
        # Tail entry: points back at object 0 as next free.
        self._xref_entries.append(
            COSWriterXRefEntry(
                offset=0,
                key=COSObjectKey(free_numbers[-1], 65535),
                obj=None,
                free=True,
            )
        )
        # If object 0 wasn't already a gap, prepend a free entry pointing at
        # the first gap so the free-list head exists.
        if free_numbers[0] > 0:
            self._xref_entries.append(
                COSWriterXRefEntry(
                    offset=free_numbers[0],
                    key=COSObjectKey(0, 65535),
                    obj=None,
                    free=True,
                )
            )

    @staticmethod
    def _build_ranges(entries: list[COSWriterXRefEntry]) -> list[tuple[int, int]]:
        """Group sorted entries into contiguous ``(first, count)`` runs."""
        ranges: list[tuple[int, int]] = []
        if not entries:
            return ranges
        first = entries[0].key.object_number
        count = 1
        for prev, cur in zip(entries, entries[1:], strict=False):
            if cur.key.object_number == prev.key.object_number + 1:
                count += 1
            else:
                ranges.append((first, count))
                first = cur.key.object_number
                count = 1
        ranges.append((first, count))
        return ranges

    def _write_xref_range(self, first: int, count: int) -> None:
        out = self._standard_output
        out.write_int(first)
        out.write(SPACE)
        out.write_int(count)
        out.write_eol()

    def _write_xref_entry(self, entry: COSWriterXRefEntry) -> None:
        out = self._standard_output
        out.write(_format_xref_offset(entry.offset))
        out.write(SPACE)
        out.write(_format_xref_generation(entry.key.generation_number))
        out.write(SPACE)
        out.write(XREF_FREE if entry.free else XREF_USED)
        # Each xref entry must end with a 2-byte EOL so the row is exactly
        # 20 bytes — ISO 32000-1 §7.5.4.
        out.write_crlf()

    # ---------- trailer ----------

    def _do_write_trailer(self, doc: COSDocument) -> None:
        out = self._standard_output
        out.write(TRAILER)
        out.write_eol()

        trailer = doc.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
        # /Size = highest object number + 1. Pulled from sorted xref entries.
        if self._xref_entries:
            highest = max(e.key.object_number for e in self._xref_entries)
            trailer.set_int(COSName.SIZE, highest + 1)  # type: ignore[attr-defined]
        else:
            trailer.set_int(COSName.SIZE, 1)  # type: ignore[attr-defined]
        # Cluster #1 is full-save; clear /Prev so we don't claim incremental.
        trailer.remove_item(COSName.PREV)  # type: ignore[attr-defined]

        # /ID array must be emitted inline (PDF spec calls it a direct array).
        id_arr = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if isinstance(id_arr, COSArray):
            id_arr.set_direct(True)

        trailer.accept(self)

    # ---------- /ID generation ----------

    def _ensure_document_id(self, doc: COSDocument) -> None:
        """If trailer lacks an /ID array (or it's malformed), generate one
        — mirrors upstream's SHA-256-based ID synthesis. Result format is
        ``[<id1> <id2>]`` per ISO 32000-1 §14.4."""
        trailer = doc.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            doc.set_trailer(trailer)
        existing = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if isinstance(existing, COSArray) and existing.size() == 2:
            return
        # Generate two 16-byte halves. Upstream uses SHA-256 over time +
        # info-dict; we use a SHA-256 over a wall-clock seed plus a random
        # nonce for reproducibility-of-shape (not value).
        seed = f"{time.time_ns()}".encode("ascii") + secrets.token_bytes(16)
        digest = hashlib.sha256(seed).digest()[:16]
        first = COSString(digest)
        first.set_force_hex_form(True)
        second = COSString(digest)
        second.set_force_hex_form(True)
        new_arr = COSArray([first, second])
        new_arr.set_direct(True)
        trailer.set_item(COSName.get_pdf_name("ID"), new_arr)

    # ---------- visitor: leaves ----------

    def visit_from_boolean(self, obj: COSBoolean) -> Any:
        self._standard_output.write(b"true" if obj.get_value() else b"false")
        return None

    def visit_from_null(self, obj: COSNull) -> Any:
        self._standard_output.write(b"null")
        return None

    def visit_from_integer(self, obj: COSInteger) -> Any:
        self._standard_output.write(str(obj.value).encode("ascii"))
        return None

    def visit_from_float(self, obj: COSFloat) -> Any:
        self._standard_output.write(self.format_float_value(obj))
        return None

    def visit_from_name(self, obj: COSName) -> Any:
        out = self._standard_output
        out.write(b"/")
        for b in obj.get_name().encode("utf-8"):
            if _is_printable_name_byte(b):
                out.write_byte(b)
            else:
                out.write(b"#")
                out.write(f"{b:02X}".encode("ascii"))
        return None

    def visit_from_string(self, obj: COSString) -> Any:
        # Encryption pipeline: when we have an active handler AND this string
        # lives inside an indirect object (so we have a (num, gen) to bind
        # to the per-object key), encipher its bytes before writing.
        # Strings inside the /Encrypt dictionary itself stay cleartext
        # (would be circular), as do strings inside the trailer (no
        # indirect key — covers /ID transparently).
        if (
            self._security_handler is not None
            and self._current_object_key is not None
            and not self._in_encrypt_subtree
        ):
            cipher_bytes = self._security_handler.encrypt_string(
                obj.get_bytes(),
                self._current_object_key.object_number,
                self._current_object_key.generation_number,
            )
            # Wrap the ciphertext in a fresh COSString so we don't mutate
            # the in-memory object — re-saves should still work. Force hex
            # form because the AES output is binary and would otherwise
            # require literal-form escaping.
            cipher_string = COSString(cipher_bytes)
            cipher_string.set_force_hex_form(True)
            self.write_string(cipher_string, self._standard_output)
            return None
        self.write_string(obj, self._standard_output)
        return None

    # ---------- visitor: containers ----------

    def visit_from_array(self, obj: COSArray) -> Any:
        out = self._standard_output
        out.write(ARRAY_OPEN)
        items = list(obj)
        for i, current in enumerate(items):
            if isinstance(current, COSDictionary):
                self._write_dictionary(current)
            elif isinstance(current, COSArray):
                self._write_array(current)
            elif isinstance(current, COSObject):
                self._add_object_to_write(current)
                self._write_reference(current)
            elif current is None:
                COSNull.NULL.accept(self)
            else:
                current.accept(self)
            if i < len(items) - 1:
                # Match upstream: every 10th item gets an EOL instead of a
                # space (helps pretty-printing without breaking parsers).
                if (i + 1) % 10 == 0:
                    out.write_eol()
                else:
                    out.write(SPACE)
        out.write(ARRAY_CLOSE)
        out.write_eol()
        return None

    def _write_array(self, array: COSArray) -> None:
        if array.is_direct():
            self.visit_from_array(array)
        else:
            self._add_object_to_write(array)
            self._write_reference(array)

    def _write_dictionary(self, dictionary: COSDictionary) -> None:
        if dictionary.is_direct():
            self.visit_from_dictionary(dictionary)
        else:
            self._add_object_to_write(dictionary)
            self._write_reference(dictionary)

    def visit_from_dictionary(self, obj: COSDictionary) -> Any:
        out = self._standard_output
        out.write(DICT_OPEN)
        out.write_eol()
        for key, value in obj.entry_set():
            if value is None:
                continue
            key.accept(self)
            out.write(SPACE)
            if isinstance(value, COSDictionary):
                self._write_dictionary(value)
            elif isinstance(value, COSObject):
                self._add_object_to_write(value)
                self._write_reference(value)
            elif isinstance(value, COSArray):
                self._write_array(value)
            else:
                value.accept(self)
            out.write_eol()
        out.write(DICT_CLOSE)
        out.write_eol()
        return None

    # ---------- visitor: stream ----------

    def visit_from_stream(self, obj: COSStream) -> Any:
        out = self._standard_output

        # Snapshot raw bytes (already filter-encoded, per parser cluster).
        if obj.has_data():
            with obj.create_raw_input_stream() as src:
                raw = src.read()
        else:
            raw = b""

        # Encryption pipeline: when an active handler is wired AND this
        # stream is being emitted as an indirect object (which is always
        # the case for streams — they cannot be direct), encrypt the body
        # using the per-object key. Streams inside the /Encrypt subtree
        # (none in practice, but guard anyway) stay cleartext.
        if (
            self._security_handler is not None
            and self._current_object_key is not None
            and not self._in_encrypt_subtree
        ):
            raw = self._security_handler.encrypt_stream(
                raw,
                self._current_object_key.object_number,
                self._current_object_key.generation_number,
            )

        # Update /Length to match what we'll actually emit. Streams are
        # always indirect, so this is safe.
        obj.set_int(COSName.LENGTH, len(raw))  # type: ignore[attr-defined]

        # Emit the dictionary first.
        self.visit_from_dictionary(obj)

        out.write(STREAM)
        out.write_crlf()
        if raw:
            out.write(raw)
        out.write_crlf()
        out.write(ENDSTREAM)
        out.write_eol()
        return None

    # ---------- visitor: indirect ref ----------

    def visit_from_object(self, obj: COSObject) -> Any:
        # Visited at top level (i.e., from ``_do_write_object``): the
        # indirect frame is already open, just emit the target's value.
        target = obj.get_object()
        if target is None:
            COSNull.NULL.accept(self)
        else:
            target.accept(self)
        return None

    def _write_reference(self, obj: COSBase) -> None:
        out = self._standard_output
        key = self._get_object_key(obj)
        out.write_int(key.object_number)
        out.write(SPACE)
        out.write_int(key.generation_number)
        out.write(SPACE)
        out.write(REFERENCE)

    # ---------- statics: number / string formatting ----------

    @staticmethod
    def format_float(value: float) -> bytes:
        """Format a float for PDF output. Mirrors upstream's
        ``COSFloat.formatString`` — avoid scientific notation, strip
        trailing zeros that arise from ``BigDecimal`` round-trip."""
        if value != value:  # NaN guard — PDFs cannot encode NaN.
            raise ValueError("cannot serialize NaN as a PDF number")
        # Use ``repr``-like form when the magnitude doesn't push into
        # exponential territory; else strip trailing zeros via the same
        # logic PDFBox applies.
        text = format(value, ".10g")
        if "e" in text or "E" in text:
            # Fall back to a non-scientific representation. ``f`` would pad
            # with zeros, but stripping mimics ``BigDecimal.stripTrailingZeros``.
            text = format(value, ".15f").rstrip("0").rstrip(".")
            if not text or text == "-":
                text = "0"
        return text.encode("iso-8859-1")

    @staticmethod
    def format_float_value(obj: COSFloat) -> bytes:
        """Prefer the original parsed text (round-trip fidelity) when set;
        else fall back to ``format_float``."""
        original = obj.get_original_form()
        if original is not None:
            return original.encode("iso-8859-1")
        return COSWriter.format_float(obj.value)

    @staticmethod
    def write_string(string: COSString, output: COSStandardOutputStream) -> None:
        """Serialize ``string`` as either a literal ``(...)`` or hex
        ``<...>`` PDF string. Matches upstream ``COSWriter.writeString``."""
        data = string.get_bytes()
        force_hex = string.is_force_hex_form()
        is_ascii = True
        if not force_hex:
            for b in data:
                # bytes >= 0x80 → non-ASCII; also avoid CR/LF to dodge EOL
                # ambiguity inside literal strings (PDFBOX-3107).
                if b >= 0x80 or b in (0x0D, 0x0A):
                    is_ascii = False
                    break
        if is_ascii and not force_hex:
            output.write(b"(")
            for b in data:
                if b in (0x28, 0x29, 0x5C):  # ( ) \
                    output.write(b"\\")
                    output.write_byte(b)
                else:
                    output.write_byte(b)
            output.write(b")")
        else:
            output.write(b"<")
            output.write(data.hex().upper().encode("ascii"))
            output.write(b">")


