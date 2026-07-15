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
from pypdfbox.cos.cos_float import format_float32
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

from .compress.compress_parameters import CompressParameters
from .cos_standard_output_stream import COSStandardOutputStream
from .cos_writer_xref_entry import COSWriterXRefEntry

# Sentinel name objects used to filter the /Encrypt and /ID entries out of the
# encryption pipeline. Hoisted to module scope so we don't recompute on every
# leaf visit. ISO 32000-1 §7.6.1: the /Encrypt dictionary itself is never
# encrypted (would be circular), and the file identifier /ID array is the
# trailer-level handle the handler keys off of — encrypting it would make the
# document undecryptable.
_ID_NAME: COSName = COSName.get_pdf_name("ID")
_FLATE_DECODE_NAME: COSName = COSName.get_pdf_name("FlateDecode")
_VERSION_NAME: COSName = COSName.get_pdf_name("Version")

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
# Default ``%PDF-x.y`` marker (PDF 32000-1 §7.5.2). Mirrors upstream
# ``COSWriter.VERSION`` byte literal — exposed as a module-level constant
# so PDFBox-style callers can refer to it under the same name.
VERSION: bytes = b"PDF-1.4"
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


def _format_xref_table_offset(offset: int) -> bytes:
    """Return a 10-byte xref-table offset or reject an unrepresentable one."""
    formatted = _format_xref_offset(offset)
    if len(formatted) != 10:
        raise ValueError(
            "xref table offsets must fit in 10 decimal digits; "
            f"got {offset}"
        )
    return formatted


def _format_xref_table_generation(gen: int) -> bytes:
    """Return a 5-byte xref-table generation or reject an invalid one."""
    if gen < 0 or gen > 65535:
        raise ValueError(f"generation must be in [0, 65535]; got {gen}")
    return _format_xref_generation(gen)


# Per PDF 32000-1 §7.5.7 readers parse ObjStm index headers sequentially,
# so PDFBox bounds each packed stream via CompressParameters. Mirror the
# default here for the writer's opt-in object-stream path.
_OBJSTM_DEFAULT_MAX: int = CompressParameters.DEFAULT_OBJECT_STREAM_SIZE


def _ceil_log256(value: int) -> int:
    """Number of bytes needed to encode ``value`` as an unsigned big-endian
    integer. Used for the ``/W`` field widths in xref streams.

    ``_ceil_log256(0) == 1`` — matches the spec's "minimum 1 byte" rule."""
    if value <= 0:
        return 1
    width = 0
    v = value
    while v > 0:
        v >>= 8
        width += 1
    return width


def _xref_field_width(max_value: int) -> int:
    """Byte width of an xref-stream ``/W`` field, mirroring
    ``PDFXRefStream.getWEntry`` (PDFBox 3.0.7,
    ``org.apache.pdfbox.pdfparser.PDFXRefStream``): the width is how many
    bytes the column's MAX value needs, and a max of 0 yields width **0**
    (not the spec-minimum 1). PDFBox's ``writeNumber`` then emits zero bytes
    for that column, so e.g. an offset-only increment whose generations are
    all 0 produces ``/W [1 3 0]``. This deliberately differs from
    :func:`_ceil_log256` (which clamps to a minimum of 1)."""
    width = 0
    v = max_value
    while v > 0:
        v >>= 8
        width += 1
    return width


def _pack_unsigned(value: int, width: int) -> bytes:
    """Big-endian unsigned int encoded in exactly ``width`` bytes. Raises
    ``ValueError`` if ``value`` doesn't fit — ISO 32000-1 §7.5.8.3 says
    field widths must be sized so this never happens, so a fit failure
    indicates a writer bug rather than user input.

    A ``width`` of 0 emits no bytes (PDFBox ``PDFXRefStream.writeNumber``
    writes ``length`` bytes high-to-low, so a 0-width column produces an
    empty field — the value is simply dropped, matching a ``/W`` entry of
    0)."""
    if value < 0:
        raise ValueError(f"xref stream field cannot be negative: {value}")
    if width < 0:
        raise ValueError(f"xref stream field width must be non-negative: {width}")
    if width == 0:
        return b""
    return int(value).to_bytes(width, "big", signed=False)


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


# Scalar COS types whose pool membership is by VALUE-EQUALITY, not identity.
# Upstream ``COSObjectPool`` keeps a ``HashMap<COSBase, COSObjectKey>``; for
# these types ``COSBase.equals`` / ``hashCode`` are value-based (COSString,
# COSInteger, COSFloat, COSName, COSBoolean all override them), while
# COSDictionary / COSArray / COSStream fall back to identity. So when a packed
# container holds a *direct* scalar that is value-equal to an already-registered
# *indirect* scalar, upstream emits a reference to that indirect rather than
# inlining the value (``COSWriterObjectStream.writeObject`` →
# ``compressionPool.contains(base)`` → ``objectPool.containsKey(base)``).
_VALUE_KEYED_POOL_TYPES: tuple[type, ...] = (
    COSString,
    COSInteger,
    COSFloat,
    COSName,
    COSBoolean,
)


class _ObjStmPoolShim:
    """Adapt ``COSWriter``'s key tables to the ``contains`` / ``get_key``
    surface :class:`COSWriterObjectStream` expects from a
    ``COSWriterCompressionPool``.

    When serialising a packed object's body, any nested indirect object must
    be written as an ``N G R`` reference rather than inlined. The object-stream
    writer asks the pool whether a base is a known indirect (``contains``) and,
    if so, for its key (``get_key``). We answer from the writer's
    ``id(obj) -> COSObjectKey`` map, which the compression pre-pass has already
    populated for every reachable indirect object.

    Containers (dict / array / stream) match by identity (``id``), exactly like
    upstream's HashMap on a type that does not override ``equals``. Scalar
    values (string / integer / float / name / boolean) additionally match by
    VALUE-EQUALITY through ``value_pool``: a direct scalar that is value-equal
    to an indirect scalar already registered in the pool resolves to that
    indirect's key, so it is emitted as ``N G R`` rather than inlined — mirroring
    upstream ``COSObjectPool.objectPool.containsKey`` on a value-hashed
    ``COSBase`` (``acroform.pdf`` object 77's ``[(BMW) 75 0 R (VW) (Audi)]``).
    """

    def __init__(
        self,
        object_keys: dict[int, COSObjectKey],
        value_pool: dict[COSBase, COSObjectKey] | None = None,
    ) -> None:
        self._object_keys = object_keys
        # ``value_pool`` is keyed by the scalar COSBase itself; since these
        # types are value-hashable, dict lookup performs value-equality (the
        # Python analogue of upstream's ``HashMap<COSBase, COSObjectKey>``).
        self._value_pool: dict[COSBase, COSObjectKey] = (
            value_pool if value_pool is not None else {}
        )

    def contains(self, obj: COSBase) -> bool:
        if id(obj) in self._object_keys:
            return True
        if isinstance(obj, _VALUE_KEYED_POOL_TYPES):
            return obj in self._value_pool
        return False

    def get_key(self, obj: COSBase) -> COSObjectKey | None:
        key = self._object_keys.get(id(obj))
        if key is not None:
            return key
        if isinstance(obj, _VALUE_KEYED_POOL_TYPES):
            return self._value_pool.get(obj)
        return None


class _WriteQueue(deque):
    """FIFO of objects awaiting their indirect-object frame, carrying a
    parallel ``id()`` set (:attr:`ids`) so the duplicate-enqueue guard in
    ``COSWriter._add_object_to_write`` is O(1) instead of an O(queue) ``is``
    scan (the latter cost ~74% of a 4000-page uncompressed save).

    The set is kept in lockstep by overriding every mutator the writer uses.
    Objects in the queue are strongly referenced by the deque, so their
    ``id()`` cannot be recycled while queued — the set faithfully mirrors
    membership. (Each object is enqueued at most once thanks to the guard, so
    the set needs no multiplicity bookkeeping.)
    """

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[int] = set()

    def append(self, obj: COSBase) -> None:  # type: ignore[override]
        super().append(obj)
        self.ids.add(id(obj))

    def appendleft(self, obj: COSBase) -> None:  # type: ignore[override]
        super().appendleft(obj)
        self.ids.add(id(obj))

    def popleft(self) -> COSBase:  # type: ignore[override]
        obj = super().popleft()
        self.ids.discard(id(obj))
        return obj

    def pop(self) -> COSBase:  # type: ignore[override]
        obj = super().pop()
        self.ids.discard(id(obj))
        return obj

    def clear(self) -> None:
        super().clear()
        self.ids.clear()


class COSWriter(ICOSVisitor):
    """
    Serialize a ``COSDocument`` or ``PDDocument`` back to PDF bytes.

    Mirrors ``org.apache.pdfbox.pdfwriter.COSWriter`` for the writer paths
    ported here: full saves, incremental appends, traditional xref tables,
    xref streams, hybrid xrefs, object streams, and standard encryption
    handoff from ``PDDocument``. Writer-level signature plumbing remains a
    placeholder; high-level signing is coordinated by ``PDDocument``.

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
        xref_stream: bool = False,
        object_stream: bool = False,
        object_stream_size: int | None = None,
        hybrid_xref: bool = False,
        allow_signing_placeholders: bool = False,
        fdf: bool = False,
    ) -> None:
        self._output = output
        self._incremental_update = incremental
        # When True, emit an ``%FDF-x.y`` header instead of ``%PDF-x.y``.
        # Mirrors upstream COSWriter, whose ``doWriteHeader`` switches the
        # header marker based on whether an ``fdfDocument`` was passed to
        # ``write(FDFDocument)``. FDFParser rejects a ``%PDF-`` header
        # ("Error: Header doesn't contain versioninfo"), so an FDF saved
        # with the PDF marker cannot be reloaded by PDFBox.
        self._fdf: bool = fdf
        self._incremental_input = incremental_input
        # When True, skip the safety guard that normally rejects re-saving a
        # source-side signature with a ``[0 0 0 0]`` ByteRange placeholder.
        # The signing pipeline (``PDDocument.add_signature`` /
        # ``save_incremental_for_external_signing``) sets this because it owns
        # the placeholder + post-write splice and will compute the digest
        # itself; everyone else stays protected.
        self._allow_signing_placeholders: bool = allow_signing_placeholders
        # PDF 32000-1 §7.5.8 — when True, replace the traditional ``xref``
        # table + ``trailer`` pair with a single ``/Type /XRef`` stream.
        self._xref_stream: bool = xref_stream
        # PDF 32000-1 §7.5.7 — when True (and ``xref_stream`` is also on,
        # since type-2 xref entries can only be addressed by a cross-
        # reference stream), pack non-stream indirect objects into ObjStm
        # streams to shrink the output.
        self._object_stream: bool = object_stream
        # Cap on objects per packed ObjStm. ``None`` keeps the PDFBox
        # default (``CompressParameters.DEFAULT_OBJECT_STREAM_SIZE``);
        # ``PDDocument.save`` threads the caller's ``CompressParameters``
        # value through here.
        if object_stream_size is not None and object_stream_size <= 0:
            raise ValueError("object_stream_size must be positive")
        self._object_stream_size: int = (
            object_stream_size
            if object_stream_size is not None
            else _OBJSTM_DEFAULT_MAX
        )
        # PDF 32000-1 §7.5.8.4 hybrid layout — emit BOTH a traditional
        # ``xref`` table and a parallel ``/Type /XRef`` stream, with the
        # trailer announcing the latter via ``/XRefStm <offset>``. Old
        # PDF-1.4 readers see the traditional table; modern readers prefer
        # the stream. Mutually exclusive with plain xref-stream output —
        # hybrid wins when both are set since it is a strict superset.
        self._hybrid_xref: bool = hybrid_xref
        # Populated during xref-stream mode by ``_pack_object_streams`` —
        # maps id(actual COSBase) → (objstm_obj_num, index_in_objstm) so
        # ``_do_write_xref_stream`` knows which entries should be written
        # as type=2 compressed records instead of type=1 indirect ones.
        self._compressed_locations: dict[int, tuple[int, int]] = {}
        # Identity-set of objects that have already been packed into an
        # ObjStm; the regular ``_do_write_object`` path skips these so we
        # don't emit duplicate indirect frames for the same payload.
        self._packed_object_ids: set[int] = set()
        # Identity-set of resolved actuals that have already had their indirect
        # frame written this pass — an actual-level dedup that lets the
        # compressed path drive emission explicitly while the main visitor
        # still safely queues references (no double-emit).
        self._emitted_actual_ids: set[int] = set()
        # ObjStm COSStreams planned by ``_pack_object_streams`` but whose
        # byte emission is deferred until after the top-level (free-standing)
        # indirect objects have been written — mirrors the upstream
        # ``doWriteBodyCompressed`` ordering (top-level first, object streams
        # last) so type-1 offsets stay as small as upstream's.
        self._pending_object_streams: list[COSStream] = []
        # id() of the /Root catalog dict — excluded from ObjStm packing
        # (set in ``_pack_object_streams``). Mirrors upstream's top-level
        # forcing of ``trailer.getCOSDictionary(ROOT)``.
        self._root_dict_id: int | None = None
        # ids of every object reachable from the trailer's /Encrypt dict
        # (populated in ``_pack_object_streams``) — the whole subtree must
        # stay out of ObjStm packing because the reader needs the complete
        # encryption dictionary (including e.g. an indirect /CF crypt-
        # filter dict) before it can decrypt any object stream.
        self._encrypt_subtree_ids: set[int] = set()
        # Value-keyed pool of indirect scalars (string / integer / float /
        # name / boolean) — populated in ``_pack_object_streams`` and consulted
        # by ``_ObjStmPoolShim`` so a direct scalar value-equal to a registered
        # indirect is emitted as a reference, mirroring upstream's
        # value-hashed ``COSObjectPool``.
        self._objstm_value_pool: dict[COSBase, COSObjectKey] = {}
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
            initial_position = (
                incremental_input.length() if incremental_input is not None else 0
            )
            self._standard_output = COSStandardOutputStream(
                self._adapter, position=initial_position
            )
        else:
            self._increment_buffer = None
            self._adapter = _RawSinkAdapter(output)
            self._standard_output = COSStandardOutputStream(self._adapter)

        # writer state — mirrors private fields on the upstream class.
        self._startxref: int = 0
        # Hybrid mode (§7.5.8.4): offset of the parallel ``/Type /XRef``
        # stream object, captured during emit so the subsequent
        # ``trailer`` can announce it via ``/XRefStm``. ``None`` outside
        # hybrid mode (so a stale value never leaks into a non-hybrid save).
        self._hybrid_xref_stm_offset: int | None = None
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
        # FIFO queue of objects awaiting their indirect-object frame. The
        # ``_WriteQueue`` subclass maintains a parallel ``id()`` set so the
        # duplicate-enqueue guard in ``_add_object_to_write`` is O(1).
        self._objects_to_write: _WriteQueue = _WriteQueue()
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
        # Optional explicit PDF-version override (PDFBox: ``setPdfVersion``).
        # When set, ``write_header(...)`` with no argument and the eventual
        # ``_do_write_header`` call use this in preference to the
        # ``COSDocument`` version. ``None`` means "fall back to the
        # document's own version".
        self._pdf_version: str | None = None
        # Started streams hook (PDFBox: ``getStartedStreams``). Upstream
        # tracks half-emitted streams here so the visitor pipeline can
        # distinguish "I'm currently inside a stream body" from "I'm at
        # the indirect-object framing layer". We don't use it yet, but
        # external callers may inspect the set, so we expose a stable
        # storage attribute and an accessor.
        self._started_streams: set[Any] = set()
        # Signature-detection flag — set by ``detect_possible_signature``
        # when ``visit_from_dictionary`` walks past a signature dict in
        # incremental mode. Mirrors upstream's private
        # ``reachedSignature`` field. The actual signing pipeline
        # (offset capture, byte-range stamp) is coordinated at the
        # pdmodel layer; the flag exists here for PDFBox-style
        # subclasses that override the writer-level hook.
        self._reached_signature: bool = False

    # ---------- public API ----------

    def get_standard_output(self) -> COSStandardOutputStream:
        return self._standard_output

    def set_standard_output(
        self, new_standard_output: COSStandardOutputStream
    ) -> None:
        """Replace the ``COSStandardOutputStream`` framing layer.

        Mirror of upstream private
        ``COSWriter.setStandardOutput(COSStandardOutputStream)``
        (line 410 of ``COSWriter.java``). Surfaced for parity with
        callers / subclasses that want to swap the formatted-output
        sink mid-construction (e.g. to wrap it in a counting stream
        for diagnostics). Most callers should leave this alone — the
        constructor wires the standard output up to the raw output
        already.
        """
        self._standard_output = new_standard_output

    def get_output(self) -> Any:
        """Return the raw output sink the writer was constructed with.

        Mirrors upstream ``COSWriter.getOutput()`` — for callers that need
        to bypass the ``COSStandardOutputStream`` framing layer (e.g. to
        splice external bytes verbatim into the file)."""
        return self._output

    def set_output(self, new_output: Any) -> None:
        """Replace the raw output sink.

        Mirror of upstream private
        ``COSWriter.setOutput(OutputStream)`` (line 400 of
        ``COSWriter.java``). Surfaced for parity with callers /
        subclasses that need to redirect the underlying byte sink. Note
        that this only updates the raw-output reference — the
        standard-output framing layer keeps writing through whatever
        adapter it was constructed with. Most callers should swap the
        full writer instead.
        """
        self._output = new_output

    def get_startxref(self) -> int:
        return self._startxref

    def set_startxref(self, value: int) -> None:
        """Override the ``startxref`` offset stamped at the tail of the
        file. Mirrors upstream ``COSWriter.setStartxref(long)`` — used by
        hybrid / xref-stream paths that need to point ``startxref`` at the
        traditional table even though the body emitted a stream first."""
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(
                f"set_startxref requires a non-negative int; got {value!r}"
            )
        self._startxref = value

    def get_xref_entries(self) -> list[COSWriterXRefEntry]:
        return self._xref_entries

    def add_xref_entry(self, entry: COSWriterXRefEntry) -> None:
        """Append ``entry`` to the writer's xref-entry list. Mirrors
        upstream ``COSWriter.addXRefEntry(XReferenceEntry)`` — exposed so
        custom serialisation paths (e.g. signature post-processing, hybrid
        layouts) can register entries without subclassing."""
        if not isinstance(entry, COSWriterXRefEntry):
            raise TypeError(
                f"add_xref_entry expects COSWriterXRefEntry; got "
                f"{type(entry).__name__}"
            )
        self._xref_entries.append(entry)

    def is_compress(self) -> bool:
        """``True`` if the writer is configured to compress non-stream
        objects into ``/Type /ObjStm`` streams. Mirrors upstream
        ``COSWriter.isCompress()`` — currently equivalent to
        :py:meth:`is_object_stream_output` since pypdfbox doesn't carry a
        separate ``CompressParameters`` toggle."""
        return self._object_stream

    def set_compress(self, value: bool) -> None:
        """Toggle compression of non-stream indirect objects into
        ``/Type /ObjStm`` streams. Paired with :py:meth:`is_compress`.

        Type-2 xref entries are the only way to address packed objects
        per PDF 32000-1 §7.5.7, so callers must also enable
        :py:meth:`set_xref_stream` (or :py:meth:`set_hybrid_xref`)
        before the actual ``write()`` call. We don't auto-promote so
        that reading either getter back stays honest about which flags
        the caller flipped."""
        self._object_stream = bool(value)

    def is_incremental(self) -> bool:
        """``True`` if this writer was constructed for an incremental
        update (the body, xref, and trailer get appended to the source
        bytes instead of replacing them).

        Mirrors upstream's private ``incrementalUpdate`` field —
        upstream lacks a public getter, but pypdfbox callers regularly
        need to introspect the mode (e.g. signature pipelines that
        configure differently for full vs. append saves)."""
        return self._incremental_update

    def get_number(self) -> int:
        """Return the running object-number counter — i.e. the highest
        ``(num, 0)`` key minted by :py:meth:`_get_object_key` so far.

        Mirrors upstream's private ``number`` field. Useful for tests
        and for callers that need to mint a fresh number externally
        (the value is read-only here; mutation goes through key
        assignment)."""
        return self._number

    # Upstream PDFBox spelling — ``getXRefEntries`` mirrors
    # ``COSWriter.getXRefEntries`` literally. Kept as a thin alias so
    # PDFBox-style callers can reach the list under either spelling.
    def get_x_ref_entries(self) -> list[COSWriterXRefEntry]:
        """Upstream alias for :py:meth:`get_xref_entries` — returns the
        live list of xref entries collected so far (empty before the
        first ``write(...)`` call)."""
        return self._xref_entries

    def get_x_ref_ranges(
        self, entries: list[COSWriterXRefEntry]
    ) -> list[int]:
        """Return flattened xref subsection ranges for ``entries``.

        Mirrors upstream ``COSWriter.getXRefRanges``: sparse object
        numbers are grouped into contiguous ``first, count`` pairs. For
        example object numbers ``0, 1, 2, 5, 6, 7, 8, 10`` yield
        ``[0, 3, 5, 4, 10, 1]``.
        """
        ranges: list[int] = []
        for first, count in self._build_ranges(sorted(entries)):
            ranges.extend((first, count))
        return ranges

    def get_started_streams(self) -> set[Any]:
        """Upstream PDFBox accessor (``getStartedStreams``). Returns the
        live set of streams whose emit is in progress; empty in the
        common case since the writer is mostly synchronous."""
        return self._started_streams

    def has_started_streams(self) -> bool:
        """Return ``True`` when the started-stream tracking set is non-empty."""
        return bool(self._started_streams)

    def clear_started_streams(self) -> None:
        """Clear the started-stream tracking set exposed by
        :py:meth:`get_started_streams`."""
        self._started_streams.clear()

    # ---- pdf version override (upstream COSWriter.setPdfVersion) ----

    def set_pdf_version(self, major: int, minor: int) -> None:
        """Pin the ``%PDF-x.y`` header version, overriding the value
        carried on the ``COSDocument``. Mirrors upstream's
        ``setPdfVersion(int, int)``."""
        if (
            not isinstance(major, int)
            or isinstance(major, bool)
            or not isinstance(minor, int)
            or isinstance(minor, bool)
        ):
            raise TypeError("set_pdf_version requires int major and minor")
        if major < 0 or minor < 0:
            raise ValueError(
                f"PDF version components must be non-negative; got "
                f"{major}.{minor}"
            )
        self._pdf_version = f"{major}.{minor}"

    def get_pdf_version(self) -> str:
        """Return the pinned PDF version string (e.g. ``"1.7"``). Falls
        back to ``"1.4"`` when no override has been set — matches the
        PDFBox default."""
        return self._pdf_version if self._pdf_version is not None else "1.4"

    # ---- upstream-spelled emit aliases ----

    def write_object(self, obj: COSBase) -> None:
        """Emit a single indirect object frame for ``obj``. Thin alias
        over the internal :py:meth:`_do_write_object` so PDFBox-style
        callers can drive the writer directly."""
        self._do_write_object(obj)

    def do_write_object(
        self,
        key_or_obj: COSObjectKey | COSBase,
        obj: COSBase | None = None,
    ) -> None:
        """Emit a single indirect object frame.

        Two upstream overloads collapse onto this one method:

        * ``do_write_object(obj)`` — assigns / reuses a key, mirrors
          upstream ``doWriteObject(COSBase)``.
        * ``do_write_object(key, obj)`` — uses ``key`` verbatim, mirrors
          upstream ``doWriteObject(COSObjectKey, COSBase)``. ``None`` /
          dangling ``COSObject`` payloads are skipped to keep the xref
          table consistent (matches upstream's null guard).
        """
        if obj is None and not isinstance(key_or_obj, COSObjectKey):
            self._do_write_object(key_or_obj)
            return
        if not isinstance(key_or_obj, COSObjectKey):
            raise TypeError(
                "do_write_object(key, obj) requires a COSObjectKey as the "
                f"first argument; got {type(key_or_obj).__name__}"
            )
        if obj is None:
            return
        if isinstance(obj, COSObject) and obj.get_object() is None:
            return
        self._do_write_object_with_key(key_or_obj, obj)

    def write_reference(self, obj: COSBase) -> None:
        """Emit ``num gen R`` for ``obj``. Mirrors upstream
        ``COSWriter.writeReference(COSBase)`` — exposed for callers that
        want to splice references into custom byte streams without
        triggering the full visitor pipeline."""
        self._write_reference(obj)

    def write_header(self, version: str | None = None) -> None:
        """Emit the ``%PDF-x.y`` header line + the binary-marker comment.

        ``version`` may be passed explicitly (``"1.7"``) or omitted, in
        which case the writer falls back to the value previously set via
        :py:meth:`set_pdf_version` (and finally to ``"1.4"``).
        """
        if version is None:
            version = self.get_pdf_version()
        if not isinstance(version, str):
            raise TypeError("write_header expects a string version like '1.7'")
        out = self._standard_output
        out.write(f"%PDF-{version}".encode("iso-8859-1"))
        out.write_eol()
        out.write(COMMENT)
        out.write(GARBAGE)
        out.write_eol()

    def write_xref(self) -> None:
        """Emit the traditional ``xref`` table for the entries collected
        during the current ``write(...)`` call. Alias over
        :py:meth:`_do_write_xref_table`."""
        self._do_write_xref_table()

    def write_trailer(self, doc: COSDocument | None = None) -> None:
        """Emit the ``trailer`` dictionary + ``startxref`` + ``%%EOF``.

        ``doc`` is required so the trailer dictionary can be sourced
        from it (mirrors the upstream signature where the document
        context is always known to the writer). If omitted, raises
        ``ValueError`` — there is no implicit document state to fall
        back on at this layer.
        """
        if doc is None:
            raise ValueError(
                "write_trailer requires a COSDocument; the trailer "
                "dictionary lives on the document, not the writer"
            )
        self._do_write_trailer(doc)
        # Match upstream COSWriter.doWriteTrailer + the startxref/%%EOF
        # epilogue emitted at the tail of ``visitFromDocument`` so the
        # standalone helper produces a complete file segment.
        out = self._standard_output
        out.write(STARTXREF)
        out.write_eol()
        out.write_int(self._startxref)
        out.write_eol()
        out.write(EOF)
        out.write_eol()

    # ---- key-lookup accessors ----

    def get_object_number(self, obj: COSBase) -> int:
        """Return the object number assigned to ``obj`` during the
        current write. Mirrors PDFBox's ``getObjectKey(obj).getNumber()``
        convenience accessor.

        Raises ``KeyError`` if the writer hasn't seen the object yet —
        matches upstream behaviour (a key must be assigned before it
        can be referenced).
        """
        key = self._lookup_existing_key(obj)
        if key is None:
            raise KeyError(f"no object key assigned for {type(obj).__name__}")
        return key.object_number

    def get_generation_number(self, obj: COSBase) -> int:
        """Return the generation number assigned to ``obj`` during the
        current write. See :py:meth:`get_object_number`."""
        key = self._lookup_existing_key(obj)
        if key is None:
            raise KeyError(f"no object key assigned for {type(obj).__name__}")
        return key.generation_number

    def _lookup_existing_key(self, obj: COSBase) -> COSObjectKey | None:
        """Return the already-assigned key for ``obj``, or ``None``.

        Resolves through ``COSObject`` wrappers so that callers can pass
        either the wrapper or the resolved actual interchangeably."""
        existing = self._object_keys.get(id(obj))
        if existing is not None:
            return existing
        if isinstance(obj, COSObject):
            actual = obj.get_object()
            if actual is not None:
                return self._object_keys.get(id(actual))
        return None

    # ---- signature placeholder hook ----

    def add_signature(self, *args: Any, **kwargs: Any) -> None:
        """Placeholder PDFBox-parity hook. Real signing is driven by
        :py:meth:`PDDocument.add_signature` which orchestrates the
        ``/ByteRange`` placeholder + post-write splice; this writer-level
        hook exists so PDFBox-style callers don't ``AttributeError`` when
        probing for the symbol. Currently a no-op."""
        return None

    # ---- upstream protected/public dispatch surface ----
    # These thin wrappers expose the strict snake_case spellings used by
    # upstream's protected/private layout (``doWriteBody`` etc.) so
    # PDFBox-style subclasses and tests can drive the writer through the
    # same names they would use against the Java class. Each forwards to
    # the underscore-prefixed implementation that already does the work.

    def add_object_to_write(self, obj: COSBase) -> None:
        """Queue ``obj`` for emission as an indirect object. Mirrors
        upstream ``COSWriter.addObjectToWrite(COSBase)``."""
        self._add_object_to_write(obj)

    def add_x_ref_entry(self, entry: COSWriterXRefEntry) -> None:
        """Upstream-cased alias for :py:meth:`add_xref_entry` mirroring
        ``COSWriter.addXRefEntry``."""
        self.add_xref_entry(entry)

    def prepare_increment(self, doc: COSDocument) -> None:
        """Populate writer key tables from the source's object pool so
        references emitted from dirty objects reuse existing keys.
        Mirrors upstream ``COSWriter.prepareIncrement``."""
        self._prepare_increment(doc)

    def get_object_key(self, obj: COSBase) -> COSObjectKey:
        """Return (and lazily assign) the indirect-object key for
        ``obj``. Mirrors upstream ``COSWriter.getObjectKey(COSBase)``.

        Note: collides spelling-wise with
        :py:meth:`pypdfbox.pdfparser.base_parser.BaseParser.get_object_key`
        which takes ``(num, gen)`` — different class, different role
        (writer assigns; parser materialises by ``(num, gen)``)."""
        return self._get_object_key(obj)

    @staticmethod
    def is_need_to_be_updated(base: COSBase | None) -> bool:
        """Return ``True`` if ``base`` carries the dirty flag.

        Mirrors upstream's private convenience method that returns
        ``false`` for nullable / non-COSUpdateInfo arguments. Static so
        callers don't need a writer instance to probe a candidate."""
        if base is None:
            return False
        is_dirty = getattr(base, "is_needs_to_be_updated", None)
        if not callable(is_dirty):
            return False
        try:
            return bool(is_dirty())
        except Exception:
            return False

    def detect_possible_signature(self, obj: COSDictionary) -> None:
        """Set the writer's ``reached_signature`` flag when ``obj`` is a
        signature dictionary in incremental-update mode.

        Mirrors upstream ``COSWriter.detectPossibleSignature(COSDictionary)``.
        We track the flag on ``self._reached_signature`` for parity with
        the upstream private field; the regular emit pipeline doesn't
        consult it yet (signing is coordinated at the pdmodel layer),
        but exposing the hook lets PDFBox-style subclasses override the
        decision the same way they would against Java upstream.

        ``obj`` must be a ``COSDictionary``. Non-dictionary input is a
        no-op rather than a hard error so callers can pass any
        candidate without first type-checking."""
        if not isinstance(obj, COSDictionary):
            return
        if not self._incremental_update:
            return
        if getattr(self, "_reached_signature", False):
            return
        type_name = obj.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
        if not isinstance(type_name, COSName):
            return
        if type_name.name not in ("Sig", "DocTimeStamp"):
            return
        byte_range_name = COSName.get_pdf_name("ByteRange")
        byte_range = obj.get_dictionary_object(byte_range_name)
        if not isinstance(byte_range, COSArray) or byte_range.size() != 4:
            return
        third = byte_range.get(2) if byte_range.size() > 2 else None
        if not isinstance(third, COSInteger):
            return
        # Upstream: ``br[2] > inputData.length()`` distinguishes "real"
        # signatures from old residue. We don't always have an input
        # source available here so we conservatively just record the
        # flag — the actual signing pipeline handles offset arithmetic.
        source_length = (
            self._incremental_input.length()
            if self._incremental_input is not None
            else 0
        )
        if third.value > source_length:
            self._reached_signature = True

    def do_write_header(self, doc: COSDocument) -> None:
        """Emit the ``%PDF-x.y`` header + binary marker. Mirrors upstream
        ``COSWriter.doWriteHeader(COSDocument)``."""
        self._do_write_header(doc)

    def do_write_body(self, doc: COSDocument) -> None:
        """Emit the document's body (root, info, encrypt, drained queue).
        Mirrors upstream ``COSWriter.doWriteBody(COSDocument)``."""
        self._do_write_body(doc)

    def do_write_body_compressed(self, doc: COSDocument) -> None:
        """Emit the body using object-stream compression. Mirrors
        upstream ``COSWriter.doWriteBodyCompressed(COSDocument)`` —
        delegates to the xref-stream body path which packs eligible
        objects into ``/Type /ObjStm`` streams."""
        self._do_write_body_xref_stream(doc)

    def do_write_objects(self) -> None:
        """Drain the object-write queue, emitting one indirect frame per
        object. Mirrors upstream ``COSWriter.doWriteObjects()``."""
        self._do_write_objects()

    def do_write_trailer(self, doc: COSDocument) -> None:
        """Emit the ``trailer`` keyword + dictionary. Mirrors upstream
        ``COSWriter.doWriteTrailer(COSDocument)`` — does NOT emit
        ``startxref``/``%%EOF``; that tail is the orchestration layer's
        job (see :py:meth:`write_trailer` for the bundled helper)."""
        self._do_write_trailer(doc)

    def do_write_x_ref_table(self) -> None:
        """Emit the traditional ``xref`` table. Mirrors upstream
        ``COSWriter.doWriteXRefTable()``."""
        self._do_write_xref_table()

    def do_write_x_ref_inc(self, doc: COSDocument) -> None:
        """Emit the incremental xref + trailer pair. Mirrors upstream
        ``COSWriter.doWriteXRefInc(COSDocument)``.

        Routes to the xref-stream path when the source uses xref
        streams; otherwise emits a traditional ``xref`` table chained
        via ``/Prev`` to the previous startxref."""
        if (
            getattr(doc, "is_xref_stream", lambda: False)()
            and not getattr(doc, "has_hybrid_xref", lambda: False)()
        ) or (
            getattr(doc, "is_xref_stream", lambda: False)()
            and not self._incremental_update
        ):
            self._do_write_xref_stream(doc)
        else:
            self._do_write_xref_increment()
            self._do_write_trailer_increment(doc)

    def fill_gaps_with_free_entries(self) -> None:
        """Insert free-list entries for object numbers not covered by
        the recorded normal entries. Mirrors upstream
        ``COSWriter.fillGapsWithFreeEntries()``."""
        self._fill_gaps_with_free_entries()

    def do_write_increment(self, doc: COSDocument) -> None:
        """Emit an append-only update on top of the source bytes.
        Mirrors upstream ``COSWriter.doWriteIncrement()`` (which takes
        no doc — pulls from instance state — but we accept the doc
        here for symmetry with the rest of the ``do_write_*`` family)."""
        self._do_write_increment(doc)

    def write_xref_range(self, x: int, y: int) -> None:
        """Emit a single ``first count`` xref-section header.
        Mirrors upstream ``COSWriter.writeXrefRange(long, long)``."""
        self._write_xref_range(x, y)

    def write_xref_entry(self, entry: COSWriterXRefEntry) -> None:
        """Emit a single 20-byte xref row. Mirrors upstream
        ``COSWriter.writeXrefEntry(XReferenceEntry)``."""
        self._write_xref_entry(entry)

    def write_array(self, array: COSArray) -> None:
        """Emit ``array`` either inline or as an indirect reference,
        depending on its ``is_direct`` flag. Mirrors upstream
        ``COSWriter.writeArray(COSArray)``."""
        self._write_array(array)

    def write_dictionary(self, dictionary: COSDictionary) -> None:
        """Emit ``dictionary`` either inline or as an indirect reference,
        depending on its ``is_direct`` flag. Mirrors upstream
        ``COSWriter.writeDictionary(COSDictionary)``."""
        self._write_dictionary(dictionary)

    # ---- signature emission stubs (upstream COSWriter signing surface) ----
    # Real signing is coordinated by ``PDDocument`` and the
    # ``signature`` cluster; the writer-level hooks here exist so
    # PDFBox-style callers can probe / override the symbols. They
    # raise the same ``IllegalStateError`` upstream raises when the
    # writer is not in a signing state, which keeps misuse loud.

    def get_data_to_sign(self) -> Any:
        """Return the byte stream to be hashed for an external
        signature. Mirrors upstream ``COSWriter.getDataToSign()``.

        Raises ``IllegalStateError`` (Python ``RuntimeError`` for
        parity with upstream's ``IllegalStateException``) — pypdfbox's
        signing pipeline is owned by ``PDDocument`` and does not
        currently exercise this writer-level hook. Implementing it
        requires the security cluster's digest path, which is tracked
        separately."""
        raise RuntimeError("PDF not prepared for signing")

    def write_external_signature(self, cms_signature: bytes) -> None:
        """Splice a CMS signature bytes blob into the reserved
        placeholder. Mirrors upstream
        ``COSWriter.writeExternalSignature(byte[])``.

        Raises ``RuntimeError`` until the writer-level signing pipeline
        is implemented (see :py:meth:`get_data_to_sign`)."""
        if not isinstance(cms_signature, (bytes, bytearray, memoryview)):
            raise TypeError(
                "write_external_signature expects bytes-like input; "
                f"got {type(cms_signature).__name__}"
            )
        raise RuntimeError("PDF not prepared for setting signature")

    def do_write_signature(self) -> None:
        """Compute the signature ``/ByteRange`` and stamp it into the
        reserved buffer slot. Mirrors upstream
        ``COSWriter.doWriteSignature()``.

        Raises ``RuntimeError`` until the writer-level signing pipeline
        is implemented; callers should drive signing through
        ``PDDocument.add_signature`` which owns the byte-range splice."""
        raise RuntimeError("PDF not prepared for signing")

    # ---- visitor: upstream alias ----

    def visit_from_int(self, obj: COSInteger) -> Any:
        """Upstream-spelled alias for :py:meth:`visit_from_integer`.

        Java's ``visitFromInt`` snake-cases to ``visit_from_int``; we
        normally use ``visit_from_integer`` to avoid shadowing Python's
        built-in ``int`` keyword in the class scope, but keeping the
        upstream spelling around as an alias lets PDFBox-style callers
        dispatch under the original name."""
        return self.visit_from_integer(obj)

    # ---- static helpers ----

    @staticmethod
    def format_xref_offset(offset: int) -> bytes:
        """Format an xref-table offset as 10-digit ASCII bytes.

        Mirrors upstream's private ``formatXrefOffset`` ``DecimalFormat``
        constant. Exposed publicly so callers writing custom xref
        layouts (e.g. signature post-processing) can reuse the same
        formatter the writer applies internally — keeps the 20-byte
        row width per ISO 32000-1 §7.5.4 byte-for-byte consistent."""
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise TypeError(
                f"format_xref_offset requires an int; got {type(offset).__name__}"
            )
        if offset < 0:
            raise ValueError(
                f"xref offset must be non-negative; got {offset}"
            )
        return _format_xref_offset(offset)

    @staticmethod
    def format_xref_generation(gen: int) -> bytes:
        """Format an xref-table generation as 5-digit ASCII bytes.

        Mirrors upstream's private ``formatXrefGeneration``
        ``DecimalFormat`` constant. Generation numbers are bounded to
        65535 by ISO 32000-1 §7.5.4; we accept that ceiling as the
        widest valid value rather than blindly zero-padding any int."""
        if not isinstance(gen, int) or isinstance(gen, bool):
            raise TypeError(
                f"format_xref_generation requires an int; got {type(gen).__name__}"
            )
        if gen < 0 or gen > 65535:
            raise ValueError(
                f"generation must be in [0, 65535]; got {gen}"
            )
        return _format_xref_generation(gen)

    @staticmethod
    def to_hex_string(value: bytes) -> str:
        """Hex-encode ``value`` to an uppercase ASCII string. Mirrors
        upstream ``COSWriter.toHexString(byte[])`` — used when emitting
        signature placeholders, file-id arrays, and similar byte blobs
        that must be readable as hex by the parser."""
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"to_hex_string expects bytes-like input, got {type(value).__name__}"
            )
        return bytes(value).hex().upper()

    # ---- lifecycle alias ----

    def release(self) -> None:
        """Upstream ``release()`` alias — frees writer resources. Currently
        delegates to :py:meth:`close`."""
        self.close()

    # ---- xref-stream / object-stream output toggles ----
    # Mirror upstream COSWriter's ``setIncrementalWriter``-style accessor
    # naming. Booleans mirror the constructor-time flags so callers can
    # flip them between construction and the actual ``write()`` call.

    def is_xref_stream_output(self) -> bool:
        """``True`` if the writer will emit an xref *stream* (PDF 32000-1
        §7.5.8) instead of a traditional ``xref`` table + ``trailer``."""
        return self._xref_stream

    def set_xref_stream(self, value: bool) -> None:
        """Toggle xref-stream output. See PDF 32000-1 §7.5.8.

        When ``True`` the writer skips emitting the ``xref`` keyword and
        the ``trailer`` keyword entirely — both are folded into a single
        ``/Type /XRef`` indirect-object stream whose offset is announced
        by the ``startxref`` line. Required for object-stream output."""
        self._xref_stream = bool(value)

    def is_object_stream_output(self) -> bool:
        """``True`` if non-stream indirect objects will be packed into
        ``/Type /ObjStm`` streams (PDF 32000-1 §7.5.7)."""
        return self._object_stream

    def set_object_stream(self, value: bool) -> None:
        """Toggle object-stream packing. Type-2 xref entries are the only
        way to address packed objects, so this implies xref-stream output;
        callers must also set :py:meth:`set_xref_stream` (we don't auto-
        promote because the user might want to flip them in either order
        and reading either getter back should be honest)."""
        self._object_stream = bool(value)

    def is_hybrid_xref_output(self) -> bool:
        """``True`` if the writer will emit a hybrid layout (PDF 32000-1
        §7.5.8.4): both a traditional ``xref`` table and a parallel
        ``/Type /XRef`` stream, linked from the trailer via ``/XRefStm``."""
        return self._hybrid_xref

    def set_hybrid_xref(self, value: bool) -> None:
        """Toggle hybrid xref output. When ``True``, the writer emits the
        body, then a ``/Type /XRef`` stream as a normal indirect object,
        then the traditional ``xref`` keyword + table covering ALL objects
        (including the xref stream itself), then the ``trailer`` with
        ``/XRefStm <offset>`` pointing at the xref stream, and finally
        ``startxref <offset_of_traditional_xref>`` so legacy readers find
        the table while modern readers can prefer the stream.

        Mutually exclusive with :py:meth:`set_xref_stream` — when both are
        on, hybrid wins (it is a superset behavior)."""
        self._hybrid_xref = bool(value)

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
            raise OSError("COSWriter already closed")

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

        self._validate_stream_output_flags()

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
            if not self._allow_signing_placeholders:
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

    def _validate_stream_output_flags(self) -> None:
        """Reject flag combinations that would silently ignore ObjStm output."""
        if not self._object_stream:
            return
        if self._hybrid_xref:
            raise ValueError(
                "object_stream output is not supported with hybrid_xref; "
                "use xref_stream=True without hybrid_xref"
            )
        if not self._xref_stream:
            raise ValueError(
                "object_stream output requires xref_stream=True so packed "
                "objects can be addressed by type-2 xref entries"
            )

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
            from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
                PublicKeyProtectionPolicy,
            )
            from pypdfbox.pdmodel.encryption.public_key_security_handler import (
                PublicKeySecurityHandler,
            )
            from pypdfbox.pdmodel.encryption.standard_protection_policy import (
                StandardProtectionPolicy,
            )
            from pypdfbox.pdmodel.encryption.standard_security_handler import (
                StandardSecurityHandler,
            )

            if isinstance(protection_policy, StandardProtectionPolicy):
                # The standard handler derives the file-encryption key from
                # the file-id; ensure trailer carries one BEFORE prepare_document
                # synthesises /O, /U, etc. (otherwise it falls back to the
                # 16-zero-bytes fixture which won't survive a re-load).
                self._propagate_document_id(cos_document)
                handler = StandardSecurityHandler(protection_policy)
                handler.prepare_document(pd_document)
            elif isinstance(protection_policy, PublicKeyProtectionPolicy):
                # Public-key (``/Adobe.PubSec``) handler — derives the file
                # key from a fresh 20-byte seed wrapped per-recipient via
                # PKCS#7 (see PublicKeySecurityHandler.prepare_document).
                # /ID still helps downstream tooling, so seed one if missing.
                self._propagate_document_id(cos_document)
                handler = PublicKeySecurityHandler(protection_policy)
                handler.prepare_document(pd_document)
            else:
                raise TypeError(
                    "COSWriter encryption: protection policy must be "
                    "StandardProtectionPolicy or PublicKeyProtectionPolicy, "
                    f"got {type(protection_policy).__name__}"
                )
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
        if self._hybrid_xref:
            # Hybrid layout (PDF 32000-1 §7.5.8.4): emit the body, then a
            # ``/Type /XRef`` stream as a normal indirect object, then the
            # traditional ``xref`` table covering ALL objects (including
            # the xref stream itself), then a ``trailer`` carrying
            # ``/XRefStm <xref_stream_offset>``. ``startxref`` points at
            # the traditional xref so legacy PDF-1.4 readers find it
            # first; modern readers see /XRefStm and prefer the stream.
            self._do_write_body(doc)
            self._do_write_xref_stream(doc, in_hybrid=True)
            self._do_write_xref_table()
            self._do_write_trailer(doc, xref_stm_offset=self._hybrid_xref_stm_offset)
        elif self._xref_stream:
            # xref-stream / object-stream output path — emit the body,
            # then a single ``/Type /XRef`` indirect object that subsumes
            # the trailer (PDF 32000-1 §7.5.8.4 — "the trailer dictionary
            # entries shall be present in the xref stream dictionary").
            self._do_write_body_xref_stream(doc)
            self._do_write_xref_stream(doc)
        else:
            # Classic path: dedicated ``xref`` section + ``trailer`` keyword.
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
        """Refuse to re-save a signed document while a ``/ByteRange``
        placeholder is still in flight.

        ISO 32000-1 §12.8 reserves a ``/ByteRange [0 0 0 0]`` placeholder
        inside the signature dict during the signing pipeline; touching
        the file before the digest is recomputed silently corrupts the
        signature. We raise here rather than emit a busted document.

        An *already-signed* PDF (whose ``/ByteRange`` honestly brackets
        the existing file end-to-end) is fine to incrementally append
        to — that's how PAdES-LTV stamps work (PDF 32000-2 §12.8.4).
        We detect a true placeholder vs a valid byterange by inspecting
        the third entry: a placeholder's ``br[2]`` is either zero
        (the ``[0 0 0 0]`` sentinel) or points past the input source's
        end (the post-render placeholder). Either way, the file content
        clearly isn't in agreement with the byterange yet.
        """
        input_length: int | None = (
            self._incremental_input.length()
            if self._incremental_input is not None
            else None
        )
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
            ints = byte_range.to_cos_number_integer_list()
            if any(i is None for i in ints):
                continue
            br = [int(i) for i in ints]  # type: ignore[arg-type]
            # Canonical placeholder shapes: all zeros, or br[2] beyond
            # the input source's end (mirrors PDFBox's
            # ``br[2] > inputData.length()`` detection).
            is_zero_placeholder = br == [0, 0, 0, 0]
            is_past_eof_placeholder = (
                input_length is not None and br[2] > input_length
            )
            if is_zero_placeholder or is_past_eof_placeholder:
                raise NotImplementedError(
                    "re-signing with PDFBox-style ByteRange placeholders "
                    "requires the security cluster"
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
        self._seed_incremental_position(source_length)

        # 1. ``prepareIncrement`` — register every existing key/actual so
        # references emitted from the dirty graph reuse the source's keys.
        self._prepare_increment(doc)

        # 2. Walk the dirty graph. Every COSObject in the pool whose
        # resolved actual is dirty becomes a candidate; we then promote
        # any directly-referenced dirty actuals.
        self._enqueue_dirty_objects(doc)

        # 2.1 Offer the trailer's top-level entries (/Root, /Info, /Encrypt)
        # to the write queue too. A brand-new dictionary wired into the
        # trailer — most commonly an /Info dict synthesised by
        # ``PDDocument.get_document_information()`` when the source had none —
        # is reachable ONLY from the trailer, never from the object pool, so
        # the pool-only walk above misses it and the appended revision would
        # silently drop the change. ``_add_object_to_write`` applies the
        # incremental dirty-filter, so an un-dirtied /Root or /Info is still
        # skipped; only a dict flagged ``needs_to_be_updated`` is enqueued and
        # minted a fresh object key. Mirrors upstream ``COSWriter.doWriteBody``,
        # which seeds the same three trailer entries before draining the queue.
        trailer = doc.get_trailer()
        if trailer is not None:
            for trailer_key in (COSName.ROOT, COSName.INFO, COSName.ENCRYPT):  # type: ignore[attr-defined]
                entry = trailer.get_item(trailer_key)
                if entry is not None:
                    self._add_object_to_write(entry)

        # Note: even when nothing is dirty (``_objects_to_write`` empty) PDFBox
        # 3.0.7 still appends a fresh revision — a new (empty) cross-reference
        # section listing only the free-list head plus a trailer chained via
        # ``/Prev`` (oracle-confirmed: ``saveIncremental`` on an unmodified
        # document grows the file and adds one ``startxref`` section). We
        # therefore fall through to the normal xref+trailer emit below instead
        # of short-circuiting to a byte-identical copy; the body pass simply
        # writes zero objects. See CHANGES.md (wave 1565).

        # 2.5 Whitespace separator so the appended bytes are unambiguously
        # delimited from the source's trailing ``%%EOF``. Mirrors upstream's
        # ``getStandardOutput().writeCRLF()`` at the top of
        # ``visitFromDocument`` in incremental mode. Goes through the
        # buffered stream so byte offsets stay consistent.
        out = self._standard_output
        out.write_crlf()

        # 3. Emit each indirect object's body. Offsets recorded by
        # ``_do_write_object`` are absolute because the standard output
        # position is seeded with the source length.
        self._do_write_objects()

        # 4/5. Emit the new cross-reference + trailer. Mirrors upstream
        # ``COSWriter.doWriteXRefInc``: a source whose most-recent
        # cross-reference is an xref STREAM (and is NOT a hybrid file)
        # receives an appended xref STREAM; everything else gets a classic
        # ``xref`` table chained via ``/Prev``. Without this branch an
        # xref-stream source would emit a classic ``xref`` table while the
        # appended trailer still carried the source's ``/Type /XRef`` (plus
        # leftover ``/W`` / ``/Index`` / ``/Filter`` keys) — a malformed
        # mix that diverges from PDFBox.
        if doc.is_xref_stream() and not doc.has_hybrid_xref():
            self._do_write_xref_stream_increment(doc)
        else:
            # 4. Emit the new xref section. Must include only the changed
            # objects + the mandatory free-list head (object 0).
            self._do_write_xref_increment()
            # 5. Emit the trailer with /Prev pointing at the prior startxref.
            self._do_write_trailer_increment(doc)

        # 6. startxref + %%EOF.
        out.write(STARTXREF)
        out.write_eol()
        out.write_int(self._startxref)
        out.write_eol()
        out.write(EOF)
        out.write_eol()

        # 7. Drain: copy source, then append increment.
        self._copy_source_to_output()
        increment = self._increment_buffer.getvalue()
        if increment:  # pragma: no branch
            # Defensive: at this point the increment buffer carries the
            # appended objects, the xref table, and the trailer — it is
            # always non-empty in well-formed incremental saves.
            self._write_to_output(increment)

    def _seed_incremental_position(self, source_length: int) -> None:
        """Align the buffered incremental stream with absolute file offsets.

        When ``incremental_input`` is supplied at construction time this is
        already true. If the source is auto-pulled from the document during
        ``write()``, seed the position just before the first append byte.
        """
        assert self._increment_buffer is not None
        if (
            self._standard_output.get_position() == 0
            and self._increment_buffer.tell() == 0
        ):
            self._standard_output = COSStandardOutputStream(
                self._adapter, position=source_length
            )

    def _prepare_increment(self, doc: COSDocument) -> None:
        """Populate ``object_keys`` / ``key_object`` from the source's
        object pool so that references emitted from dirty objects resolve
        to existing keys instead of minting fresh ones."""
        for key in doc.get_object_keys():
            cos_obj = doc.get_object_from_pool(key)
            if not cos_obj.is_dereferenced():
                # Never loaded: cannot be dirty and its actual is unreachable
                # from the dirty graph, so skip the force-parse. Still reserve
                # the wrapper's KEY so a reference emitted from the dirty graph
                # to this COSObject resolves to the existing key instead of
                # minting a fresh one (and so /Size accounting stays correct).
                self._object_keys[id(cos_obj)] = key
                self._key_holders[id(cos_obj)] = cos_obj
                continue
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
            # A never-dereferenced lazy object cannot be dirty (marking it
            # dirty requires first resolving it), so it cannot appear in the
            # appended revision — skip the force-parse.
            if not cos_obj.is_dereferenced():
                continue
            actual = cos_obj.get_object()
            if actual is None:
                continue
            if actual.is_needs_to_be_updated() or cos_obj.is_needs_to_be_updated():
                self._add_object_to_write(cos_obj)

    def _do_write_xref_increment(self) -> None:
        """Emit the new xref section. Subsections cover only the changed /
        new objects plus the mandatory free-list head."""
        out = self._standard_output

        # Always include the free-list head (object 0). Upstream calls this
        # ``addXRefEntry(FreeXReference.NULL_ENTRY)``.
        self._xref_entries.append(COSWriterXRefEntry.get_null_entry())

        entries = sorted(self._xref_entries)
        # Record startxref as an absolute offset. The standard output
        # position was seeded with ``source_length`` before any append bytes.
        self._startxref = out.get_position()

        out.write(XREF)
        out.write_eol()

        # ``entries`` is sorted and ``_build_ranges`` groups it into
        # contiguous runs, so each range consumes exactly the next ``count``
        # entries — a single running index avoids the O(ranges × entries)
        # rescan the per-range filter would incur.
        idx = 0
        for first, count in self._build_ranges(entries):
            self._write_xref_range(first, count)
            for entry in entries[idx : idx + count]:
                self._write_xref_entry_incremental(entry)
            idx += count

    def _write_xref_entry_incremental(self, entry: COSWriterXRefEntry) -> None:
        """Same wire format as the full-save xref entry."""
        out = self._standard_output
        out.write(_format_xref_table_offset(entry.offset))
        out.write(SPACE)
        out.write(_format_xref_table_generation(entry.key.generation_number))
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

        # /ID: ISO 32000-1 §14.4 — "if the file has been updated, the second
        # [byte string] shall be changed". PDFBox's incremental save preserves
        # /ID[0] (the permanent file identifier) and regenerates /ID[1] (the
        # changing identifier) as a SHA-256 digest over the document state.
        # Mirror that contract: keep /ID[0] stable, replace /ID[1] with a fresh
        # 32-byte digest. We build a NEW array on a copied dict so the in-memory
        # document is left untouched (a re-save must still see the source /ID).
        id_arr = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if isinstance(id_arr, COSArray) and id_arr.size() == 2:
            first = id_arr.get_object(0)
            new_id = self._regenerate_changing_id(doc, first)
            new_id.set_direct(True)
            trailer.set_item(COSName.get_pdf_name("ID"), new_id)
        elif isinstance(id_arr, COSArray):
            id_arr.set_direct(True)

        # Other ephemeral keys upstream strips before re-emit.
        trailer.remove_item(COSName.get_pdf_name("DocChecksum"))
        trailer.remove_item(COSName.get_pdf_name("XRefStm"))

        trailer.accept(self)

    def _do_write_xref_stream_increment(self, doc: COSDocument) -> None:
        """Append an incremental cross-reference STREAM for an xref-stream
        source. Mirrors the xref-stream arm of upstream
        ``COSWriter.doWriteXRefInc`` (which builds a ``PDFXRefStream``,
        feeds it ``getXRefEntries()``, copies the trailer info, and writes
        the stream as a regular object).

        The appended stream lists ONLY the objects this increment rewrote
        (already accumulated in ``self._xref_entries`` by the body pass)
        plus the mandatory free-list head (object 0). Crucially the xref
        stream's OWN entry is NOT added to its ``/Index`` — upstream's
        ``PDFXRefStream.getIndexEntry`` only knows about object 0 and the
        entries fed via ``addEntry``; the reader locates the stream through
        ``startxref``, not through a self-reference (oracle-confirmed:
        ``/Index [0 1 33 1]`` for a one-page edit, no self-entry).

        ``/Size`` is the document-wide highest object number + 1 (covering
        the freshly-minted xref stream object), ``/Prev`` points at the
        source's previous ``startxref``, and ``/ID[1]`` is refreshed while
        ``/ID[0]`` is preserved (PDF 32000-1 §14.4)."""
        out = self._standard_output

        # Mint the xref stream's own number FIRST so /Size can account for
        # it. It is deliberately kept out of the entry/index set below.
        xref_key = self._mint_fresh_object_key()

        # The changed entries fed into the stream (``streamData`` upstream).
        # This list mirrors exactly what ``COSWriter.doWriteXRefInc`` passes to
        # ``PDFXRefStream.addEntry`` — only the objects this increment rewrote.
        # We deliberately do NOT prepend object 0's free head here and do NOT
        # add the xref stream's OWN self-entry: upstream
        # ``PDFXRefStream.writeStreamData`` emits the object-0 ``NULL_ENTRY``
        # row implicitly (always, as a single leading row) and the self
        # ``NormalXReference`` is only registered on ``COSWriter`` *after*
        # ``getStream()`` already serialised the body, so it never lands in the
        # stream data nor the ``/Index`` (oracle-confirmed against PDFBox
        # 3.0.7: a one-field edit emits ``/Index [0 1 30 1 32 1]`` with three
        # rows and no self-row). We do NOT run ``_fill_gaps_with_free_entries``
        # — that would re-declare every untouched object number as free.
        entries: list[tuple[int, int, int, int]] = []
        for entry in self._xref_entries:
            objnum = entry.key.object_number
            if entry.free:
                entries.append((objnum, 0, entry.offset, entry.key.generation_number))
                continue
            actual = (
                entry.obj.get_object()
                if isinstance(entry.obj, COSObject)
                else entry.obj
            )
            comp = (
                self._compressed_locations.get(id(actual))
                if actual is not None
                else None
            )
            if comp is not None:
                objstm_num, idx = comp
                entries.append((objnum, 2, objstm_num, idx))
            else:
                entries.append((objnum, 1, entry.offset, entry.key.generation_number))

        # ``streamData`` is sorted by object number before width computation
        # (upstream sorts it in ``writeStreamData``); sort here so the body and
        # the /Index ranges agree.
        entries.sort(key=lambda r: r[0])

        # /W widths — mirror ``PDFXRefStream.getWEntry``: each field width is
        # the byte count of the MAX value in that column ACROSS ``streamData``
        # ONLY (the implicit object-0 NULL_ENTRY row and the self-entry are
        # both excluded from the width scan). A column whose max is 0 yields
        # width 0 — so a pure offset-only increment (all generations 0, no
        # object-stream rows) correctly produces ``/W [1 3 0]`` rather than the
        # over-wide ``[1 3 2]`` that injecting the 65535 free-head gen forced.
        max_field1 = max((t for _n, t, _f2, _f3 in entries), default=0)
        max_field2 = max((f2 for _n, _t, f2, _f3 in entries), default=0)
        max_field3 = max((f3 for _n, _t, _f2, f3 in entries), default=0)
        w1 = _xref_field_width(max_field1)
        w2 = _xref_field_width(max_field2)
        w3 = _xref_field_width(max_field3)
        if w1 + w2 + w3 == 0:
            # Degenerate increment: no object was rewritten, so the stream
            # body holds only the implicit object-0 free-head row. All-zero
            # widths would make that row (and the stream) unparseable —
            # readers reject ``/W [0 0 0]``. Give the type and offset
            # columns one byte each so the mandatory row survives.
            w1, w2 = 1, 1

        # /Index — upstream ``getIndexEntry`` always seeds object 0 into the
        # index range (so a fresh reader sees the free-list head), then the
        # changed object numbers. The self-entry's number is excluded.
        index_numbers = sorted({0, *(n for n, _t, _f2, _f3 in entries)})

        # Body: leading object-0 row from the NULL_ENTRY (type 0, next-free 0,
        # generation 65535) written with the COMPUTED w3 — when w3 is 0 the
        # 65535 truncates to zero bytes, exactly as ``writeNumber`` does
        # upstream — then the sorted streamData rows.
        body = bytearray()
        body.extend(_pack_unsigned(0, w1))
        body.extend(_pack_unsigned(0, w2))
        body.extend(_pack_unsigned(65535 & ((1 << (8 * w3)) - 1) if w3 else 0, w3))
        for _objnum, t, f2, f3 in entries:
            body.extend(_pack_unsigned(t, w1))
            body.extend(_pack_unsigned(f2, w2))
            body.extend(_pack_unsigned(f3, w3))

        xref_offset = out.get_position()

        index_arr = COSArray()
        index_arr.set_direct(True)
        for first, count in self._build_int_ranges(index_numbers):
            index_arr.add(COSInteger.get(first))
            index_arr.add(COSInteger.get(count))

        w_arr = COSArray()
        w_arr.set_direct(True)
        for width in (w1, w2, w3):
            w_arr.add(COSInteger.get(width))

        # Build the xref-stream dictionary in upstream's EXACT key-insertion
        # order so the appended tail is byte-identical to PDFBox. Upstream's
        # COSStream keySet is insertion-ordered (LinkedHashMap), and the
        # serialiser emits keys in that order. The insertion sequence in
        # PDFBox is:
        #   1. ``/Length 0`` — seeded by the ``COSStream`` constructor.
        #   2. ``addTrailerInfo`` — the trailer's ``/Info /Root /Encrypt /ID
        #      /Prev`` subset, copied IN TRAILER-ITERATION ORDER (the
        #      ``forEach`` over the trailer's own LinkedHashMap). Upstream
        #      sets the new ``/Prev`` onto the trailer (``trailer.setLong``)
        #      BEFORE ``addTrailerInfo`` runs, so ``/Prev`` rides along at its
        #      existing trailer position.
        #   3. ``getStream`` — ``/Type /Size /Index /W`` in that order.
        #   4. ``createOutputStream`` — ``/Filter`` appended last; ``/Length``
        #      is then updated in place and stays at the front.
        # pypdfbox's ``COSStream.__init__`` does not pre-seed ``/Length``, so
        # we seed it explicitly to reproduce step (1)'s front position.
        xref_stream = COSStream()
        xref_stream.set_int(COSName.LENGTH, 0)  # type: ignore[attr-defined]

        # /Size = document-wide highest object number + 1, including the new
        # xref stream object. Mirrors upstream ``setSize(number + 2)`` where
        # ``number`` is the highest source object number. Computed up front but
        # inserted in step (3) below.
        doc_keys = {k.object_number for k in doc.get_object_keys()}
        doc_keys.update(k.object_number for k in self._key_object)
        size_value = max(doc_keys | {xref_key.object_number}, default=0) + 1

        # Step (2): ``addTrailerInfo`` — copy the ``/Info /Root /Encrypt /ID
        # /Prev`` subset from the source trailer IN ITS OWN ITERATION ORDER,
        # substituting the freshly-computed ``/Prev`` value (upstream had
        # already overwritten it on the trailer before this call).
        prev_value = doc.get_start_xref()
        source_trailer = doc.get_trailer()
        _info_subset = {
            COSName.INFO,  # type: ignore[attr-defined]
            COSName.ROOT,  # type: ignore[attr-defined]
            COSName.ENCRYPT,  # type: ignore[attr-defined]
            COSName.get_pdf_name("ID"),
            COSName.PREV,  # type: ignore[attr-defined]
        }
        if source_trailer is not None:
            for tkey in source_trailer.key_set():
                if tkey not in _info_subset:
                    continue
                if tkey == COSName.PREV:  # type: ignore[attr-defined]
                    xref_stream.set_int(COSName.PREV, prev_value)  # type: ignore[attr-defined]
                else:
                    xref_stream.set_item(tkey, source_trailer.get_item(tkey))
        # ``/Prev`` may be absent from the source trailer (a first-revision
        # synthesised document); upstream still writes it because COSWriter
        # set it on the trailer before ``addTrailerInfo``. Append it if the
        # iteration above didn't already.
        if not xref_stream.contains_key(COSName.PREV):  # type: ignore[attr-defined]
            xref_stream.set_int(COSName.PREV, prev_value)  # type: ignore[attr-defined]

        # Step (3): ``getStream`` — /Type /Size /Index /W in that order.
        xref_stream.set_item(COSName.TYPE, COSName.get_pdf_name("XRef"))  # type: ignore[attr-defined]
        xref_stream.set_int(COSName.SIZE, size_value)  # type: ignore[attr-defined]
        xref_stream.set_item(COSName.get_pdf_name("Index"), index_arr)
        xref_stream.set_item(COSName.get_pdf_name("W"), w_arr)

        # Step (4): write the body through the FlateDecode chain. This appends
        # ``/Filter`` last and updates the pre-seeded ``/Length`` in place.
        xref_stream.set_data(bytes(body), [_FLATE_DECODE_NAME])

        # Refresh /ID[1] (stable /ID[0]) — PDF 32000-1 §14.4. Build a fresh
        # array so the in-memory document's trailer /ID is left untouched.
        id_value = xref_stream.get_dictionary_object(COSName.get_pdf_name("ID"))
        if isinstance(id_value, COSArray) and id_value.size() == 2:
            new_id = self._regenerate_changing_id(doc, id_value.get_object(0))
            new_id.set_direct(True)
            xref_stream.set_item(COSName.get_pdf_name("ID"), new_id)
        elif isinstance(id_value, COSArray):
            id_value.set_direct(True)

        # Register the xref stream's key BEFORE emit so internal references
        # reuse the minted number.
        self._object_keys[id(xref_stream)] = xref_key
        self._key_holders[id(xref_stream)] = xref_stream
        self._key_object[xref_key] = xref_stream

        # startxref points at the xref stream itself.
        self._startxref = xref_offset
        self._do_write_object(xref_stream)

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
        # Object-stream compression requires PDF 1.5+ (object streams) and a
        # cross-reference stream; upstream ``COSWriter.doWriteHeader`` raises the
        # version to ``COSWriterCompressionPool.MINIMUM_SUPPORTED_VERSION`` (1.6)
        # when ``isCompress()`` — bumping BOTH the PDDocument (catalog ``/Version``
        # entry, for docs whose header version is already >= 1.4) and the
        # COSDocument (the header version itself) — so a 1.4 input compressed-saves
        # as ``%PDF-1.6`` with ``/Version /1.6`` in the catalog. Mirror that here
        # before the header version is read (skipped when an explicit
        # ``set_pdf_version`` override is in play, matching upstream's preference
        # for an explicit pin).
        if self._object_stream and self._pdf_version is None:
            self._bump_version_for_compress(doc)
        # Honour an explicit ``set_pdf_version`` override so callers can
        # bump the header without mutating the COSDocument. Falls through
        # to the document's own version when no override is in play.
        if self._pdf_version is not None:
            version_text = self._pdf_version
        else:
            version_text = self._format_version(doc.get_version())
        marker = "FDF" if self._fdf else "PDF"
        out.write(f"%{marker}-{version_text}".encode("iso-8859-1"))
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

    def _bump_version_for_compress(self, doc: COSDocument) -> None:
        """Raise the document's PDF version to the compression minimum (1.6),
        mirroring ``COSWriter.doWriteHeader``'s ``isCompress()`` branch.

        Upstream bumps both ``pdDocument.setVersion`` and ``doc.setVersion`` to
        ``max(current, MINIMUM_SUPPORTED_VERSION)``. ``PDDocument.setVersion``
        writes ``/Version`` into the document catalog when the header version is
        already >= 1.4 (otherwise it bumps only the COSDocument header). We
        replicate both effects directly on the COS layer: the catalog dict is
        reached via the trailer's ``/Root`` (resolving an indirect reference)."""
        from .compress.cos_writer_compression_pool import (
            COSWriterCompressionPool,
        )

        minimum = COSWriterCompressionPool.MINIMUM_SUPPORTED_VERSION
        header_version = doc.get_version()

        # Catalog-version side, mirroring ``PDDocument.setVersion(max(pdVersion,
        # minimum))``. ``PDDocument.getVersion()`` is ``max(catalogVersion,
        # headerVersion)`` (catalog /Version only counts when headerVersion >=
        # 1.4); ``setVersion`` then writes /Version into the catalog (for header
        # version >= 1.4) iff the new version exceeds the current effective one.
        trailer = doc.get_trailer()
        catalog = None
        if trailer is not None:
            root = trailer.get_item(COSName.ROOT)
            if isinstance(root, COSObject):
                root = root.get_object()
            if isinstance(root, COSDictionary):
                catalog = root

        catalog_version = -1.0
        if catalog is not None and header_version >= 1.4:
            existing = catalog.get_item(_VERSION_NAME)
            if isinstance(existing, COSName):
                try:
                    catalog_version = float(existing.get_name())
                except ValueError:
                    catalog_version = -1.0

        effective_version = (
            max(catalog_version, header_version)
            if header_version >= 1.4
            else header_version
        )
        new_version = max(effective_version, minimum)
        if new_version > effective_version and header_version >= 1.4 and catalog is not None:
            catalog.set_item(
                _VERSION_NAME,
                COSName.get_pdf_name(self._format_version(new_version)),
            )

        # Header side (doc.setVersion): always raise the COSDocument header
        # version to the compression minimum.
        if header_version < minimum:
            doc.set_version(minimum)

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
        if id(obj) in self._objects_to_write.ids:
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
        elif self._object_stream:
            # Compressed xref-stream full save: the whole graph is pre-keyed
            # by ``_collect_indirect_objects`` *before* any emit, so an actual
            # that has a key but was never queued/emitted must still be
            # queueable here. Gate the duplicate-skip on the real "already
            # emitted this pass" signal (``_emitted_actual_ids``) rather than
            # mere key presence (which the pre-pass sets for everything).
            if (
                actual is not None
                and id(actual) in self._emitted_actual_ids
            ):
                return
        else:
            # In plain full-save mode, an actual that already has a key has
            # already been queued under its first sighting — skip the
            # duplicate. (No pre-pass keys objects ahead of emission here, so
            # key presence is a faithful "already seen" signal.)
            if actual is not None and id(actual) in self._object_keys:
                return

        self._objects_to_write.append(obj)
        if actual is not None:  # pragma: no branch
            # Defensive: the only call sites reach here with actual already
            # resolved via get_object() — never None.
            self._actuals_added.add(id(actual))

    def _do_write_object(self, obj: COSBase) -> None:
        # Skip dangling references (matches upstream).
        if isinstance(obj, COSObject) and obj.get_object() is None:
            return
        # Object-stream packing: any object that has been packed into an
        # ObjStm must NOT also be emitted as a free-standing indirect frame
        # (the xref stream points at its in-objstm location instead).
        actual_for_skip: COSBase | None = (
            obj.get_object() if isinstance(obj, COSObject) else obj
        )
        if (
            actual_for_skip is not None
            and id(actual_for_skip) in self._packed_object_ids
        ):
            self._written_objects.add(id(obj))
            return
        # Idempotency on the resolved actual: the compressed xref-stream path
        # drives the top-level emit explicitly off the pre-pass key table, but
        # serialising each top-level object still routes references through the
        # main visitor (which queues them). Guarding on the actual id keeps a
        # referenced-then-explicitly-listed object from being emitted twice —
        # each indirect frame is written exactly once regardless of how it was
        # reached.
        if (
            actual_for_skip is not None
            and id(actual_for_skip) in self._emitted_actual_ids
        ):
            self._written_objects.add(id(obj))
            return
        self._written_objects.add(id(obj))
        if actual_for_skip is not None:
            self._emitted_actual_ids.add(id(actual_for_skip))
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

    def _mint_fresh_object_key(self) -> COSObjectKey:
        """Return a never-before-used ``(num, 0)`` key, advancing
        ``self._number`` past any declared keys already in flight.

        The plain ``self._number += 1`` pattern works for the classic
        full-save path because every actual is funneled through
        :py:meth:`_get_object_key` first. For ObjStm and xref-stream
        paths we mint keys *outside* that funnel (we know we
        want a brand-new number for the synthetic stream), so we must
        check against ``_key_object`` to avoid colliding with any
        explicitly-declared ``COSObject(n, 0)`` numbers."""
        while True:
            self._number += 1
            candidate = COSObjectKey(self._number, 0)
            if candidate not in self._key_object:
                return candidate

    def _get_object_key(self, obj: COSBase) -> COSObjectKey:
        """Return (and lazily assign) the indirect-object key for ``obj``.

        Faithful port of upstream ``COSWriter.getObjectKey(COSBase)``
        (PDFBox 3.0.7). The key is read from the *resolved actual's* own
        ``COSBase.getKey()`` — the (num, gen) stamped on the underlying
        object by the parser (``cos_parser`` / ``pdf_parser`` call
        ``set_key`` on the body) — NOT from a ``COSObject`` wrapper's
        declared number. A freshly-built ``COSObject(n, g, resolved=...)``
        wrapper that carries a declared number but whose actual has no key
        set is therefore RENUMBERED contiguously from 1, exactly as
        upstream does (upstream's ``computeIfAbsent(actual, ...)`` mints a
        fresh ``(++number, 0)`` for any actual not already keyed, and when
        that computed key differs from the wrapper key the computed one
        wins). This matters for the cross-reference table: a programmatic
        document with sparse object numbers is emitted as a single
        contiguous xref subsection, not a gap-filled sparse table
        (CHANGES.md Wave 1530).

        For parser-loaded documents the parser already stamped the actual's
        key, so re-saves preserve the original numbering — the same outcome
        as before, just sourced from the actual rather than the wrapper.
        """
        # The classic (traditional ``xref`` table + ``trailer``) full-save
        # path renumbers per upstream ``getObjectKey``: the key comes from the
        # *actual's* own ``get_key()`` (stamped by the parser on a re-save) and
        # any actual lacking one is minted a fresh contiguous ``(++number, 0)``
        # — a programmatic ``COSObject`` wrapper's declared number is discarded.
        # The object-stream / xref-stream / hybrid / incremental paths instead
        # honour the wrapper's declared ``(num, gen)`` because their type-2
        # entry geometry and ObjStm packability decisions depend on the
        # caller-declared numbering being preserved.
        honor_declared = (
            self._object_stream
            or self._xref_stream
            or self._hybrid_xref
            or self._incremental_update
        )
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

        if honor_declared:
            # Stream / compressed / incremental path: keep the caller's
            # declared (num, gen) verbatim (legacy behaviour).
            if declared_key is not None and declared_key.object_number > 0:
                key = declared_key
            else:
                key = self._mint_fresh_object_key()
        else:
            # Classic full-save: upstream reads the actual's OWN key (parser
            # stamps it on re-saves); a programmatic actual whose own
            # ``get_key()`` is None is renumbered contiguously, discarding any
            # wrapper-declared number — so a sparse object-number set collapses
            # to one contiguous xref subsection (CHANGES.md Wave 1530).
            actual_key = actual.get_key()
            if actual_key is not None and actual_key.object_number > 0:
                key = actual_key
            else:
                key = self._mint_fresh_object_key()

        # Avoid number collisions when honouring a declared key: bump a fresh
        # number if the chosen key is already bound to a different actual.
        while key in self._key_object and self._key_object[key] is not actual:
            key = self._mint_fresh_object_key()

        self._object_keys[id(actual)] = key
        self._key_holders[id(actual)] = actual
        self._key_object[key] = actual
        if not honor_declared:
            # Stamp the actual with its assigned key (upstream
            # ``actual.setKey``) so a subsequent re-save preserves it.
            actual.set_key(key)
        if isinstance(obj, COSObject):
            self._object_keys[id(obj)] = key
            self._key_holders[id(obj)] = obj
        return key

    # ---------- xref ----------

    def _do_write_xref_table(self) -> None:
        out = self._standard_output

        # Always include a free entry at object 0 (offset 0, gen 65535).
        # The upstream "fillGapsWithFreeEntries" path accounts for cases
        # where mid-numbers are missing; if object 0 is not already covered
        # by a gap, we emit the standard NULL_ENTRY free-list head.
        self._fill_gaps_with_free_entries()

        entries = sorted(self._xref_entries)
        self._startxref = out.get_position()

        out.write(XREF)
        out.write_eol()

        # ``entries`` is sorted and ``_build_ranges`` groups it into
        # contiguous runs, so each range consumes exactly the next ``count``
        # entries — a single running index avoids the O(ranges × entries)
        # rescan the per-range filter would incur.
        idx = 0
        for first, count in self._build_ranges(entries):
            self._write_xref_range(first, count)
            for entry in entries[idx : idx + count]:
                self._write_xref_entry(entry)
            idx += count

    def _fill_gaps_with_free_entries(self) -> None:
        # Collect normal entries (matches upstream's ``NormalXReference``
        # filter — recorded non-free entries describe concrete objects).
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
        out.write(_format_xref_table_offset(entry.offset))
        out.write(SPACE)
        out.write(_format_xref_table_generation(entry.key.generation_number))
        out.write(SPACE)
        out.write(XREF_FREE if entry.free else XREF_USED)
        # Each xref entry must end with a 2-byte EOL so the row is exactly
        # 20 bytes — ISO 32000-1 §7.5.4.
        out.write_crlf()

    # ---------- xref-stream / object-stream output (§7.5.7, §7.5.8) ----------

    def _do_write_body_xref_stream(self, doc: COSDocument) -> None:
        """Body emission for the xref-stream path.

        Identical to ``_do_write_body`` in *what* gets reached, but:

        * if object-stream packing is enabled, non-stream indirect objects
          are routed through the ObjStm packer first (it emits one or more
          ``/Type /ObjStm`` indirect objects and records type-2 xref
          locations for the packed payloads).
        * the xref stream itself is emitted by the caller in
          ``_do_write_xref_stream`` after this method returns.
        """
        trailer = doc.get_trailer()
        root = info = encrypt = None
        if trailer is not None:
            root = trailer.get_item(COSName.ROOT)  # type: ignore[attr-defined]
            info = trailer.get_item(COSName.INFO)  # type: ignore[attr-defined]
            encrypt = trailer.get_item(COSName.ENCRYPT)  # type: ignore[attr-defined]

        if self._object_stream:
            # Mirror upstream ``COSWriter.doWriteBodyCompressed`` (PDFBox
            # 3.0.7, bytecode 0-554): the compression pool classifies every
            # reachable indirect object into top-level (stays a free-standing
            # indirect) vs object-stream (packed) BEFORE any byte is written,
            # so each object is emitted EXACTLY once. We achieve the same by
            # (1) walking the graph to assign keys without emitting,
            # (2) packing the eligible objects into ``/ObjStm`` streams (which
            #     records ``_packed_object_ids`` + ``_compressed_locations``),
            # (3) emitting the remaining (top-level) indirects — whose emit
            #     path skips anything already packed.
            # The previous order (emit everything, then pack) double-wrote
            # every packed object: once as a free-standing indirect, once
            # inside the ObjStm body, inflating the file ~30% (e.g. 91 KB vs
            # upstream's 69 KB on unencrypted.pdf).
            self._collect_indirect_objects(root, info, encrypt)
            self._pack_object_streams(doc)
            # Emit every TOP-LEVEL (non-packed) indirect object — the
            # ``topLevelObjects`` bucket upstream's pool produces. We packed
            # objects into ObjStm bodies via the compact ``COSWriterObjectStream``
            # writer, which emits nested indirects as ``N G R`` references
            # WITHOUT queuing them, so we can no longer rely on the visitor's
            # graph-walk to discover the referenced streams. Instead drive the
            # emit directly from the pre-pass key table, in ascending object
            # number (matches upstream's sorted ``topLevelObjects`` iteration,
            # ``doWriteBodyCompressed`` bytecode 239-299). Packed objects are
            # skipped (``_packed_object_ids``); the /Encrypt dict is held back
            # so it lands last like upstream.
            encrypt_actual = (
                encrypt.get_object() if isinstance(encrypt, COSObject) else encrypt
            )
            pending_ids = {id(s) for s in self._pending_object_streams}
            top_level_keys = sorted(
                (
                    k
                    for k, actual in self._key_object.items()
                    if id(actual) not in self._packed_object_ids
                    and actual is not encrypt_actual
                    and id(actual) not in pending_ids
                ),
                key=lambda k: (k.object_number, k.generation_number),
            )
            for key in top_level_keys:
                self._do_write_object(self._key_object[key])
            # Object streams are written AFTER the top-level objects
            # (upstream ``doWriteBodyCompressed`` order), then the /Encrypt
            # dict last (it is never packed).
            for objstm in self._pending_object_streams:
                self._do_write_object(objstm)
            self._pending_object_streams.clear()
            if encrypt is not None:
                self._add_object_to_write(encrypt)
            self._do_write_objects()
            return

        if trailer is not None:
            if root is not None:
                self._add_object_to_write(root)
            if info is not None:
                self._add_object_to_write(info)
            self._do_write_objects()
            if encrypt is not None:
                self._add_object_to_write(encrypt)
            self._do_write_objects()
        else:
            self._do_write_objects()

    def _collect_indirect_objects(self, *roots: COSBase | None) -> None:
        """Non-emitting graph walk that assigns an object key to every
        reachable indirect object, populating ``_key_object`` /
        ``_object_keys`` so :py:meth:`_pack_object_streams` can run BEFORE
        any indirect frame is written.

        Discovery mirrors the byte-emitting visitor and upstream
        ``COSWriterCompressionPool.addStructure`` / ``filterElement``: an
        indirect object is a ``COSObject`` or a non-direct
        ``COSDictionary`` / ``COSArray``; we recurse into the values of
        dictionaries and the elements of arrays. Keys are minted through
        :py:meth:`_get_object_key`, so declared source numbers are
        preserved (and only un-numbered objects draw a fresh number) —
        identical to what the subsequent emit pass would assign, just
        without writing bytes.
        """
        seen: set[int] = set()
        stack: list[COSBase] = [r for r in roots if r is not None]
        while stack:
            current = stack.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            actual: COSBase | None
            if isinstance(current, COSObject):
                actual = current.get_object()
                if actual is None:
                    continue
                self._get_object_key(current)
            elif isinstance(current, (COSDictionary, COSArray)) and not current.is_direct():
                actual = current
                self._get_object_key(current)
            elif isinstance(current, (COSDictionary, COSArray)):
                actual = current
            else:
                continue
            if isinstance(actual, COSArray):
                stack.extend(v for v in list(actual) if v is not None)
            elif isinstance(actual, COSDictionary):
                stack.extend(v for v in actual.values() if v is not None)

    def _pack_object_streams(self, doc: COSDocument) -> None:
        """Bundle eligible non-stream indirect objects into one or more
        ``/Type /ObjStm`` streams (PDF 32000-1 §7.5.7).

        Each ObjStm carries up to the PDFBox default
        ``CompressParameters.DEFAULT_OBJECT_STREAM_SIZE`` payloads. Wire format:

        * dictionary entries: ``/Type /ObjStm /N <count> /First <offset>
          /Filter /FlateDecode /Length ...``
        * body: the index header (whitespace-separated ``<obj_num>
          <byte_offset>`` pairs covering ``N`` objects), then the
          concatenated object bodies starting at ``/First``.

        For each packed object we record ``id(actual) → (objstm_num, idx)``
        so :py:meth:`_do_write_xref_stream` knows to emit a type-2 entry
        for it; the regular indirect-frame emission in
        :py:meth:`_do_write_object` is suppressed via ``_packed_object_ids``.
        """
        # Resolve the document catalog (/Root) so it can be excluded from
        # packing — upstream ``COSWriterCompressionPool.addObjectToPool``
        # forces ``document.getTrailer().getCOSDictionary(ROOT)`` to the
        # top-level bucket (bytecode 102-117), keeping the catalog a
        # free-standing indirect.
        self._root_dict_id = None
        trailer = doc.get_trailer()
        if trailer is not None:
            root = trailer.get_cos_dictionary(COSName.ROOT)  # type: ignore[attr-defined]
            if root is not None:
                self._root_dict_id = id(root)

        # Exclude the complete /Encrypt subtree from packing. The reader
        # must be able to construct the security handler (which may need
        # indirect children of the encryption dictionary, e.g. /CF) before
        # it can decrypt an ObjStm body.
        self._encrypt_subtree_ids = set()
        if trailer is not None:
            encrypt_entry = trailer.get_item(COSName.ENCRYPT)  # type: ignore[attr-defined]
            if encrypt_entry is not None:
                self._collect_reachable_ids(
                    encrypt_entry, self._encrypt_subtree_ids
                )

        # Build the VALUE-keyed pool of indirect scalars. Upstream's
        # ``COSObjectPool`` registers every pooled object in a
        # ``HashMap<COSBase, COSObjectKey>``; for the value-hashed scalar types
        # (string / integer / float / name / boolean) this means a direct
        # occurrence of a value-equal scalar inside a packed container is
        # emitted as a reference to the registered indirect, not inlined. We
        # mirror that by recording each genuinely-indirect scalar value here,
        # keeping the LOWEST object number when two indirects share a value
        # (deterministic stand-in for upstream's first-``put``-wins on the
        # structure walk). Containers stay identity-keyed via ``_object_keys``.
        self._objstm_value_pool = {}
        for key, actual in sorted(
            self._key_object.items(),
            key=lambda kv: (kv[0].object_number, kv[0].generation_number),
        ):
            if (
                isinstance(actual, _VALUE_KEYED_POOL_TYPES)
                and actual not in self._objstm_value_pool
            ):
                self._objstm_value_pool[actual] = key

        candidates: list[tuple[COSObjectKey, COSBase]] = []
        for key, actual in self._key_object.items():
            if id(actual) in self._packed_object_ids:
                continue
            if not self._is_packable(actual, key):
                continue
            # Generation must be 0 — type-2 entries can't represent
            # non-zero generations (the second field is the ObjStm number,
            # the third is the index, and gen is implicitly 0 per spec).
            if key.generation_number != 0:
                continue
            candidates.append((key, actual))

        if not candidates:
            return

        # Stable order: by object number ascending — matches what the
        # reader will reconstruct.
        candidates.sort(key=lambda kv: kv[0].object_number)

        for chunk_start in range(0, len(candidates), self._object_stream_size):
            chunk = candidates[
                chunk_start : chunk_start + self._object_stream_size
            ]
            self._emit_one_object_stream(chunk)

    def _collect_reachable_ids(self, value: Any, out: set[int]) -> None:
        """Record ``id()`` of every ``COSBase`` reachable from ``value``
        (resolving indirect references, cycle-safe). Used to keep the
        /Encrypt subtree out of ObjStm packing."""
        if isinstance(value, COSObject):
            value = value.get_object()
        if value is None or id(value) in out:
            return
        out.add(id(value))
        if isinstance(value, COSDictionary):
            for key in list(value.key_set()):
                self._collect_reachable_ids(value.get_item(key), out)
        elif isinstance(value, COSArray):
            for item in value:
                self._collect_reachable_ids(item, out)

    def _is_packable(self, actual: COSBase, key: COSObjectKey) -> bool:
        """Per ISO 32000-1 §7.5.7: streams cannot be inside another
        stream, the /Encrypt dict — and every indirect object reachable
        from it, e.g. an indirect ``/CF`` crypt-filter dictionary — can
        never be packed (the reader needs the complete encryption
        dictionary before it can decrypt anything, and an ObjStm body is
        itself encrypted), and signature dictionaries rely on the
        on-disk byte range so packing would invalidate the signature."""
        if isinstance(actual, COSStream):
            return False
        if (
            self._encrypt_dict_id is not None
            and id(actual) == self._encrypt_dict_id
        ):
            return False
        if id(actual) in self._encrypt_subtree_ids:
            return False
        if (
            getattr(self, "_root_dict_id", None) is not None
            and id(actual) == self._root_dict_id
        ):
            # The /Root catalog is forced to top-level upstream
            # (``COSWriterCompressionPool.addObjectToPool`` excludes
            # ``trailer.getCOSDictionary(ROOT)`` from the object-stream
            # bucket), so it is never packed.
            return False
        if isinstance(actual, COSDictionary):
            type_name = actual.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
            if isinstance(type_name, COSName) and type_name.name in (
                "Sig",
                "DocTimeStamp",
            ):
                return False
        return True

    def _emit_one_object_stream(
        self, chunk: list[tuple[COSObjectKey, COSBase]]
    ) -> None:
        """Pack ``chunk`` into a single ObjStm and emit it as an
        indirect object. Records compressed-locations for each packed
        object so the xref stream can resolve them."""
        # Serialise each packed object's body with the upstream-faithful
        # COMPACT writer ``COSWriterObjectStream`` (PDFBox 3.0.7
        # ``writeObjectsToStream`` / ``writeObject``), NOT the main visitor.
        # The main ``COSWriter`` visitor pretty-prints dictionaries with a
        # newline after ``<<`` and after each entry (``<<\n/Contents 2 0 R\n
        # ...``); upstream packs objects compactly with single-space
        # separators and trailing spaces (``<</Contents 2 0 R /CropBox [0.0
        # 0.0 612.0 792.0 ] ...``). Using the compact writer makes the
        # decoded ObjStm body byte-identical to PDFBox's, leaving only the
        # deflate-compressed envelope (zlib vs java.util.zip.Deflater) as the
        # residual divergence. Nested indirect references are resolved
        # through a thin pool shim over the writer's key tables. Because the
        # compact writer emits nested indirects as ``N G R`` references WITHOUT
        # queuing them for emission, the caller drives the top-level emit
        # directly off the pre-pass key table (see
        # ``_do_write_body_xref_stream``) rather than relying on visitor-side
        # graph discovery.
        # Lazy import — ``cos_writer_object_stream`` imports ``COSWriter`` at
        # call time, so importing it at module top would be cyclic.
        from pypdfbox.pdfwriter.compress.cos_writer_object_stream import (
            COSWriterObjectStream,
        )

        pool_shim = _ObjStmPoolShim(self._object_keys, self._objstm_value_pool)
        objstm_writer = COSWriterObjectStream(pool_shim)
        bodies: list[bytes] = []
        for _key, actual in chunk:
            buf = io.BytesIO()
            objstm_writer.write_object(buf, actual, top_level=True)
            bodies.append(buf.getvalue())

        # Build the index header EXACTLY as upstream
        # ``COSWriterObjectStream.writeObjectsToStream`` (PDFBox 3.0.7): for
        # each object it writes ``<obj_num><SPACE><offset><SPACE>`` (a trailing
        # space after every pair, including the last). ``/First`` is the byte
        # length of that whole header — so the first body begins right after
        # the final trailing space, with no extra newline separator. Matching
        # this byte-for-byte (rather than the previous space-joined +
        # trailing-``\n`` form) makes the decoded ObjStm body identical to
        # PDFBox's.
        index_blob = bytearray()
        running = 0
        for (key, _), body in zip(chunk, bodies, strict=False):
            index_blob += f"{key.object_number} {running} ".encode("ascii")
            running += len(body)
        first_offset = len(index_blob)
        payload = bytes(index_blob) + b"".join(bodies)

        # Mint a fresh object number for the ObjStm itself (skip past any
        # declared keys that haven't been ``_get_object_key``-funneled).
        objstm_key = self._mint_fresh_object_key()

        # Build the COSStream wrapper. ``set_data(..., FlateDecode)``
        # compresses on commit and sets /Filter; we then add the §7.5.7
        # required keys.
        objstm = COSStream()
        objstm.set_data(payload, [_FLATE_DECODE_NAME])
        objstm.set_item(COSName.TYPE, COSName.get_pdf_name("ObjStm"))  # type: ignore[attr-defined]
        objstm.set_int(COSName.get_pdf_name("N"), len(chunk))
        objstm.set_int(COSName.get_pdf_name("First"), first_offset)

        # Register the ObjStm in the writer's key tables so the xref pass
        # picks it up.
        self._object_keys[id(objstm)] = objstm_key
        self._key_holders[id(objstm)] = objstm
        self._key_object[objstm_key] = objstm

        # Record per-packed-object compressed locations BEFORE the actual
        # emit (so even if the emit raises, ``_do_write_object``'s skip-
        # set keeps in sync — and so the xref stream can see them). Each
        # packed object also gets a type-2 xref entry registered here —
        # mirroring upstream ``doWriteBodyCompressed``'s
        # ``addXRefEntry(new ObjectStreamXReference(i, key, obj, objStmKey))``
        # (bytecode 427-446): the packed object is never written as a
        # free-standing indirect, so this is the ONLY place its xref entry
        # is created. ``_do_write_xref_stream`` resolves the (objstm, index)
        # pair from ``_compressed_locations`` keyed on the resolved actual.
        for index, (pkey, actual) in enumerate(chunk):
            self._compressed_locations[id(actual)] = (objstm_key.object_number, index)
            self._packed_object_ids.add(id(actual))
            self._xref_entries.append(
                COSWriterXRefEntry(offset=0, key=pkey, obj=actual, free=False)
            )

        # Defer the byte emission of the ObjStm itself until AFTER the
        # top-level (free-standing) indirect objects have been written.
        # Upstream ``doWriteBodyCompressed`` writes the top-level objects
        # first (bytecode 239-299) and only then serialises + writes the
        # object streams (302-466). Emitting the ObjStm early would place
        # the large packed payload near the file start and push every
        # subsequent top-level stream's byte offset higher — on
        # unencrypted.pdf that pushed two type-1 offsets past 65535 and
        # widened ``/W`` from ``1 2 1`` to ``1 3 1``. The COSStream payload
        # is already committed above, so deferring only the placement keeps
        # the in-objstm relative offsets intact.
        self._pending_object_streams.append(objstm)

    def _do_write_xref_stream(
        self, doc: COSDocument, *, in_hybrid: bool = False
    ) -> None:
        """Emit the xref stream that subsumes the trailer (§7.5.8).

        Workflow:

        1. mint a fresh object number for the xref stream itself
        2. add a free-list head (object 0) + any gap entries
        3. compute /W field widths from the maximum offset
        4. pack each xref entry (free / type-1 / type-2) into the body
        5. wrap the body in a COSStream with /Type /XRef + trailer entries
        6. emit it as a normal indirect object — the existing
           ``visit_from_stream`` path runs FlateDecode + the encryption
           pipeline (if active) for us.

        When ``in_hybrid`` is ``True`` (PDF 32000-1 §7.5.8.4 hybrid layout):

        * skip the gap-filling pass (the subsequent traditional xref
          table emit will run it itself, and double-running would emit
          duplicate free-list entries),
        * publish the xref stream's offset into
          ``self._hybrid_xref_stm_offset`` instead of clobbering
          ``self._startxref`` (which must end up pointing at the
          *traditional* xref table for legacy readers).
        """
        out = self._standard_output

        # 1. Fresh number for the xref stream object.
        xref_key = self._mint_fresh_object_key()

        # 2. Build the table of (objnum, type, field2, field3, is_free) tuples.
        # Type 1 = uncompressed (offset, gen)
        # Type 2 = compressed (objstm_num, index_in_objstm)
        #
        # Unlike the traditional ``xref`` table, the xref-STREAM path mirrors
        # ``org.apache.pdfbox.pdfparser.PDFXRefStream`` (PDFBox 3.0.7), which
        # does NOT fill inter-object gaps with explicit free entries. Its
        # ``streamData`` carries only the real entries fed via ``addEntry``
        # (type-1 uncompressed + type-2 compressed); the single object-0
        # ``FreeXReference.NULL_ENTRY`` leading row is emitted by
        # ``writeStreamData`` and object 0 is seeded into ``getIndexEntry``'s
        # TreeSet, but no per-gap free rows exist. Filling gaps here would
        # both bloat the body (one extra fixed-width row per missing object
        # number) and collapse the otherwise-sparse multi-run ``/Index`` into
        # a single dense run — the exact divergence this path used to carry
        # (``PDFXRefStream.addEntry`` bytecode 0-58; ``getIndexEntry`` 0-170).
        # Note: we intentionally do not call ``_fill_gaps_with_free_entries``
        # in either the full or hybrid xref-stream sub-path.
        records: list[tuple[int, int, int, int, bool]] = []
        for entry in self._xref_entries:
            if entry.free:
                # Defensive: the xref-stream path no longer seeds free
                # entries, but if a caller pre-staged one we drop it — only
                # the implicit object-0 NULL row belongs in an xref stream.
                continue
            objnum = entry.key.object_number
            actual = (
                entry.obj.get_object()
                if isinstance(entry.obj, COSObject)
                else entry.obj
            )
            comp = (
                self._compressed_locations.get(id(actual))
                if actual is not None
                else None
            )
            if comp is not None:
                objstm_num, idx = comp
                records.append((objnum, 2, objstm_num, idx, False))
            else:
                records.append(
                    (objnum, 1, entry.offset, entry.key.generation_number, False)
                )

        # 4. The xref stream's OWN entry is NOT placed in the body. Upstream
        # ``COSWriter.doWriteXRefInc`` (PDFBox 3.0.7) builds the stream via
        # ``PDFXRefStream.getStream()`` (which serialises ``streamData`` +
        # ``/Index``) and only THEN calls ``doWriteObject`` on the xref
        # stream object — so its ``NormalXReference`` is registered *after*
        # the body has been frozen and never feeds ``getStream``
        # (``doWriteXRefInc`` bytecode: getStream @140 precedes doWriteObject
        # @148). The result: ``/Size`` is highest+1 but the top object number
        # (the xref stream itself) is absent from ``/Index`` and the body,
        # and its offset never widens ``/W`` — the parser still finds the
        # stream via ``startxref``. Omitting it here keeps ``/W`` and the
        # ``/Index`` run-shape bit-identical to upstream (a self-entry whose
        # offset exceeds 65535 would otherwise force ``w2`` from 2 to 3).
        xref_offset = out.get_position()
        records.sort(key=lambda r: r[0])

        # 5. Compute /W widths exactly as ``PDFXRefStream.getWEntry`` does
        # (PDFBox 3.0.7 ``org.apache.pdfbox.pdfparser.PDFXRefStream``,
        # bytecode getWEntry 0-126): each field width is the byte count of the
        # MAX value in that column across ``streamData``, and a column whose
        # max is 0 yields width **0** (``while (w[i] > 0) { count++; w[i] >>= 8 }``).
        # The implicit object-0 ``FreeXReference.NULL_ENTRY`` leading row is
        # emitted by ``writeStreamData`` (always) but is NOT scanned — its gen
        # 65535 never widens w3. pypdfbox additionally fills inter-object gaps
        # with explicit free entries (gen 65535) for self-consistency; those
        # NULL-style generations are likewise excluded from the field-3 scan so
        # they don't force the over-wide column upstream never has. The
        # third column of a type-2 object-stream row carries the in-objstm
        # INDEX (``ObjectStreamXReference.getThirdColumnValue``) and IS scanned,
        # so a compressed save with object streams correctly widens w3 to that
        # max index while an all-uncompressed all-gen-0 save yields ``/W [1 3 0]``.
        max_field1 = max((t for _n, t, _f2, _f3, _fr in records), default=0)
        max_field2 = max((f2 for _n, _t, f2, _f3, _fr in records), default=0)
        max_field3 = max(
            (f3 for _n, _t, _f2, f3, fr in records if not fr), default=0
        )
        w1 = _xref_field_width(max_field1)
        w2 = _xref_field_width(max_field2)
        w3 = _xref_field_width(max_field3)

        # Pack the body. ``PDFXRefStream.writeStreamData`` (bytecode 0-44)
        # ALWAYS emits the object-0 ``FreeXReference.NULL_ENTRY`` row first
        # (type 0, next-free 0, gen 65535) regardless of whether object 0 is
        # in ``streamData``; the NULL row's gen 65535 is truncated to the
        # computed w3 (``writeNumber`` masks/right-aligns), so when w3 is 0 it
        # drops to zero bytes. The real entries (type-1/type-2) follow. Only
        # the real entries widen ``/W`` (``getWEntry`` never scans the NULL
        # row) — the NULL row is excluded from the max-scan above.
        body = bytearray()
        body.extend(_pack_unsigned(0, w1))
        body.extend(_pack_unsigned(0, w2))
        body.extend(
            _pack_unsigned(0xFFFF & ((1 << (8 * w3)) - 1) if w3 else 0, w3)
        )
        for _objnum, t, f2, f3, _fr in records:
            body.extend(_pack_unsigned(t, w1))
            body.extend(_pack_unsigned(f2, w2))
            body.extend(
                _pack_unsigned(f3 & ((1 << (8 * w3)) - 1) if w3 else 0, w3)
            )

        # /Index — sparse list of (first, count) ranges over the union of the
        # real object numbers and object 0 (``getIndexEntry`` seeds its TreeSet
        # with ``0L`` then ``addAll(objectNumbers)``, bytecode 21-44). The runs
        # are built over that union — no per-gap free rows means a genuinely
        # sparse multi-run ``/Index`` matching PDFBox.
        ranges = self._build_int_ranges([0, *[r[0] for r in records]])
        index_arr = COSArray()
        index_arr.set_direct(True)
        for first, count in ranges:
            index_arr.add(COSInteger.get(first))
            index_arr.add(COSInteger.get(count))

        # /W array.
        w_arr = COSArray()
        w_arr.set_direct(True)
        w_arr.add(COSInteger.get(w1))
        w_arr.add(COSInteger.get(w2))
        w_arr.add(COSInteger.get(w3))

        # Build the xref-stream COSStream.
        xref_stream = COSStream()
        xref_stream.set_data(bytes(body), [_FLATE_DECODE_NAME])
        xref_stream.set_item(COSName.TYPE, COSName.get_pdf_name("XRef"))  # type: ignore[attr-defined]
        # /Size = highest object number + 1.
        size_value = max((r[0] for r in records), default=0) + 1
        xref_stream.set_int(COSName.SIZE, size_value)  # type: ignore[attr-defined]
        xref_stream.set_item(COSName.get_pdf_name("W"), w_arr)
        xref_stream.set_item(COSName.get_pdf_name("Index"), index_arr)

        # Promote trailer entries (Root, Info, Encrypt, ID) into the xref-
        # stream dict. Per §7.5.8.4 the xref stream IS the trailer in this
        # mode — there is no separate ``trailer`` keyword.
        trailer = doc.get_trailer()
        if trailer is not None:
            for tkey in (
                COSName.ROOT,  # type: ignore[attr-defined]
                COSName.INFO,  # type: ignore[attr-defined]
                COSName.ENCRYPT,  # type: ignore[attr-defined]
                COSName.get_pdf_name("ID"),
            ):
                value = trailer.get_item(tkey)
                if value is not None:
                    xref_stream.set_item(tkey, value)
            # Ensure /ID stays direct (not promoted into a fresh indirect).
            id_arr = xref_stream.get_dictionary_object(COSName.get_pdf_name("ID"))
            if isinstance(id_arr, COSArray):  # pragma: no branch
                # Defensive: /ID is always a direct array here — the
                # branch above always seeds it from the trailer.
                id_arr.set_direct(True)

        # Register the xref stream's key BEFORE emit so any internal
        # reference attempts use the same number we minted above.
        self._object_keys[id(xref_stream)] = xref_key
        self._key_holders[id(xref_stream)] = xref_stream
        self._key_object[xref_key] = xref_stream

        # 6. Emit the xref stream as a regular indirect object. This goes
        # through ``visit_from_stream``; that visitor explicitly skips the
        # encryption pass for ``/Type /XRef`` streams (ISO 32000-2 §7.6.2:
        # "All cross-reference streams in the file shall not be
        # encrypted."), so the body stays plaintext-FlateDecoded and the
        # parser can read /Encrypt's byte offset out of it before any
        # security handler exists.
        #
        # Hybrid mode: ``startxref`` belongs to the traditional table that
        # will be emitted next, so stash the stream offset for the trailer
        # to publish via /XRefStm and leave ``_startxref`` alone.
        if in_hybrid:
            self._hybrid_xref_stm_offset = xref_offset
        else:
            self._startxref = xref_offset
        self._do_write_object(xref_stream)

    @staticmethod
    def _build_int_ranges(numbers: list[int]) -> list[tuple[int, int]]:
        """Group sorted object numbers into ``(first, count)`` runs.
        Mirrors :py:meth:`_build_ranges` but takes ints not entries."""
        nums = sorted(set(numbers))
        ranges: list[tuple[int, int]] = []
        if not nums:
            return ranges
        first = nums[0]
        count = 1
        for prev, cur in zip(nums, nums[1:], strict=False):
            if cur == prev + 1:
                count += 1
            else:
                ranges.append((first, count))
                first = cur
                count = 1
        ranges.append((first, count))
        return ranges

    # ---------- trailer ----------

    def _do_write_trailer(
        self, doc: COSDocument, *, xref_stm_offset: int | None = None
    ) -> None:
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
        # Full saves clear /Prev so we don't claim an incremental chain.
        trailer.remove_item(COSName.PREV)  # type: ignore[attr-defined]

        # A ``trailer`` keyword block follows a *traditional* ``xref`` table.
        # When the source document used a cross-reference stream, its trailer
        # COSDictionary IS that XRef stream's dictionary and still carries the
        # stream-only keys (/Type /XRef, /W, /Index, /Filter, /Length,
        # /DecodeParms). Those keys are illegal in a classic trailer (PDF
        # 32000-1 §7.5.5 lists the permitted trailer entries; §7.5.8 confines
        # /Type=/XRef, /W, /Index, /Filter, /Length, /DecodeParms to the xref
        # *stream* dictionary). Emitting them in a ``trailer`` block produces a
        # structurally malformed file — qpdf still recovers via the table but
        # strict readers may choke. PDFBox never hits this because its classic
        # path rebuilds a clean trailer; we strip them here to match.
        for stale in (
            COSName.TYPE,
            COSName.W,
            COSName.INDEX,
            COSName.FILTER,
            COSName.LENGTH,
            COSName.get_pdf_name("DecodeParms"),
        ):
            trailer.remove_item(stale)  # type: ignore[attr-defined]

        # Hybrid layout (§7.5.8.4): announce the parallel xref stream's
        # offset via /XRefStm so modern readers can use it; legacy readers
        # ignore the key and fall back to the traditional table at
        # ``startxref``. Outside hybrid mode we strip any stale /XRefStm
        # the source may have carried — full-save invalidates it.
        xref_stm_name = COSName.get_pdf_name("XRefStm")
        if xref_stm_offset is not None:
            trailer.set_int(xref_stm_name, xref_stm_offset)
        else:
            trailer.remove_item(xref_stm_name)

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
        # Generate two identical 32-byte halves. Upstream COSWriter
        # (PDFBox 3.0.7) feeds current time + file size + Info-dict entries
        # into a SHA-256 MessageDigest and uses the full, untruncated 32-byte
        # digest() for both /ID halves. We seed differently (wall-clock + a
        # random nonce) — the value is time-based either way — but must match
        # the *length*: emit the full SHA-256 digest, not a 16-byte slice, so
        # the synthesised /ID is structurally identical to PDFBox's.
        seed = f"{time.time_ns()}".encode("ascii") + secrets.token_bytes(16)
        digest = hashlib.sha256(seed).digest()
        first = COSString(digest)
        first.set_force_hex_form(True)
        second = COSString(digest)
        second.set_force_hex_form(True)
        new_arr = COSArray([first, second])
        new_arr.set_direct(True)
        trailer.set_item(COSName.get_pdf_name("ID"), new_arr)

    def _regenerate_changing_id(
        self, doc: COSDocument, first: COSBase | None
    ) -> COSArray:
        """Build a fresh ``/ID`` array for an incremental update.

        Per ISO 32000-1 §14.4 the first element (the *permanent* identifier)
        stays stable across updates while the second (the *changing*
        identifier) is regenerated so consumers can detect the file changed.
        Mirrors PDFBox's ``saveIncremental`` which preserves ``/ID[0]`` and
        emits a fresh SHA-256 digest for ``/ID[1]``.

        ``first`` is the source ``/ID[0]``; it is preserved byte-for-byte.
        The new ``/ID[1]`` is a 32-byte SHA-256 over the document state (size
        + the existing identifier + a wall-clock seed and random nonce). The
        exact digest input differs from upstream's MD5 recipe — only the
        contract (stable first, changed second) is load-bearing here."""
        if isinstance(first, COSString):
            first_string: COSString = COSString(first.get_bytes())
        else:
            # Defensive: source /ID[0] was not a string — synthesise one so we
            # never emit a malformed array. Shouldn't happen for a well-formed
            # source trailer.
            first_string = COSString(secrets.token_bytes(16))
        first_string.set_force_hex_form(True)

        trailer = doc.get_trailer()
        size = 0
        if trailer is not None:
            size_obj = trailer.get_dictionary_object(COSName.SIZE)  # type: ignore[attr-defined]
            if isinstance(size_obj, COSInteger):
                size = size_obj.value
        seed = (
            f"{size}".encode("ascii")
            + first_string.get_bytes()
            + f"{time.time_ns()}".encode("ascii")
            + secrets.token_bytes(16)
        )
        changing = hashlib.sha256(seed).digest()
        second = COSString(changing)
        second.set_force_hex_form(True)
        return COSArray([first_string, second])

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
        for b in obj.get_bytes():
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
            # Match upstream ``COSWriter.visitFromArray``: the separator is
            # guarded by ``if (i.hasNext())`` so there is NO trailing space
            # before the closing ``]``. Every 10th element gets an EOL
            # instead of a space (helps pretty-printing without breaking
            # parsers).
            if i < len(items) - 1:
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
                if not self._incremental_update:
                    # PDFBOX-3684: on a full save, write a nested /XObject or
                    # /Resources sub-dictionary as a DIRECT (inline) object to
                    # save file size — but never the dict's own self-named key
                    # (avoid a dictionary that references itself). Mirrors
                    # upstream ``COSWriter.visitFromDictionary``.
                    xobject_item = value.get_item(COSName.XOBJECT)
                    if xobject_item is not None and key != COSName.XOBJECT:
                        xobject_item.set_direct(True)
                    resources_item = value.get_item(COSName.RESOURCES)
                    if resources_item is not None and key != COSName.RESOURCES:
                        resources_item.set_direct(True)
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

        # Decrypt-on-write: a stream loaded from an encrypted document keeps
        # its on-disk ciphertext in the buffer until something decodes it
        # (pypdfbox decrypts lazily, just before the /Filter chain). If the
        # body was never decoded, ``create_raw_input_stream`` would hand us
        # the still-ciphertext bytes — and the encryption pass below would
        # encipher them a SECOND time (double encryption → FlateDecode
        # garbage on reload). Force the one-shot decrypt now so the snapshot
        # below is plaintext, then the encryption pass enciphers exactly
        # once. Mirrors upstream COSWriter, which sees handler-decrypted
        # bytes because PDFBox decrypts on access. No-op for plaintext
        # streams or streams already decoded.
        ensure_decrypted = getattr(obj, "ensure_decrypted", None)
        if callable(ensure_decrypted):
            ensure_decrypted()

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
        #
        # Cross-reference streams (``/Type /XRef``) are exempted per ISO
        # 32000-2 §7.6.2: "All cross-reference streams in the file shall
        # not be encrypted." They carry the byte offsets the parser uses
        # to locate /Encrypt itself, so encrypting them would create a
        # chicken-and-egg bootstrap: the FlateDecode pass would see
        # ciphertext and fail before the security handler could ever be
        # built. Skipping them here keeps the writer's output round-
        # trippable through the parser's eager-decrypt path.
        type_name = obj.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
        is_xref_stream = (
            isinstance(type_name, COSName) and type_name.name == "XRef"
        )
        # /Type /Metadata streams stay cleartext on disk when the active
        # security handler has /EncryptMetadata=false (PDF 32000-1 §7.6.3.2
        # /EncryptMetadata note: "if false, the document's /Metadata
        # stream(s) shall be passed through to the document unchanged").
        # Without this exemption a writer that obeys ``/EncryptMetadata
        # false`` only in the key-derivation step would still emit
        # ciphertext metadata, and any external indexer / search engine
        # trying to read the cleartext catalog would see scrambled bytes
        # — exactly the regression /EncryptMetadata false is designed to
        # avoid. (Wave 1367 latent-bug fix.)
        is_metadata_stream = (
            isinstance(type_name, COSName) and type_name.name == "Metadata"
        )
        skip_metadata_encrypt = is_metadata_stream and (
            self._security_handler is not None
            and not bool(
                getattr(
                    self._security_handler, "is_encrypt_metadata", lambda: True
                )()
            )
        )
        if (
            self._security_handler is not None
            and self._current_object_key is not None
            and not self._in_encrypt_subtree
            and not is_xref_stream
            and not skip_metadata_encrypt
        ):
            raw = self._security_handler.encrypt_stream(
                raw,
                self._current_object_key.object_number,
                self._current_object_key.generation_number,
            )

        # Update /Length to match what we'll actually emit. Streams are
        # always indirect, so this is safe.
        #
        # Upstream invariant: ``/Length`` is the FIRST dictionary entry. The
        # PDFBox ``COSStream()`` constructor seeds ``setInt(COSName.LENGTH, 0)``
        # before anything else, and the parser updates that seeded entry
        # IN PLACE (keeping its leading position) even when the source file
        # spells ``/Length`` after ``/Type``. pypdfbox's ``COSStream`` does not
        # carry a ``/Length`` entry until the body is committed, so a
        # freshly-built or parsed stream can end up with ``/Length`` in a
        # trailing position. Move it to the front here so the emitted dictionary
        # matches upstream byte-for-byte (``<< /Length N /Type ... >>``). The
        # writer is the right place: COSStream's ``/Length``-absent state is
        # load-bearing elsewhere (length queries return -1, parser
        # commit hooks), so the reorder is applied only at serialization time.
        obj.remove_item(COSName.LENGTH)  # type: ignore[attr-defined]
        length_value = COSInteger.get(len(raw))
        existing_items = list(obj.entry_set())  # type: ignore[attr-defined]
        obj.clear()  # type: ignore[attr-defined]
        obj.set_item(COSName.LENGTH, length_value)  # type: ignore[attr-defined]
        for entry_key, entry_value in existing_items:
            obj.set_item(entry_key, entry_value)  # type: ignore[attr-defined]

        # Emit the dictionary first. For xref streams the dict subsumes
        # the trailer — its /ID strings must stay cleartext (the standard
        # security handler folds /ID[0] into the file-encryption-key
        # derivation, so encrypting it would make the document
        # unreadable). The regular trailer-emit path bypasses
        # ``visit_from_string``'s encryption branch by leaving
        # ``_current_object_key`` at None; xref streams ARE indirect, so
        # we instead flip ``_in_encrypt_subtree`` for the dict block.
        previous_in_enc = self._in_encrypt_subtree
        if is_xref_stream:
            self._in_encrypt_subtree = True
        try:
            self.visit_from_dictionary(obj)
        finally:
            self._in_encrypt_subtree = previous_in_enc

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
        """Format a float for PDF output, byte-for-byte matching upstream
        ``COSFloat.formatString`` (PDFBox 3.0.7).

        PDFBox stores the value as an IEEE-754 ``float`` and serialises it
        via ``Float.toString`` (shortest round-tripping single-precision
        decimal), keeping that string verbatim unless it carries an
        exponent — in which case it expands to plain notation with trailing
        zeros stripped. Both branches live in the shared
        :func:`pypdfbox.cos.cos_float.format_float32`, which ``COSFloat``'s own
        ``write_pdf`` path also calls — one implementation, no drift. The
        classic divergence this fixes: ``%g``-on-the-double exposed float32
        representation noise (e.g. ``0.1`` → ``0.1000000015``); the float32
        shortest-digit search recovers PDFBox's ``0.1``."""
        if value != value:  # NaN guard — PDFs cannot encode NaN.
            raise ValueError("cannot serialize NaN as a PDF number")
        return format_float32(value).encode("iso-8859-1")

    @staticmethod
    def format_float_value(obj: COSFloat) -> bytes:
        """Prefer the original parsed text (round-trip fidelity) when set;
        else fall back to ``format_float``."""
        original = obj.get_original_form()
        if original is not None:
            return original.encode("iso-8859-1")
        return COSWriter.format_float(obj.value)

    @staticmethod
    def write_string(
        string: COSString | bytes | bytearray | memoryview,
        output: Any,
    ) -> None:
        """Serialize ``string`` as either a literal ``(...)`` or hex
        ``<...>`` PDF string. Matches upstream ``COSWriter.writeString``.

        Two upstream overloads share this entry point:

        * ``writeString(COSString, OutputStream)`` — honours
          :py:meth:`COSString.is_force_hex_form`.
        * ``writeString(byte[], OutputStream)`` — always writes literal
          unless the bytes themselves are non-ASCII / contain EOL bytes.

        ``output`` may be a :class:`COSStandardOutputStream` or any
        ``write(bytes)`` sink (mirrors upstream's ``OutputStream`` accept
        signature)."""
        if isinstance(string, COSString):
            data = string.get_bytes()
            force_hex = string.is_force_hex_form()
        elif isinstance(string, (bytes, bytearray, memoryview)):
            data = bytes(string)
            force_hex = False
        else:
            raise TypeError(
                "write_string expects a COSString or bytes-like input; "
                f"got {type(string).__name__}"
            )
        is_ascii = True
        if not force_hex:
            for b in data:
                # bytes >= 0x80 → non-ASCII; also avoid CR/LF to dodge EOL
                # ambiguity inside literal strings (PDFBOX-3107).
                if b >= 0x80 or b in (0x0D, 0x0A):
                    is_ascii = False
                    break
        # Branch on the output API surface so callers can pass either a
        # ``COSStandardOutputStream`` (writeByte support) or a plain
        # ``write(bytes)`` sink. The byte-by-byte path is hot when escaping
        # literal-form payloads, so we cache the resolved write function.
        write_byte = getattr(output, "write_byte", None)

        def _emit_byte(b: int) -> None:
            if write_byte is not None:
                write_byte(b)
            else:
                output.write(bytes((b,)))

        if is_ascii and not force_hex:
            output.write(b"(")
            for b in data:
                if b in (0x28, 0x29, 0x5C):  # ( ) \
                    output.write(b"\\")
                    _emit_byte(b)
                else:
                    _emit_byte(b)
            output.write(b")")
        else:
            output.write(b"<")
            output.write(data.hex().upper().encode("ascii"))
            output.write(b">")
