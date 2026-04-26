"""End-to-end test of the hmtx -> PDTrueTypeFont.get_glyph_width pipeline.

Builds a tiny in-memory TrueType byte buffer with just the four tables
needed for advance-width lookup (``head`` + ``hhea`` + ``maxp`` + ``hmtx``,
plus a minimal format-0 ``cmap``) so we can exercise both the pure
fontbox parser and the PDTrueTypeFont wiring without a real on-disk font.
"""

from __future__ import annotations

import struct

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import (
    HorizontalHeaderTable,
    HorizontalMetricsTable,
    TrueTypeFont,
)
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

# ---------- TTF builder ----------------------------------------------------


def _pad4(b: bytes) -> bytes:
    """SFNT directory entries point at 4-byte-aligned offsets."""
    pad = (-len(b)) & 3
    return b + b"\x00" * pad


def _build_head(units_per_em: int = 1000) -> bytes:
    return struct.pack(
        ">iIIIHHqqhhhhHHhhh",
        0x00010000,          # version 1.0
        0x00010000,          # fontRevision 1.0
        0,                   # checkSumAdjustment
        0x5F0F3CF5,          # magicNumber
        0,                   # flags
        units_per_em,        # unitsPerEm
        0,                   # created
        0,                   # modified
        0, 0, 1000, 1000,    # xMin yMin xMax yMax
        0,                   # macStyle
        8,                   # lowestRecPPEM
        2,                   # fontDirectionHint
        0,                   # indexToLocFormat
        0,                   # glyphDataFormat
    )


def _build_hhea(num_h_metrics: int) -> bytes:
    return struct.pack(
        ">hHhhhHhhhhhhhhhhhH",
        1, 0,            # version 1.0
        800,             # ascender
        -200,            # descender
        90,              # lineGap
        2048,            # advanceWidthMax
        0, 0, 1900,      # minLSB / minRSB / xMaxExtent
        1, 0,            # caretSlopeRise / caretSlopeRun
        0, 0, 0, 0, 0,   # 5 reserved shorts
        0,               # metricDataFormat
        num_h_metrics,
    )


def _build_maxp(num_glyphs: int) -> bytes:
    # version 0.5 — short form, just numGlyphs.
    return struct.pack(">iH", 0x00005000, num_glyphs)


def _build_hmtx(metrics: list[tuple[int, int]], trailing_lsbs: list[int]) -> bytes:
    out = bytearray()
    for advance, lsb in metrics:
        out += struct.pack(">Hh", advance, lsb)
    for lsb in trailing_lsbs:
        out += struct.pack(">h", lsb)
    return bytes(out)


def _build_cmap_format0_identity() -> bytes:
    """Minimal cmap with one (3,1) subtable in format 0 mapping
    every byte ``c`` to glyph_id ``c``. Format 0 uses a 256-byte
    glyph index array — exactly what we need for our smoke test."""
    glyph_array = bytes(range(256))
    subtable = struct.pack(">HHH", 0, 262, 0) + glyph_array  # format=0, length=262, version=0
    # cmap header: version=0, numTables=1, then one EncodingRecord.
    header = struct.pack(">HH", 0, 1)
    encoding_record = struct.pack(">HHI", 3, 1, 4 + 8)  # platform=3, encoding=1, offset=12
    return header + encoding_record + subtable


def _build_ttf(
    *,
    units_per_em: int,
    num_h_metrics: int,
    metrics: list[tuple[int, int]],
    trailing_lsbs: list[int],
    num_glyphs: int,
    include_cmap: bool = False,
) -> bytes:
    """Assemble a minimal SFNT with just the tables we need.

    Tables are emitted in alphabetical-tag order (cmap, head, hhea,
    hmtx, maxp). Each is 4-byte aligned per the SFNT spec.
    """
    head = _build_head(units_per_em)
    hhea = _build_hhea(num_h_metrics)
    maxp = _build_maxp(num_glyphs)
    hmtx = _build_hmtx(metrics, trailing_lsbs)
    cmap = _build_cmap_format0_identity() if include_cmap else b""

    tables: list[tuple[str, bytes]] = []
    if include_cmap:
        tables.append(("cmap", cmap))
    tables += [("head", head), ("hhea", hhea), ("hmtx", hmtx), ("maxp", maxp)]

    num_tables = len(tables)
    # Compute offsets: header(12) + directory(num_tables * 16), each table padded to 4 bytes.
    offset = 12 + num_tables * 16
    directory_entries: list[bytes] = []
    body = bytearray()
    for tag, blob in tables:
        directory_entries.append(struct.pack(">4sIII", tag.encode("ascii"), 0, offset, len(blob)))
        body += _pad4(blob)
        offset += len(_pad4(blob))

    # SFNT header: version=0x00010000 (TrueType), numTables, searchRange, entrySelector, rangeShift.
    # The search-range trio is purely advisory; tests don't validate them.
    sfnt = struct.pack(">IHHHH", 0x00010000, num_tables, 0, 0, 0)
    return sfnt + b"".join(directory_entries) + bytes(body)


# ---------- pure-parser tests ---------------------------------------------


def test_advance_widths_inherit_last_for_trailing_lsbs() -> None:
    """The hmtx table has 2 hMetrics + 1 trailing LSB → the third
    glyph's advance width inherits from the last hMetric."""
    blob = _build_hmtx(metrics=[(500, 0), (750, 10)], trailing_lsbs=[3])
    table = HorizontalMetricsTable()
    table.set_length(len(blob))

    # Stub the dependencies the way HorizontalMetricsTable expects.
    class _StubTTF:
        def get_horizontal_header(self) -> HorizontalHeaderTable:
            hhea = HorizontalHeaderTable()
            hhea._number_of_h_metrics = 2  # noqa: SLF001
            return hhea

        def get_number_of_glyphs(self) -> int:
            return 3

    table.read(_StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]

    assert table.get_advance_width(0) == 500
    assert table.get_advance_width(1) == 750
    assert table.get_advance_width(2) == 750  # inherits from last hMetric


def test_true_type_font_parses_directory_and_hmtx() -> None:
    """End-to-end through TrueTypeFont: directory walk + lazy table reads."""
    ttf_bytes = _build_ttf(
        units_per_em=1000,
        num_h_metrics=2,
        metrics=[(500, 0), (750, 10)],
        trailing_lsbs=[3],
        num_glyphs=3,
    )
    ttf = TrueTypeFont.from_bytes(ttf_bytes)

    assert ttf.get_units_per_em() == 1000
    assert ttf.get_number_of_glyphs() == 3
    assert ttf.get_advance_width(0) == 500
    assert ttf.get_advance_width(1) == 750
    assert ttf.get_advance_width(2) == 750  # inherits from last entry


# ---------- PDTrueTypeFont integration -------------------------------------


def _make_font_dict_with_fontfile2(ttf_bytes: bytes) -> COSDictionary:
    """Build a /Font dict whose /FontDescriptor has /FontFile2 pointing
    at the supplied TrueType bytes."""
    descriptor = PDFontDescriptor()
    font_file = COSStream()
    font_file.set_data(ttf_bytes)
    descriptor.set_font_file2(font_file)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return font_dict


def test_pd_true_type_font_get_glyph_width_from_fontfile2() -> None:
    ttf_bytes = _build_ttf(
        units_per_em=1000,
        num_h_metrics=2,
        metrics=[(500, 0), (750, 10)],
        trailing_lsbs=[3],
        num_glyphs=3,
        include_cmap=True,
    )
    font_dict = _make_font_dict_with_fontfile2(ttf_bytes)
    font = PDTrueTypeFont(font_dict)

    # No /Widths and no /Encoding → falls through to cmap (format-0
    # identity) → hmtx → 500 / 1000 * 1000 = 500.
    assert font.get_glyph_width(0) == 500.0
    assert font.get_glyph_width(1) == 750.0
    # gid 2 inherits from the last hMetric.
    assert font.get_glyph_width(2) == 750.0


def test_pd_true_type_font_get_glyph_width_scales_units_per_em() -> None:
    """unitsPerEm=2048 should rescale advances into 1/1000 em."""
    ttf_bytes = _build_ttf(
        units_per_em=2048,
        num_h_metrics=2,
        metrics=[(1024, 0), (2048, 0)],  # 0.5 em and 1.0 em
        trailing_lsbs=[],
        num_glyphs=2,
        include_cmap=True,
    )
    font_dict = _make_font_dict_with_fontfile2(ttf_bytes)
    font = PDTrueTypeFont(font_dict)

    assert font.get_glyph_width(0) == 500.0  # 1024/2048 * 1000
    assert font.get_glyph_width(1) == 1000.0  # 2048/2048 * 1000


def test_widths_array_overrides_hmtx() -> None:
    """PDF 32000-1 §9.7.3 — /Widths in the font dict wins over the
    embedded program's hmtx."""
    ttf_bytes = _build_ttf(
        units_per_em=1000,
        num_h_metrics=2,
        metrics=[(500, 0), (750, 10)],
        trailing_lsbs=[3],
        num_glyphs=3,
        include_cmap=True,
    )
    font_dict = _make_font_dict_with_fontfile2(ttf_bytes)

    # Add /FirstChar + /Widths covering codes 0..2 — should mask hmtx.
    from pypdfbox.cos import COSArray, COSInteger

    font_dict.set_int(COSName.get_pdf_name("FirstChar"), 0)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), 2)
    widths = COSArray()
    widths.add(COSInteger(123))
    widths.add(COSInteger(456))
    widths.add(COSInteger(789))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)

    font = PDTrueTypeFont(font_dict)
    assert font.get_glyph_width(0) == 123.0
    assert font.get_glyph_width(1) == 456.0
    assert font.get_glyph_width(2) == 789.0


def test_widths_overrides_only_inside_first_last_range() -> None:
    """Codes outside [FirstChar, LastChar] still fall through to hmtx."""
    ttf_bytes = _build_ttf(
        units_per_em=1000,
        num_h_metrics=2,
        metrics=[(500, 0), (750, 10)],
        trailing_lsbs=[3],
        num_glyphs=3,
        include_cmap=True,
    )
    font_dict = _make_font_dict_with_fontfile2(ttf_bytes)

    from pypdfbox.cos import COSArray, COSInteger

    # /Widths covers code 1 only.
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), 1)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), 1)
    widths = COSArray()
    widths.add(COSInteger(999))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)

    font = PDTrueTypeFont(font_dict)
    assert font.get_glyph_width(1) == 999.0          # /Widths wins
    assert font.get_glyph_width(0) == 500.0          # hmtx fallback
    assert font.get_glyph_width(2) == 750.0          # hmtx fallback


def test_pd_true_type_font_no_fontfile2_returns_zero_without_widths() -> None:
    """Bare font with no /FontFile2 and no /Widths → 0.0 (caller's
    job to supply a fallback)."""
    font = PDTrueTypeFont()
    assert font.get_glyph_width(65) == 0.0


def test_set_true_type_font_injects_program_directly() -> None:
    """``set_true_type_font`` lets callers bypass /FontFile2 parsing."""
    ttf_bytes = _build_ttf(
        units_per_em=1000,
        num_h_metrics=1,
        metrics=[(321, 0)],
        trailing_lsbs=[],
        num_glyphs=1,
        include_cmap=True,
    )
    font = PDTrueTypeFont()
    font.set_true_type_font(TrueTypeFont.from_bytes(ttf_bytes))
    assert font.get_glyph_width(0) == 321.0
