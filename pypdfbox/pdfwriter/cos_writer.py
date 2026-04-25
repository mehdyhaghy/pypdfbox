from __future__ import annotations

import hashlib
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
from pypdfbox.io import RandomAccessWrite

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
    ) -> None:
        if incremental:
            raise NotImplementedError("incremental save lands in cluster #2")
        self._output = output
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

    # ---------- public API ----------

    def get_standard_output(self) -> COSStandardOutputStream:
        return self._standard_output

    def get_startxref(self) -> int:
        return self._startxref

    def get_xref_entries(self) -> list[COSWriterXRefEntry]:
        return self._xref_entries

    def write(self, document: COSDocument) -> None:
        """Emit ``document`` end-to-end as a self-contained PDF.

        ``PDDocument`` is not yet ported (see PRD §6.6); for now callers
        pass a ``COSDocument`` directly — matches upstream's
        ``write(COSDocument)`` overload that wraps ``new PDDocument(doc)``.
        """
        if self._closed:
            raise ValueError("operation on closed COSWriter")
        if not isinstance(document, COSDocument):
            raise TypeError(
                "COSWriter.write expects a pypdfbox.cos.COSDocument; PDDocument "
                "is not yet ported (PRD §6.6)."
            )
        if document.is_encrypted():
            raise NotImplementedError(
                "writing encrypted documents lands with the security cluster"
            )

        # Seed numbering from the highest existing object number so we
        # don't reuse keys when the parser already loaded them.
        existing_keys = document.get_object_keys()
        self._number = max((k.object_number for k in existing_keys), default=0)

        self._ensure_document_id(document)
        document.accept(self)

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
        # If we already have a key for the actual, this is a duplicate — skip.
        if actual is not None and id(actual) in self._object_keys:
            # Different ``obj`` (e.g., a fresh COSObject wrapping the same
            # actual) but the actual will already be emitted under its
            # registered key.
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
        self._do_write_object_with_key(key, obj)

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


