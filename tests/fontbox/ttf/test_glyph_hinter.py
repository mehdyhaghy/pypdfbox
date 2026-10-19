"""Hand-written tests for ``GlyphHinter`` (PDFBOX-3293): its fontTools-backed
glyph descriptions, gating, failure reporting, path output and the fast
``GlyphRenderer.get_path``."""

import io
import logging
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import (
    ControlValueProgramTable,
    MemoryTTFDataStream,
    TrueTypeFont,
    TTFParser,
)
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyph_hinter import GlyphHinter, _component
from pypdfbox.fontbox.ttf.glyph_renderer import GlyphRenderer

_TTF = Path(__file__).resolve().parents[2] / "fixtures" / "fontbox" / "ttf"
_LIBERATION = _TTF / "LiberationSans-Regular.ttf"


@pytest.fixture(scope="module")
def liberation() -> TrueTypeFont:
    return TTFParser().parse(_LIBERATION)


def _gid(font: TrueTypeFont, ch: str) -> int:
    lookup = font.get_unicode_cmap_lookup()
    assert lookup is not None
    return lookup.get_glyph_id(ord(ch))


def _with_prep(font_path: Path, prefix: bytes) -> TrueTypeFont:
    font = TTFParser().parse(font_path)
    program = prefix + bytes(font.get_control_value_program().get_program())
    table = ControlValueProgramTable()
    table.set_tag(ControlValueProgramTable.TAG)
    table.set_length(len(program))
    table.read(font, MemoryTTFDataStream(program))
    font.add_table(table)
    return font


# --- descriptions ------------------------------------------------------------------------------


def test_simple_description_matches_glyph_data(liberation: TrueTypeFont) -> None:
    hinter = GlyphHinter(liberation)
    hinter._initialize()
    for ch in "HoxQ8&":
        gid = _gid(liberation, ch)
        gd = hinter._description(gid)
        raw = liberation.get_glyph(gid).get_description()
        assert not gd.is_composite()
        assert gd.get_point_count() == raw.get_point_count()
        assert gd.get_contour_count() == raw.get_contour_count()
        for i in range(gd.get_point_count()):
            # both carry upstream's (lsb - xMin) x-shift
            assert gd.get_x_coordinate(i) == raw.get_x_coordinate(i)
            assert gd.get_y_coordinate(i) == raw.get_y_coordinate(i)
            assert gd.get_flags(i) & 1 == raw.get_flags(i) & 1
        assert gd.get_instructions()
        # a description is built once
        assert hinter._description(gid) is gd


def test_composite_description_resolves_components(liberation: TrueTypeFont) -> None:
    hinter = GlyphHinter(liberation)
    hinter._initialize()
    eacute = _gid(liberation, "é")
    gd = hinter._description(eacute)
    assert gd.is_composite()
    components = gd.get_components()
    assert [c.get_glyph_index() for c in components][0] == _gid(liberation, "e")
    e = hinter._description(_gid(liberation, "e"))
    assert components[0].get_first_index() == 0
    assert components[1].get_first_index() == e.get_point_count()
    assert components[1].get_first_contour() == e.get_contour_count()
    acute = hinter._description(components[1].get_glyph_index())
    assert gd.get_point_count() == e.get_point_count() + acute.get_point_count()
    assert gd.get_end_pt_of_contours(gd.get_contour_count() - 1) == gd.get_point_count() - 1
    # composite points are the components' points plus the component offset
    comp = components[1]
    k = 3
    assert gd.get_x_coordinate(comp.get_first_index() + k) == (
        acute.get_x_coordinate(k) + comp.get_x_translate()
    )
    assert gd.get_y_coordinate(comp.get_first_index() + k) == (
        acute.get_y_coordinate(k) + comp.get_y_translate()
    )


def test_out_of_range_gid_has_no_description(liberation: TrueTypeFont) -> None:
    hinter = GlyphHinter(liberation)
    hinter._initialize()
    assert hinter._description(-1) is None
    assert hinter._description(liberation.get_number_of_glyphs()) is None
    assert hinter.get_path(liberation.get_number_of_glyphs(), 16) is None
    assert hinter.get_path(_gid(liberation, "H"), 0) is None
    assert hinter.get_failure_count() == 0


class _FontToolsComponent:
    def __init__(self, **attrs: object) -> None:
        self.__dict__.update(attrs)


def test_component_reads_offsets_and_anchor_points() -> None:
    # fontTools strips ARGS_ARE_XY_VALUES; the offset form is recognised by its attributes
    offset = _component(_FontToolsComponent(flags=0x0004, x=12, y=-7), 5)
    assert offset.get_glyph_index() == 5
    assert offset.get_x_translate() == 12
    assert offset.get_y_translate() == -7
    assert offset.get_flags() & GlyfCompositeComp.ROUND_XY_TO_GRID
    assert offset.args_are_xy_values()
    anchored = _component(_FontToolsComponent(flags=0, firstPt=3, secondPt=4), 6)
    assert not anchored.args_are_xy_values()
    assert anchored.get_x_translate() == 0
    assert anchored.get_argument1() == 3
    scaled = _component(
        _FontToolsComponent(flags=0, x=0, y=0, transform=[[0.5, 0.25], [-0.25, 2.0]]), 7
    )
    assert scaled.get_x_scale() == 0.5
    assert scaled.get_scale01() == 0.25
    assert scaled.get_scale10() == -0.25
    assert scaled.get_y_scale() == 2.0


# --- output ------------------------------------------------------------------------------------


def test_path_is_the_hinted_points_in_font_units(liberation: TrueTypeFont) -> None:
    hinter = GlyphHinter(liberation)
    gid = _gid(liberation, "H")
    points = hinter.get_hinted_points_f26_dot6(gid, 16)
    path = hinter.get_path(gid, 16)
    assert points is not None and path is not None
    upem = liberation.get_units_per_em()
    xs = {round(x * upem / (16 * 64)) for x in points[0]}
    ys = {round(y * upem / (16 * 64)) for y in points[1]}
    for _op, args in path.value:
        for x, y in args:
            assert x in xs
            assert y in ys
    # the baseline is grid-fitted, so it is a whole pixel in font units
    assert Fixed.round(min(points[1])) == min(points[1])


def test_fast_renderer_path_equals_describe_and_calculate_path(
    liberation: TrueTypeFont,
) -> None:
    hinter = GlyphHinter(liberation)
    hinter._initialize()
    checked = 0
    for gid in range(liberation.get_number_of_glyphs()):
        gd = hinter._description(gid)
        if gd is None or gd.get_point_count() == 0:
            continue
        for hinted in (None, gd.xs):
            renderer = GlyphRenderer(gd, hinted, gd.ys if hinted is not None else None)
            slow = renderer.calculate_path(renderer.describe(gd, hinted, renderer._hinted_y))
            assert renderer.get_path().value == slow.value, f"gid {gid}"
        # without the precomputed flags (any GlyphDescription)
        plain = liberation.get_glyph(gid).get_description()
        renderer = GlyphRenderer(plain)
        assert renderer.get_path().value == renderer.calculate_path(renderer.describe(plain)).value
        checked += 1
    assert checked > 2000


def test_trace_glyph_writes_a_trace(liberation: TrueTypeFont) -> None:
    hinter = GlyphHinter(liberation)
    out = io.StringIO()
    hinter.trace_glyph(_gid(liberation, "H"), 16, out, 0)
    assert out.getvalue().count("\n") > 10
    assert hinter._interpreter._tracer is None


# --- gating and failures -----------------------------------------------------------------------


def test_failures_warn_once_then_log_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    # MPPEM 16 EQ IF <invalid opcode 0x28> EIF: prep fails at 16ppem only
    font = _with_prep(_LIBERATION, bytes([0x4B, 0xB0, 16, 0x54, 0x58, 0x28, 0x59]))
    hinter = GlyphHinter(font)
    with caplog.at_level(logging.DEBUG, logger="pypdfbox.fontbox.ttf.glyph_hinter"):
        assert hinter.get_path(_gid(font, "H"), 16) is None
        assert hinter.get_path(_gid(font, "o"), 16) is None
        assert hinter.get_path(_gid(font, "H"), 13) is not None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "further failures in this font are logged at debug level" in warnings[0].getMessage()
    assert hinter.get_failure_count() == 2
    first = hinter.get_first_failure()
    assert first is not None and first.startswith(f"glyph {_gid(font, 'H')} at 16ppem: ")


def test_font_without_maxp_bytecode_is_not_hinted(liberation: TrueTypeFont) -> None:
    from fontTools.ttLib import TTFont

    tt = TTFont(str(_LIBERATION))
    del tt["fpgm"]
    del tt["prep"]
    buffer = io.BytesIO()
    tt.save(buffer)
    font = TTFParser().parse(buffer.getvalue())
    hinter = GlyphHinter(font)
    assert hinter.get_path(_gid(font, "H"), 16) is None
    assert not hinter.is_full_control()
    assert hinter._interpreter is None


def test_probe_samples_instructed_glyphs_once(liberation: TrueTypeFont) -> None:
    hinter = GlyphHinter(liberation)
    hinter._initialize()
    sample = hinter._probe_sample()
    assert 0 < len(sample) <= GlyphHinter.PROBE_SAMPLE
    assert sample == sorted(sample)
    assert not hinter.is_full_control()
    # the probe ran prep at its own size, so the next glyph re-runs it at its own
    assert hinter._current_ppem == -1
    hinter.get_path(_gid(liberation, "H"), 16)
    assert hinter._current_ppem == 16
    hinter.get_path(_gid(liberation, "o"), 16)
    assert hinter._current_ppem == 16


def test_full_control_font_is_assembled_at_lowest_rec_ppem(liberation: TrueTypeFont) -> None:
    font = TTFParser().parse(_LIBERATION)
    font.get_header().set_lowest_rec_ppem(20)
    hinter = GlyphHinter(font)
    hinter._initialize()
    hinter._full_control = True  # as if the probe had found a "tricky" font
    gid = _gid(font, "H")
    # below lowestRecPPEM it is hinted at 20ppem and scaled down; the points are not
    path = hinter.get_path(gid, 12)
    assert path is not None
    assert hinter._current_ppem == 20
    assert hinter.get_hinted_points_f26_dot6(gid, 12) is not None
    assert hinter._current_ppem == 12


def test_hinted_path_is_created_lazily_once_per_font() -> None:
    font = TTFParser().parse(_LIBERATION)
    assert font._hinter is None
    first = font.get_hinted_path(_gid(font, "H"), 16)
    hinter = font._hinter
    assert isinstance(hinter, GlyphHinter)
    assert font.get_hinted_path(_gid(font, "H"), 16).value == first.value
    assert font._hinter is hinter
