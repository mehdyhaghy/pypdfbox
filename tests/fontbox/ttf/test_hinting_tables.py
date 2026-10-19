"""Hand-written tests for the TrueType hinting tables (``cvt ``, ``fpgm``,
``prep``, ``gasp``), the ``TrueTypeFont`` accessors, the hinted
``GlyphRenderer`` constructor and the ``get_hinted_path`` entry point
(PDFBOX-3293)."""

import io
import struct
import sys
import types
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import (
    ControlValueProgramTable,
    ControlValueTable,
    FontProgramTable,
    GaspTable,
    MemoryTTFDataStream,
    TrueTypeFont,
    TTFParser,
    TTFTable,
)
from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript
from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer

_TTF_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "ttf"
_LIBERATION = _TTF_DIR / "LiberationSans-Regular.ttf"
_HINTER_MODULE = "pypdfbox.fontbox.ttf.glyph_hinter"


def _liberation() -> TrueTypeFont:
    return TTFParser().parse(_LIBERATION)


def _read(table: TTFTable, data: bytes) -> TTFTable:
    table.set_length(len(data))
    table.read(None, MemoryTTFDataStream(data))  # type: ignore[arg-type]
    return table


# ---------------------------------------------------------------------------
# table readers
# ---------------------------------------------------------------------------


def test_tags_match_upstream() -> None:
    assert ControlValueTable.TAG == "cvt "
    assert FontProgramTable.TAG == "fpgm"
    assert ControlValueProgramTable.TAG == "prep"
    assert GaspTable.TAG == "gasp"
    assert ControlValueTable().get_tag() == "cvt "


def test_cvt_reads_signed_fwords() -> None:
    cvt = _read(ControlValueTable(), struct.pack(">hhh", 1484, -12, 0))
    assert cvt.get_values() == [1484, -12, 0]
    assert cvt.get_value_count() == 3
    assert cvt.get_initialized()


def test_cvt_odd_length_drops_trailing_byte() -> None:
    cvt = _read(ControlValueTable(), struct.pack(">hh", 7, 8) + b"\x01")
    assert cvt.get_values() == [7, 8]


def test_cvt_unread_has_no_values() -> None:
    cvt = ControlValueTable()
    assert cvt.get_values() is None
    assert cvt.get_value_count() == 0


@pytest.mark.parametrize("table_class", [FontProgramTable, ControlValueProgramTable])
def test_program_tables_keep_raw_bytecode(table_class: type[TTFTable]) -> None:
    table = table_class()
    assert table.get_program() is None
    _read(table, b"\xb0\x01\x2c")
    assert table.get_program() == b"\xb0\x01\x2c"
    assert isinstance(table.get_program(), bytes)


def test_gasp_lookup_and_grid_fit() -> None:
    data = struct.pack(">HH", 1, 2) + struct.pack(">HHHH", 10, 0x0A, 0xFFFF, 0x0F)
    gasp = _read(GaspTable(), data)
    assert gasp.get_version() == 1
    assert gasp.get_range_max_ppem() == [10, 0xFFFF]
    assert gasp.get_range_flags() == [0x0A, 0x0F]
    assert gasp.get_flags(10) == 0x0A
    assert gasp.get_flags(11) == 0x0F
    assert not gasp.is_grid_fit(10)
    assert gasp.is_grid_fit(11)
    assert GaspTable.GASP_SYMMETRIC_GRIDFIT == 0x0004
    assert GaspTable.GASP_SYMMETRIC_SMOOTHING == 0x0008


def test_gasp_beyond_last_range_uses_last_flags() -> None:
    gasp = _read(GaspTable(), struct.pack(">HHHH", 0, 1, 20, 0x02))
    assert gasp.get_flags(21) == 0x02


def test_gasp_without_ranges_gives_zero_flags() -> None:
    assert GaspTable().get_flags(12) == 0
    empty = _read(GaspTable(), struct.pack(">HH", 0, 0))
    assert empty.get_flags(12) == 0
    assert not empty.is_grid_fit(12)


# ---------------------------------------------------------------------------
# TrueTypeFont accessors
# ---------------------------------------------------------------------------


def test_accessors_return_typed_cached_tables() -> None:
    font = _liberation()
    cvt = font.get_control_values()
    assert isinstance(cvt, ControlValueTable)
    assert font.get_control_values() is cvt
    # the directory entry is replaced by the typed table, as upstream
    assert font.get_table("cvt ") is cvt
    assert isinstance(font.get_font_program(), FontProgramTable)
    assert isinstance(font.get_control_value_program(), ControlValueProgramTable)
    assert isinstance(font.get_gasp(), GaspTable)


def test_table_bytes_match_fonttools() -> None:
    font = _liberation()
    tt = font._tt
    assert font.get_control_values().get_values() == list(tt["cvt "].values)
    assert font.get_font_program().get_program() == tt["fpgm"].program.getBytecode()
    assert font.get_control_value_program().get_program() == tt["prep"].program.getBytecode()


def _liberation_without(*tags: str) -> TrueTypeFont:
    """LiberationSans with ``tags`` dropped from the table directory."""
    from fontTools.ttLib import TTFont

    tt = TTFont(str(_LIBERATION))
    for tag in tags:
        del tt[tag]
    out = io.BytesIO()
    tt.save(out)
    return TTFParser().parse(out.getvalue())


def test_absent_tables_return_none() -> None:
    # same shape as upstream's JosefinSans-Italic case (no cvt/fpgm)
    font = _liberation_without("cvt ", "fpgm")
    assert font.get_control_values() is None
    assert font.get_font_program() is None
    assert font.get_control_value_program() is not None
    assert font.get_gasp() is not None
    # and the Lohit-Tamil case (no gasp)
    no_gasp = _liberation_without("gasp")
    assert no_gasp.get_gasp() is None
    assert no_gasp.get_control_values() is not None


def test_truncated_gasp_raises_oserror_and_retries() -> None:
    font = _liberation()
    entry = font.get_table("gasp")
    original_length = entry.get_length()
    entry.set_length(3)
    with pytest.raises(OSError):
        font.get_gasp()
    # a failed read is not cached: restoring the length makes it readable
    font.get_table("gasp").set_length(original_length)
    assert font.get_gasp().get_range_max_ppem() == [8, 17, 65535]


def test_table_past_end_of_font_raises_oserror() -> None:
    font = _liberation()
    font.get_table("cvt ").set_offset(font.get_original_data_size())
    with pytest.raises(OSError):
        font.get_control_values()


def test_odd_cvt_length_in_font() -> None:
    font = _liberation()
    font.get_table("cvt ").set_length(7)
    assert font.get_control_values().get_values() == [1484, *font._tt["cvt "].values[1:3]]


def test_parser_directory_switch_creates_typed_tables() -> None:
    parser = TTFParser()
    raw = _LIBERATION.read_bytes()
    font = parser.create_font_with_tables(MemoryTTFDataStream(raw))
    entry = font.get_table("fpgm")
    assert isinstance(entry, FontProgramTable)
    assert not entry.get_initialized()
    assert parser._new_directory_table("glyf").__class__ is TTFTable
    # parse_tables forces the typed entries to load
    parser._is_embedded = True
    parser.parse_tables(font)
    assert entry.get_initialized()
    assert len(entry.get_program()) == 1972
    assert font.get_font_program() is entry


# ---------------------------------------------------------------------------
# hinting entry point
# ---------------------------------------------------------------------------


def test_get_hinted_path_without_glyph_hinter_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, _HINTER_MODULE, None)
    font = _liberation()
    assert font.get_hinted_path(43, 16) is None
    assert font._hinter is False


def test_get_hinted_path_delegates_to_lazily_created_hinter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[object] = []

    class _FakeHinter:
        def __init__(self, ttf: TrueTypeFont) -> None:
            created.append(ttf)

        def get_path(self, gid: int, ppem: int) -> tuple[int, int]:
            return (gid, ppem)

    fake = types.ModuleType(_HINTER_MODULE)
    fake.GlyphHinter = _FakeHinter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, _HINTER_MODULE, fake)
    font = _liberation()
    assert font.get_hinted_path(43, 16) == (43, 16)
    assert font.get_hinted_path(44, 11) == (44, 11)
    assert created == [font]


# ---------------------------------------------------------------------------
# GlyphRenderer with hinted coordinates
# ---------------------------------------------------------------------------


def _triangle() -> GlyfSimpleDescript:
    d = GlyfSimpleDescript()
    d._contour_count = 1
    d._end_pts_of_contours = [2]
    d._flags = [GlyfDescript.ON_CURVE] * 3
    d._x_coordinates = [0, 10, 5]
    d._y_coordinates = [0, 0, 10]
    d._point_count = 3
    return d


def test_glyph_renderer_uses_hinted_coordinates() -> None:
    pen = GlyphRenderer(_triangle(), [1, 11, 6], [2, 2, 12]).get_path()
    assert pen.value[0] == ("moveTo", ((1, 2),))
    assert ("lineTo", ((6, 12),)) in pen.value


def test_glyph_renderer_unhinted_default_unchanged() -> None:
    assert GlyphRenderer(_triangle()).get_path().value == (
        GlyphRenderer(_triangle(), None, None).get_path().value
    )
    assert GlyphRenderer(_triangle()).get_path().value[0] == ("moveTo", ((0, 0),))
