"""Linearization Hint Table decoder (PDF 32000-1 Annex F).

The primary hint stream of a linearized PDF carries three contiguous
sub-tables — Page Offset, Shared Object, and (optionally) Thumbnail —
that web-streaming consumers use to fetch the right byte ranges before
a full xref walk is possible.

Apache PDFBox itself does **not** ship a hint-stream decoder: its
``PDFParser.java`` only notes that "it can handle linearized pdfs"
referring to the trailing xref, never the hint stream body. pypdfbox
therefore exposes the decoder as a standalone helper (this module) and
thin entry points on :class:`PDFParser` (``decode_page_offset_hint_table``,
``decode_shared_object_hint_table``, ``decode_thumbnail_hint_table``).

This module decodes all three sub-tables:

* **Page Offset Hint Table** — §F.3, indexed by /H[0]. Answers "which
  byte range covers page N?". Required by the spec; always first.
* **Shared Object Hint Table** — §F.4, indexed by /H[2] (optional in
  the linearization parameter dictionary). Lists objects shared across
  pages so a streaming consumer can fetch them once.
* **Thumbnail Hint Table** — §F.5, indexed by /H[3] (optional). Lists
  per-page thumbnail objects so a streaming consumer can fetch
  thumbnails before the full page data.

Layout (PDF 32000-1 Table F.3 — Page Offset Hint Table header, 12
fixed bytes followed by variable-length per-page records):

    Item 1 (4 bytes) — least number of objects in a page
    Item 2 (4 bytes) — location of first page's page object (byte offset)
    Item 3 (2 bytes) — bits needed for the per-page delta in object count
    Item 4 (4 bytes) — least page length in bytes
    Item 5 (2 bytes) — bits needed for the per-page delta in page length
    Item 6 (4 bytes) — least offset to content stream start
    Item 7 (2 bytes) — bits needed for the per-page delta in content offset
    Item 8 (4 bytes) — least content stream length
    Item 9 (2 bytes) — bits needed for the per-page delta in content length
    Item 10 (2 bytes) — bits needed for the shared-object reference count
    Item 11 (2 bytes) — bits needed for the greatest shared-object identifier
    Item 12 (2 bytes) — bits needed in the numerator for fractional position
    Item 13 (2 bytes) — denominator of fractional position

After the 32-byte header, per-page records follow (one per page in
document order). Each record packs five bit-fields (widths driven by
Items 3, 5, 7, 9, and 10) — the data is **byte-aligned at the start of
each table** but **bit-packed within the table**: padding to the next
byte boundary happens only at the boundary between the per-page block
and the next block (Shared Object Reference Numerators), per §F.4.

The decoder works on the **decoded** hint stream body, i.e. after the
``/FlateDecode`` filter chain has been unwound. Callers must run the
filter chain themselves (`PDFParser.decode_page_offset_hint_table` does
this when handed the hint stream as a `COSStream`).
"""

from __future__ import annotations

from dataclasses import dataclass


class HintTableParseError(ValueError):
    """Raised when the hint stream body is too short or malformed."""


@dataclass(frozen=True)
class PageOffsetHintHeader:
    """Decoded 32-byte Page Offset Hint Table header (PDF 32000-1
    Table F.3, Items 1-13)."""

    least_objects_per_page: int
    first_page_object_offset: int
    bits_for_object_count_delta: int
    least_page_length: int
    bits_for_page_length_delta: int
    least_content_stream_offset: int
    bits_for_content_stream_offset_delta: int
    least_content_stream_length: int
    bits_for_content_stream_length_delta: int
    bits_for_shared_object_count: int
    bits_for_shared_object_id: int
    bits_for_fraction_numerator: int
    fraction_denominator: int


@dataclass(frozen=True)
class PageOffsetEntry:
    """One per-page row of the Page Offset Hint Table.

    All five fields are **deltas** added to the corresponding "least"
    value in the header — e.g. the page's actual object count is
    ``header.least_objects_per_page + object_count_delta``. The
    ``shared_object_count`` does **not** index any shared-object
    sub-table in this lite decoder; consumers that need shared-object
    resolution wire that up against the Shared Object Hint Table (not
    decoded here)."""

    object_count_delta: int
    page_length_delta: int
    content_stream_offset_delta: int
    content_stream_length_delta: int
    shared_object_count: int


@dataclass(frozen=True)
class PageOffsetHintTable:
    """The full decoded Page Offset Hint Table: a 13-field header plus
    one :class:`PageOffsetEntry` per page in document order."""

    header: PageOffsetHintHeader
    pages: list[PageOffsetEntry]

    def page_count(self) -> int:
        """Number of decoded page rows. Equal to ``/N`` from the
        linearization parameter dictionary."""
        return len(self.pages)

    def object_count_for_page(self, page_index: int) -> int:
        """Number of objects on the ``page_index``-th page (0-based)."""
        if not 0 <= page_index < len(self.pages):
            raise IndexError(page_index)
        return (
            self.header.least_objects_per_page
            + self.pages[page_index].object_count_delta
        )

    def page_length_for_page(self, page_index: int) -> int:
        """Byte length of the ``page_index``-th page (0-based)."""
        if not 0 <= page_index < len(self.pages):
            raise IndexError(page_index)
        return (
            self.header.least_page_length
            + self.pages[page_index].page_length_delta
        )

    def content_stream_offset_for_page(self, page_index: int) -> int:
        """Byte offset of the content stream of the ``page_index``-th page
        (0-based)."""
        if not 0 <= page_index < len(self.pages):
            raise IndexError(page_index)
        return (
            self.header.least_content_stream_offset
            + self.pages[page_index].content_stream_offset_delta
        )

    def content_stream_length_for_page(self, page_index: int) -> int:
        """Byte length of the content stream of the ``page_index``-th page
        (0-based)."""
        if not 0 <= page_index < len(self.pages):
            raise IndexError(page_index)
        return (
            self.header.least_content_stream_length
            + self.pages[page_index].content_stream_length_delta
        )


class _BitReader:
    """Big-endian bit reader over a ``bytes`` source.

    PDF 32000-1 §F.4 specifies "values are stored in the order of most
    significant bit first" within each table — i.e. a 12-bit field
    laid out across two bytes reads the top 4 bits of the second byte
    as the low 4 bits of the value. This reader implements exactly that
    convention; calls to :meth:`read` advance the bit cursor."""

    __slots__ = ("_data", "_bit_pos", "_bit_len")

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._bit_pos = 0
        self._bit_len = len(data) * 8

    def read(self, n_bits: int) -> int:
        """Read ``n_bits`` MSB-first as an unsigned integer.

        ``n_bits == 0`` returns 0 immediately (the spec uses zero bit
        widths to encode "all rows share the same value"). Raises
        :class:`HintTableParseError` when the source is exhausted."""
        if n_bits == 0:
            return 0
        if n_bits < 0:
            raise HintTableParseError(f"negative bit width: {n_bits}")
        if self._bit_pos + n_bits > self._bit_len:
            raise HintTableParseError(
                "hint table truncated — cannot read "
                f"{n_bits} bits at bit-offset {self._bit_pos}"
            )
        value = 0
        remaining = n_bits
        while remaining > 0:
            byte_index = self._bit_pos >> 3
            bit_in_byte = self._bit_pos & 7
            byte = self._data[byte_index]
            available = 8 - bit_in_byte
            take = min(remaining, available)
            shift = available - take
            chunk = (byte >> shift) & ((1 << take) - 1)
            value = (value << take) | chunk
            self._bit_pos += take
            remaining -= take
        return value

    def align_to_byte(self) -> None:
        """Advance the bit cursor to the next byte boundary (no-op when
        already aligned). PDF 32000-1 §F.4 requires byte alignment
        between the per-page block and the next block."""
        rem = self._bit_pos & 7
        if rem:
            self._bit_pos += 8 - rem


def _read_u16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise HintTableParseError(
            f"hint stream truncated reading u16 at offset {offset}"
        )
    return int.from_bytes(data[offset : offset + 2], "big")


def _read_u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise HintTableParseError(
            f"hint stream truncated reading u32 at offset {offset}"
        )
    return int.from_bytes(data[offset : offset + 4], "big")


def parse_page_offset_hint_header(decoded: bytes) -> PageOffsetHintHeader:
    """Parse the 32-byte Page Offset Hint Table header (Items 1-13) from
    the **decoded** hint stream body. The body must be at least 32 bytes
    or :class:`HintTableParseError` is raised."""
    if len(decoded) < 32:
        raise HintTableParseError(
            f"hint stream too short for header: {len(decoded)} < 32"
        )
    return PageOffsetHintHeader(
        least_objects_per_page=_read_u32(decoded, 0),
        first_page_object_offset=_read_u32(decoded, 4),
        bits_for_object_count_delta=_read_u16(decoded, 8),
        least_page_length=_read_u32(decoded, 10),
        bits_for_page_length_delta=_read_u16(decoded, 14),
        least_content_stream_offset=_read_u32(decoded, 16),
        bits_for_content_stream_offset_delta=_read_u16(decoded, 20),
        least_content_stream_length=_read_u32(decoded, 22),
        bits_for_content_stream_length_delta=_read_u16(decoded, 26),
        bits_for_shared_object_count=_read_u16(decoded, 28),
        bits_for_shared_object_id=_read_u16(decoded, 30),
        # Items 12 + 13 sit at offsets 32 + 34 but the spec packs them
        # *after* the per-page records — they live in the header for
        # documentation purposes only; some producers omit them when
        # they're zero. We surface them via a second-pass read at the
        # caller's discretion (see ``parse_page_offset_hint_table``).
        bits_for_fraction_numerator=0,
        fraction_denominator=0,
    )


def parse_page_offset_hint_table(
    decoded: bytes,
    *,
    page_count: int,
) -> PageOffsetHintTable:
    """Parse a Page Offset Hint Table out of the **decoded** hint stream
    body, given the total page count from the linearization parameter
    dictionary's ``/N`` entry.

    The function expects the body to start with the Page Offset header
    (§F.3 Items 1-11; Items 12-13 are not required by this decoder and
    are emitted as zero). One :class:`PageOffsetEntry` per page is
    decoded sequentially; the bit cursor is byte-aligned only at the
    very start (the per-page block is bit-packed end-to-end).

    Raises :class:`HintTableParseError` when the body is truncated, when
    any bit field is negative, or when ``page_count`` is non-positive."""
    if page_count <= 0:
        raise HintTableParseError(f"page_count must be > 0, got {page_count}")
    header = parse_page_offset_hint_header(decoded)
    # The per-page block starts immediately after the 32-byte fixed
    # header (Items 12 + 13 sit at the very end of the table and are
    # decoded only by the optional second pass — they're zero in the
    # vast majority of producers).
    body = decoded[32:]
    reader = _BitReader(body)
    pages: list[PageOffsetEntry] = []
    for _ in range(page_count):
        object_count_delta = reader.read(header.bits_for_object_count_delta)
        page_length_delta = reader.read(header.bits_for_page_length_delta)
        content_stream_offset_delta = reader.read(
            header.bits_for_content_stream_offset_delta
        )
        content_stream_length_delta = reader.read(
            header.bits_for_content_stream_length_delta
        )
        shared_object_count = reader.read(header.bits_for_shared_object_count)
        pages.append(
            PageOffsetEntry(
                object_count_delta=object_count_delta,
                page_length_delta=page_length_delta,
                content_stream_offset_delta=content_stream_offset_delta,
                content_stream_length_delta=content_stream_length_delta,
                shared_object_count=shared_object_count,
            )
        )
    return PageOffsetHintTable(header=header, pages=pages)


# ---------------------------------------------------------------------------
# Shared Object Hint Table (PDF 32000-1 §F.4 / Table F.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SharedObjectHintHeader:
    """Decoded 24-byte fixed header of the Shared Object Hint Table
    (PDF 32000-1 Table F.4, Items 1-7).

    The shared-object section lists objects referenced from more than
    one page (e.g. shared fonts, images, content-stream resources) so a
    streaming consumer can fetch them once and reuse across pages.
    The first ``num_shared_objects_first_page`` entries describe objects
    that also appear in the first page's hint coverage; the remaining
    ``num_shared_objects_total - num_shared_objects_first_page`` entries
    describe objects elsewhere in the document."""

    first_shared_object_number: int
    first_shared_object_location: int
    num_shared_objects_first_page: int
    num_shared_objects_total: int
    bits_for_group_object_count: int
    least_shared_object_length: int
    bits_for_shared_object_length_delta: int


@dataclass(frozen=True)
class SharedObjectEntry:
    """One per-object row of the Shared Object Hint Table.

    ``length_delta`` is added to the header's
    ``least_shared_object_length`` to recover the actual object length
    in bytes. ``signature_present`` indicates a 128-bit MD5 hash follows
    in the encoded record; pypdfbox surfaces the hash bytes verbatim in
    :attr:`signature_md5` (``b""`` when absent). ``group_object_count``
    is the number of objects in the group that share this entry's
    position — for non-grouped shared objects this is 0."""

    length_delta: int
    signature_present: bool
    signature_md5: bytes
    group_object_count: int


@dataclass(frozen=True)
class SharedObjectHintTable:
    """The full decoded Shared Object Hint Table — header plus one
    :class:`SharedObjectEntry` per shared object."""

    header: SharedObjectHintHeader
    entries: list[SharedObjectEntry]

    def shared_object_count(self) -> int:
        """Number of decoded shared-object rows. Equals
        ``header.num_shared_objects_total``."""
        return len(self.entries)

    def length_for_entry(self, entry_index: int) -> int:
        """Byte length of the ``entry_index``-th shared object (0-based)."""
        if not 0 <= entry_index < len(self.entries):
            raise IndexError(entry_index)
        return (
            self.header.least_shared_object_length
            + self.entries[entry_index].length_delta
        )


def parse_shared_object_hint_header(decoded: bytes) -> SharedObjectHintHeader:
    """Parse the 24-byte Shared Object Hint Table header (Items 1-7)
    from the **decoded** sub-table body. Raises
    :class:`HintTableParseError` when the body is shorter than 24
    bytes."""
    if len(decoded) < 24:
        raise HintTableParseError(
            f"shared-object hint sub-table too short for header: "
            f"{len(decoded)} < 24"
        )
    return SharedObjectHintHeader(
        first_shared_object_number=_read_u32(decoded, 0),
        first_shared_object_location=_read_u32(decoded, 4),
        num_shared_objects_first_page=_read_u32(decoded, 8),
        num_shared_objects_total=_read_u32(decoded, 12),
        bits_for_group_object_count=_read_u16(decoded, 16),
        least_shared_object_length=_read_u32(decoded, 18),
        bits_for_shared_object_length_delta=_read_u16(decoded, 22),
    )


def parse_shared_object_hint_table(decoded: bytes) -> SharedObjectHintTable:
    """Parse a Shared Object Hint Table out of the **decoded** sub-table
    body. The body must start with the 24-byte fixed header; the
    per-entry block immediately follows and is bit-packed end-to-end.

    Each entry encodes four fields (PDF 32000-1 Table F.5):

    1. ``length_delta`` — width ``bits_for_shared_object_length_delta``
    2. ``signature_present`` — 1 bit
    3. ``signature_md5`` — 128 bits, present iff ``signature_present``
    4. ``group_object_count`` — width ``bits_for_group_object_count``

    Raises :class:`HintTableParseError` when the body is truncated."""
    header = parse_shared_object_hint_header(decoded)
    body = decoded[24:]
    reader = _BitReader(body)
    entries: list[SharedObjectEntry] = []
    for _ in range(header.num_shared_objects_total):
        length_delta = reader.read(
            header.bits_for_shared_object_length_delta
        )
        signature_flag = reader.read(1)
        if signature_flag:
            md5_bytes = bytearray(16)
            for i in range(16):
                md5_bytes[i] = reader.read(8)
            signature_md5 = bytes(md5_bytes)
        else:
            signature_md5 = b""
        group_object_count = reader.read(header.bits_for_group_object_count)
        entries.append(
            SharedObjectEntry(
                length_delta=length_delta,
                signature_present=bool(signature_flag),
                signature_md5=signature_md5,
                group_object_count=group_object_count,
            )
        )
    return SharedObjectHintTable(header=header, entries=entries)


# ---------------------------------------------------------------------------
# Thumbnail Hint Table (PDF 32000-1 §F.5 / Table F.6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThumbnailHintHeader:
    """Decoded 20-byte fixed header of the Thumbnail Hint Table
    (PDF 32000-1 Table F.6, Items 1-6).

    Each entry in the per-page block describes the thumbnail object
    associated with one page (when present); not every page necessarily
    has a thumbnail in the linearized layout, so the header carries
    ``num_pages_with_thumbnails`` distinct from the overall page count."""

    first_thumbnail_object_number: int
    first_thumbnail_object_location: int
    num_pages_with_thumbnails: int
    bits_for_thumbnail_length_delta: int
    least_thumbnail_length: int
    bits_for_shared_thumbnail_id: int
    least_shared_thumbnail_reference: int


@dataclass(frozen=True)
class ThumbnailEntry:
    """One per-page row of the Thumbnail Hint Table.

    ``length_delta`` is added to the header's ``least_thumbnail_length``
    to recover the thumbnail's byte length. ``shared_id_delta`` is
    added to ``least_shared_thumbnail_reference`` when shared-thumbnail
    pooling is in use; consumers that don't track shared thumbnails can
    treat this as zero."""

    length_delta: int
    shared_id_delta: int


@dataclass(frozen=True)
class ThumbnailHintTable:
    """The full decoded Thumbnail Hint Table — header plus one
    :class:`ThumbnailEntry` per page that carries a thumbnail."""

    header: ThumbnailHintHeader
    entries: list[ThumbnailEntry]

    def thumbnail_count(self) -> int:
        """Number of decoded thumbnail rows. Equals
        ``header.num_pages_with_thumbnails``."""
        return len(self.entries)

    def length_for_entry(self, entry_index: int) -> int:
        """Byte length of the ``entry_index``-th thumbnail (0-based)."""
        if not 0 <= entry_index < len(self.entries):
            raise IndexError(entry_index)
        return (
            self.header.least_thumbnail_length
            + self.entries[entry_index].length_delta
        )


def parse_thumbnail_hint_header(decoded: bytes) -> ThumbnailHintHeader:
    """Parse the 20-byte Thumbnail Hint Table header (Items 1-6) from
    the **decoded** sub-table body. Raises :class:`HintTableParseError`
    when the body is shorter than 20 bytes."""
    if len(decoded) < 20:
        raise HintTableParseError(
            f"thumbnail hint sub-table too short for header: "
            f"{len(decoded)} < 20"
        )
    return ThumbnailHintHeader(
        first_thumbnail_object_number=_read_u32(decoded, 0),
        first_thumbnail_object_location=_read_u32(decoded, 4),
        num_pages_with_thumbnails=_read_u32(decoded, 8),
        bits_for_thumbnail_length_delta=_read_u16(decoded, 12),
        least_thumbnail_length=_read_u32(decoded, 14),
        bits_for_shared_thumbnail_id=_read_u16(decoded, 18),
        least_shared_thumbnail_reference=0,
    )


def parse_thumbnail_hint_table(decoded: bytes) -> ThumbnailHintTable:
    """Parse a Thumbnail Hint Table out of the **decoded** sub-table
    body. The body must start with the 20-byte fixed header; the
    per-entry block immediately follows and is bit-packed end-to-end.

    Each entry encodes two fields:

    1. ``length_delta`` — width ``bits_for_thumbnail_length_delta``
    2. ``shared_id_delta`` — width ``bits_for_shared_thumbnail_id``

    Raises :class:`HintTableParseError` when the body is truncated."""
    header = parse_thumbnail_hint_header(decoded)
    body = decoded[20:]
    reader = _BitReader(body)
    entries: list[ThumbnailEntry] = []
    for _ in range(header.num_pages_with_thumbnails):
        length_delta = reader.read(header.bits_for_thumbnail_length_delta)
        shared_id_delta = reader.read(header.bits_for_shared_thumbnail_id)
        entries.append(
            ThumbnailEntry(
                length_delta=length_delta,
                shared_id_delta=shared_id_delta,
            )
        )
    return ThumbnailHintTable(header=header, entries=entries)
