"""Coverage-boost tests for ``CCITTFactory`` (wave 1323).

Targets the residual missing branches in
``pypdfbox.pdmodel.graphics.image.ccitt_factory``: ``extract_from_tiff``
error arms (truncated header, endianness mismatch, unsupported bytes,
bad magic, IFD tag-count overrun on both the skip-loop and main loop,
unsupported ``FillOrder``, unsupported ``Orientation``, T4 'uncompressed
mode' / 'fill bits' rejections, missing-compression and missing-strip
guards), and the happy-path branches that exercise the byte-typed tag
read, ``FillOrder=2`` bit-reversal, tile-offset (tags 324/325) parsing,
``Photometric=1`` BlackIs1 inference, and explicit Columns/Rows tags.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.graphics.image.ccitt_factory import extract_from_tiff


def _ifd_entries(tags: list[tuple[int, int, int, int]]) -> bytes:
    """Pack a sequence of ``(tag, type, count, val)`` IFD entries."""
    out = b""
    for tag, type_, count, val in tags:
        out += struct.pack("<HHII", tag, type_, count, val)
    return out


def _make_tiff_le(
    tags: list[tuple[int, int, int, int]],
    *,
    strip_offset: int = 0,
    strip_payload: bytes = b"",
) -> bytes:
    """Build a synthetic little-endian TIFF with the given IFD tags.

    Layout: header(8) + numtags(2) + tags(12*n) + next_ifd_offset(4),
    optionally followed by padding + ``strip_payload`` placed at
    ``strip_offset``.
    """
    hdr = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    body = struct.pack("<H", len(tags)) + _ifd_entries(tags) + struct.pack("<I", 0)
    if strip_offset == 0 or not strip_payload:
        return hdr + body
    base = len(hdr) + len(body)
    assert strip_offset >= base, (
        f"strip_offset {strip_offset} collides with IFD (base={base})"
    )
    return hdr + body + (b"\x00" * (strip_offset - base)) + strip_payload


# ---------------------------------------------------------------------------
# header-level guards
# ---------------------------------------------------------------------------


def test_extract_truncated_header_raises() -> None:
    """Short < 2 bytes — covers line 116."""
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(io.BytesIO(b"I"), io.BytesIO(), COSDictionary(), 0)


def test_extract_mismatched_endianness_bytes_raises() -> None:
    """First byte ``I`` but second byte ``M`` — covers line 121."""
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(io.BytesIO(b"IM"), io.BytesIO(), COSDictionary(), 0)


def test_extract_unsupported_endianness_raises() -> None:
    """Header bytes that match each other but aren't 'I' or 'M' — covers
    line 125."""
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(io.BytesIO(b"XX"), io.BytesIO(), COSDictionary(), 0)


def test_extract_bad_magic_number_raises() -> None:
    """Endianness valid but magic != 42 — covers the magic-number check."""
    blob = b"II" + struct.pack("<H", 99) + struct.pack("<I", 8)
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(io.BytesIO(blob), io.BytesIO(), COSDictionary(), 0)


# ---------------------------------------------------------------------------
# IFD-walk guards
# ---------------------------------------------------------------------------


def _huge_ifd_tiff() -> bytes:
    """Build a TIFF whose first IFD claims 51 tags — over the 50-tag cap."""
    n = 51
    hdr = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    ifd = (
        struct.pack("<H", n)
        + (b"\x00" * (12 * n))
        + struct.pack("<I", 0)
    )
    return hdr + ifd


def test_extract_numtags_over_fifty_in_main_loop_raises() -> None:
    """Main-loop numtags > 50 — covers line 145."""
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(
            io.BytesIO(_huge_ifd_tiff()), io.BytesIO(), COSDictionary(), 0
        )


def test_extract_numtags_over_fifty_in_skip_loop_raises() -> None:
    """Skip-loop numtags > 50 — covers line 134. ``number=1`` forces one
    iteration of the skip loop against the over-50 IFD."""
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(
            io.BytesIO(_huge_ifd_tiff()), io.BytesIO(), COSDictionary(), 1
        )


def test_extract_walks_past_end_of_chain_returns_early() -> None:
    """``number`` past the end of the IFD chain: next-IFD offset is 0
    inside the skip loop, function returns silently (out buffer stays
    empty). Exercises the ``return`` branch in the skip loop."""
    tiff = _make_tiff_le(
        [
            (259, 3, 1, 4),
            (273, 4, 1, 64),
            (279, 4, 1, 1),
        ],
        strip_offset=64,
        strip_payload=b"X",
    )
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(tiff), out, COSDictionary(), 1)
    assert out.getvalue() == b""


# ---------------------------------------------------------------------------
# tag-specific error arms
# ---------------------------------------------------------------------------


def test_extract_unsupported_fill_order_raises() -> None:
    """Tag 266 (FillOrder) with value != 1/2 — covers lines 186-188."""
    tiff = _make_tiff_le([(266, 3, 1, 99)])
    with pytest.raises(OSError, match="FillOrder 99 is not supported"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


def test_extract_unsupported_orientation_raises() -> None:
    """Tag 274 (Orientation) with value != 1 — covers lines 194-195."""
    tiff = _make_tiff_le([(274, 3, 1, 2)])
    with pytest.raises(OSError, match="Orientation 2 is not supported"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


def test_extract_t4_uncompressed_mode_raises() -> None:
    """Tag 292 (T4Options) bit 4 — covers lines 204-205."""
    tiff = _make_tiff_le([(292, 4, 1, 4)])
    with pytest.raises(OSError, match="uncompressed mode"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


def test_extract_t4_fill_bits_before_eol_raises() -> None:
    """Tag 292 (T4Options) bit 2 — covers lines 206-209."""
    tiff = _make_tiff_le([(292, 4, 1, 2)])
    with pytest.raises(OSError, match="fill bits before EOL"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


def test_extract_t4_two_dimensional_records_k_fifty() -> None:
    """Tag 292 bit 1 (2D) sets ``K=50`` — covers line 201-202."""
    tiff = _make_tiff_le(
        [
            (259, 3, 1, 3),
            (292, 4, 1, 1),
            (273, 4, 1, 96),
            (279, 4, 1, 2),
        ],
        strip_offset=96,
        strip_payload=b"AB",
    )
    params = COSDictionary()
    extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), params, 0)
    assert params.get_int("K", -1) == 50


def test_extract_missing_compression_tag_raises() -> None:
    """When tag 259 is absent ``k`` stays at -1000 — covers line 219."""
    tiff = _make_tiff_le(
        [
            (273, 4, 1, 96),
            (279, 4, 1, 1),
        ],
        strip_offset=96,
        strip_payload=b"x",
    )
    with pytest.raises(OSError, match="not CCITT T4 or T6 compressed"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


def test_extract_missing_strip_offset_raises() -> None:
    """No tag 273/324 → dataoffset stays 0 — covers line 221."""
    tiff = _make_tiff_le([(259, 3, 1, 4)])
    with pytest.raises(OSError, match="single tile/strip"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


# ---------------------------------------------------------------------------
# happy-path tag arms
# ---------------------------------------------------------------------------


def test_extract_records_columns_rows_and_blackis1() -> None:
    """Tags 256/257 set ``Columns``/``Rows``; tag 262 with val=1 sets
    ``BlackIs1`` — covers the assignment branches and the type=3 read."""
    tiff = _make_tiff_le(
        [
            (256, 3, 1, 99),  # Columns
            (257, 3, 1, 77),  # Rows
            (259, 3, 1, 4),
            (262, 3, 1, 1),  # photometric=1 → BlackIs1
            (273, 4, 1, 96),
            (279, 4, 1, 3),
        ],
        strip_offset=96,
        strip_payload=b"\xab\xcd\xef",
    )
    params = COSDictionary()
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(tiff), out, params, 0)
    assert params.get_int("Columns", 0) == 99
    assert params.get_int("Rows", 0) == 77
    assert params.get_boolean("BlackIs1", False) is True
    assert out.getvalue() == b"\xab\xcd\xef"


def test_extract_byte_type_tag_reads_one_byte() -> None:
    """A type=1 (byte) IFD entry reads one byte then discards 3 padding
    bytes — covers lines 159-164."""
    tiff = _make_tiff_le(
        [
            (262, 1, 1, 1),  # byte-type photometric
            (259, 3, 1, 4),
            (273, 4, 1, 96),
            (279, 4, 1, 1),
        ],
        strip_offset=96,
        strip_payload=b"Q",
    )
    params = COSDictionary()
    extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), params, 0)
    assert params.get_boolean("BlackIs1", False) is True


def test_extract_fill_order_two_reverses_bits() -> None:
    """FillOrder=2 applies the bit-reversal table — covers lines 231-232.
    A single payload byte ``0x01`` reverses to ``0x80``."""
    tiff = _make_tiff_le(
        [
            (259, 3, 1, 4),
            (266, 3, 1, 2),  # FillOrder=2 (LSB-first)
            (273, 4, 1, 96),
            (279, 4, 1, 1),
        ],
        strip_offset=96,
        strip_payload=b"\x01",
    )
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(tiff), out, COSDictionary(), 0)
    assert out.getvalue() == b"\x80"


def test_extract_tile_offset_tags_324_325_carry_strip() -> None:
    """Tags 324 (TileOffsets) and 325 (TileByteCounts) with count==1 are
    accepted as a substitute for tags 273/279 — covers lines 211-215."""
    tiff = _make_tiff_le(
        [
            (259, 3, 1, 4),
            (324, 4, 1, 96),
            (325, 4, 1, 1),
        ],
        strip_offset=96,
        strip_payload=b"Z",
    )
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(tiff), out, COSDictionary(), 0)
    assert out.getvalue() == b"Z"


def test_extract_orientation_one_is_accepted_silently() -> None:
    """Orientation==1 is the only accepted value and passes through with
    no params side-effect — covers the Orientation branch's accept arm."""
    tiff = _make_tiff_le(
        [
            (259, 3, 1, 4),
            (274, 3, 1, 1),
            (273, 4, 1, 96),
            (279, 4, 1, 1),
        ],
        strip_offset=96,
        strip_payload=b"O",
    )
    extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)


def test_extract_byte_type_truncated_raises() -> None:
    """When the IFD claims a byte-type tag but the file truncates right
    before the val(4) field, the inner ``reader.read(1)`` returns empty
    and the helper raises — covers lines 161-162."""
    # header(8) + numtags(2) + 8 bytes of tag descriptor (no val field).
    hdr = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    body = (
        struct.pack("<H", 1) + struct.pack("<HHI", 262, 1, 1)
    )  # tag=262, type=1 (byte), count=1; val(4) missing
    with pytest.raises(OSError, match="Not a valid tiff file"):
        extract_from_tiff(io.BytesIO(hdr + body), io.BytesIO(), COSDictionary(), 0)


def test_extract_strip_offset_past_end_of_file_breaks_loop() -> None:
    """When ``dataoffset`` seeks past EOF, the strip-copy loop's
    ``reader.read`` returns empty and the loop breaks — covers line 230.
    Output stays empty even though ``datalength`` was nonzero."""
    hdr = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    n = 3
    tags = (
        struct.pack("<HHII", 259, 3, 1, 4)
        + struct.pack("<HHII", 273, 4, 1, 1000)  # offset way past EOF
        + struct.pack("<HHII", 279, 4, 1, 50)  # claims 50 bytes
    )
    ifd = struct.pack("<H", n) + tags + struct.pack("<I", 0)
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(hdr + ifd), out, COSDictionary(), 0)
    assert out.getvalue() == b""


def test_extract_strip_count_other_than_one_skips_data_offset() -> None:
    """Tag 273 with count != 1 is *not* taken as the strip offset
    (upstream parity — multi-strip TIFFs aren't supported). Covers the
    count guard at line 190 and triggers the dataoffset==0 raise."""
    tiff = _make_tiff_le(
        [
            (259, 3, 1, 4),
            (273, 4, 2, 96),  # count != 1
            (279, 4, 2, 1),  # count != 1
        ],
        strip_offset=96,
        strip_payload=b"X",
    )
    with pytest.raises(OSError, match="single tile/strip"):
        extract_from_tiff(io.BytesIO(tiff), io.BytesIO(), COSDictionary(), 0)
