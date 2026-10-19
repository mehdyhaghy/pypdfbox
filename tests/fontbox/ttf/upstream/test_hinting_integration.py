"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``fontbox/src/test/java/org/apache/fontbox/ttf/HintingIntegrationTest.java``.

End-to-end tests: drive hinting through ``TrueTypeFont.get_hinted_path``
at the path level. LiberationSans carries a full bytecode program.

Deviation: upstream exercises the no-bytecode fallback with Lohit-Bengali
(a ``cvt`` but no ``fpgm``/``prep``), which is SIL OFL and deliberately not
bundled; the same shape is built here by dropping ``fpgm`` and ``prep`` from
Liberation Sans.
"""

import io
from pathlib import Path
from typing import Any

from pypdfbox.fontbox.ttf import (
    ControlValueProgramTable,
    MemoryTTFDataStream,
    TrueTypeFont,
    TTFParser,
)
from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyph_hinter import GlyphHinter

_TTF = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "ttf"
_LIBERATION = _TTF / "LiberationSans-Regular.ttf"


def _parse(path: Path = _LIBERATION) -> TrueTypeFont:
    return TTFParser().parse(path)


def _gid(font: TrueTypeFont, code_point: int | str) -> int:
    if isinstance(code_point, str):
        code_point = ord(code_point)
    lookup = font.get_unicode_cmap_lookup()
    assert lookup is not None
    return lookup.get_glyph_id(code_point)


def _flatten(path: Any) -> list[Any]:
    """A path as a segment list so two paths can be compared point-for-point."""
    return list(path.value)


def test_gasp_gate() -> None:
    font = _parse()
    h = _gid(font, "H")
    # LiberationSans gasp: grid-fitting is off at <=8 ppem, on above it
    assert font.get_hinted_path(h, 8) is None, "no hinting expected at 8ppem (gasp)"
    assert font.get_hinted_path(h, 16) is not None, "hinting expected at 16ppem"


def test_lowest_rec_ppem_gate() -> None:
    """``head.lowestRecPPEM`` is the vendor's smallest readable outline size; the value is
    raised on Liberation Sans (normally 8) before the hinter first reads it."""
    font = _parse()
    font.get_header().set_lowest_rec_ppem(20)
    h = _gid(font, "H")
    assert font.get_hinted_path(h, 16) is None, "no hinting below lowestRecPPEM"
    assert font.get_hinted_path(h, 20) is not None, "hinting expected from lowestRecPPEM up"


def test_hinted_differs_from_raw_outline() -> None:
    font = _parse()
    h = _gid(font, "H")
    hinted = font.get_hinted_path(h, 16)
    assert hinted is not None
    raw = font.get_glyph(h).get_path()
    # grid-fitting must actually change the outline (proves the pipeline is wired in)
    assert _flatten(hinted) != _flatten(raw), "hinted path should differ from the raw outline"


def test_deterministic() -> None:
    font = _parse()
    h = _gid(font, "H")
    first = _flatten(font.get_hinted_path(h, 16))
    second = _flatten(font.get_hinted_path(h, 16))
    # re-hinting the same glyph at the same ppem is deterministic (no leaked state)
    assert first == second


def test_hinting_is_independent_of_glyph_order() -> None:
    """Hinting one glyph must not change the next; a composite is in the run because it
    re-enters the hinter for each component."""
    font = _parse()
    h = _gid(font, "H")
    eacute = _gid(font, 0x00E9)
    assert font.get_glyph(eacute).get_number_of_contours() < 0, (
        "expected e-acute to be a composite glyph"
    )
    before = _flatten(font.get_hinted_path(h, 16))
    for c in "oxn8":
        font.get_hinted_path(_gid(font, c), 16)
    font.get_hinted_path(eacute, 16)
    after = _flatten(font.get_hinted_path(h, 16))
    assert before == after, "hinting other glyphs must not change the result for 'H'"


def test_hinting_is_independent_of_ppem_order() -> None:
    """Returning to a ppem must reproduce the earlier result."""
    font = _parse()
    h = _gid(font, "H")
    before = _flatten(font.get_hinted_path(h, 16))
    font.get_hinted_path(h, 11)
    font.get_hinted_path(h, 24)
    after = _flatten(font.get_hinted_path(h, 16))
    assert before == after, "hinting at other ppems must not change the result at 16ppem"


def test_failed_prep_does_not_leave_stale_state() -> None:
    """Liberation Sans's own ``prep`` is prefixed with ``MPPEM 11 EQ IF <invalid opcode> EIF``
    so it fails at 11ppem only; returning to 16ppem must re-run ``prep``."""
    font = _with_prep_prefix(0x4B, 0xB0, 11, 0x54, 0x58, 0x28, 0x59)
    h = _gid(font, "H")
    before = _flatten(font.get_hinted_path(h, 16))
    assert font.get_hinted_path(h, 11) is None, "prep fails at 11ppem, so no hinting there"
    after = _flatten(font.get_hinted_path(h, 16))
    assert before == after, "a prep failure at another size must not change the result at 16ppem"


def test_round_xy_to_grid_rounds_only_the_component_y_offset() -> None:
    """In Liberation Sans the '1/4' glyph (no instructions of its own) places four.sups at
    (952, -561) font units with ROUND_XY_TO_GRID; at 11ppem that scales to
    (327.25, -192.84)/64 px, and FreeType offsets the component's points by exactly
    (+327, -192)."""
    font = _parse()
    assert font.get_units_per_em() == 2048
    hinter = GlyphHinter(font)
    hinter._initialize()
    # pypdfbox's GlyphData description is a fontTools adapter without the component list, so the
    # hinter's own upstream-shaped description stands in for GlyfCompositeDescript here
    quarter = hinter._description(_gid(font, 0x00BC))
    quarter.resolve()
    four = quarter.get_components()[2]
    assert four.get_x_translate() == 952
    assert four.get_y_translate() == -561
    assert four.get_flags() & GlyfCompositeComp.ROUND_XY_TO_GRID != 0

    # four.sups has no instructions, so it enters the composite as its plain scaled outline
    component = font.get_glyph(four.get_glyph_index()).get_description()
    assert hinter.get_hinted_points_f26_dot6(four.get_glyph_index(), 11) is None

    composite = hinter.get_hinted_points_f26_dot6(_gid(font, 0x00BC), 11)
    assert composite is not None
    for k in range(component.get_point_count()):
        x = Fixed.scale(component.get_x_coordinate(k), 11, 2048)
        y = Fixed.scale(component.get_y_coordinate(k), 11, 2048)
        assert composite[0][four.get_first_index() + k] - x == 327, f"x of point {k}"
        assert composite[1][four.get_first_index() + k] - y == -192, f"y of point {k}"


def test_instctrl_in_prep_can_disable_hinting() -> None:
    """INSTCTRL(1,1) in prep switches hinting off at that size: FreeType renders the raw
    outline."""
    font = _with_prep_prefix(0xB1, 1, 1, 0x8E)
    assert font.get_hinted_path(_gid(font, "H"), 16) is None


def test_instctrl_in_prep_can_waive_backward_compatibility() -> None:
    """INSTCTRL(4,3) in prep is the native-ClearType waiver: x-direction moves are no longer
    suppressed and the result differs from the default."""
    plain = _parse()
    waived = _with_prep_prefix(0xB1, 4, 3, 0x8E)
    h = _gid(plain, "H")
    assert _flatten(plain.get_hinted_path(h, 16)) != _flatten(waived.get_hinted_path(h, 16))


def _with_prep_prefix(*prefix: int) -> TrueTypeFont:
    """Loads Liberation Sans with the given bytecode prepended to its ``prep``, before the
    hinter first reads the table."""
    font = _parse()
    prep = font.get_control_value_program().get_program()
    program = bytes(prefix) + bytes(prep)
    table = ControlValueProgramTable()
    table.set_tag(ControlValueProgramTable.TAG)
    table.set_length(len(program))
    table.read(font, MemoryTTFDataStream(program))
    font.add_table(table)
    return font


def test_point_delta_is_the_largest_point_displacement() -> None:
    """The full-control probe compares two outlines by the largest displacement of any point on
    either axis - so a component moved inside the glyph counts, not just its extents."""
    a = [[0, 640, 320], [0, 0, 640]]
    assert GlyphHinter.point_delta(a, a) == 0
    # an interior point moves 5px in x (bounding box unchanged), another 1px in y
    b = [[0, 640, 640], [0, 64, 640]]
    assert GlyphHinter.point_delta(a, b) == 320


def test_builds_geometry_needs_both_signals() -> None:
    raw = [[0, 640], [0, 640]]
    near_raw = [[0, 640], [0, 704]]  # 1px from raw: ordinary hinting
    built = [[640, 640], [0, 640]]  # 10px from raw: components moved
    wild = [[6400, 640], [0, 640]]  # 100px: broken x instructions
    # tricky font: far from raw with backward compatibility on, and different again without
    assert GlyphHinter.builds_geometry(raw, built, wild)
    # broken x hinting: fine with backward compatibility on, wild without
    assert not GlyphHinter.builds_geometry(raw, near_raw, wild)
    # ordinary font: neither
    assert not GlyphHinter.builds_geometry(raw, near_raw, near_raw)
    # far from raw but backward compatibility makes no difference: full control would not help
    assert not GlyphHinter.builds_geometry(raw, built, built)


def test_assembly_ppem() -> None:
    # MingLiU-like font (lowestRecPPEM 25): below 25 assemble at 25, from 25 up unchanged
    assert GlyphHinter.assembly_ppem(13, True, 25) == 25
    assert GlyphHinter.assembly_ppem(24, True, 25) == 25
    assert GlyphHinter.assembly_ppem(25, True, 25) == 25
    assert GlyphHinter.assembly_ppem(107, True, 25) == 107
    # ordinary fonts are never resized, whatever lowestRecPPEM says
    assert GlyphHinter.assembly_ppem(13, False, 25) == 13
    # an absurd lowestRecPPEM is capped
    assert GlyphHinter.assembly_ppem(13, True, 255) == 64
    # nothing to do for a font that declares a small lowestRecPPEM, or a non-positive size
    assert GlyphHinter.assembly_ppem(13, True, 9) == 13
    assert GlyphHinter.assembly_ppem(0, True, 25) == 0


def test_font_without_bytecode_falls_back() -> None:
    # upstream: Lohit-Bengali (a cvt, no fpgm, no prep; not bundled). Same shape from Liberation.
    from fontTools.ttLib import TTFont

    tt = TTFont(str(_LIBERATION))
    del tt["fpgm"]
    del tt["prep"]
    assert "cvt " in tt
    buffer = io.BytesIO()
    tt.save(buffer)
    font = TTFParser().parse(buffer.getvalue())
    assert font.get_hinted_path(_gid(font, "H"), 16) is None


def test_empty_glyph_falls_back() -> None:
    font = _parse()
    # the space glyph has no contours; hinting must fall back rather than fail
    assert font.get_hinted_path(_gid(font, " "), 16) is None


def test_common_glyphs_hint_without_falling_back() -> None:
    # every one of these simple glyphs carries instructions and must grid-fit without raising
    # (which would silently fall back to None)
    font = _parse()
    sample = "HILEToxn0123456789"
    for ppem in (11, 13, 16, 24):
        for c in sample:
            assert font.get_hinted_path(_gid(font, c), ppem) is not None, (
                f"expected '{c}' to hint at {ppem}ppem"
            )
