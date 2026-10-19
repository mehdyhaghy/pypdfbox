from pathlib import Path

from fontTools.ttLib import TTFont

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript

_FONT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _descript(name: str) -> GlyfCompositeDescript:
    font = TTFont(str(_FONT))
    glyf = font["glyf"]
    return GlyfCompositeDescript.from_glyph(glyf[name], glyf, lambda _gid: None)


def test_offset_component_keeps_translation() -> None:
    comps = _descript("Aacute")._components
    accent = comps[1]
    assert accent.args_are_xy_values()
    assert (accent.get_x_translate(), accent.get_y_translate()) == (475, 0)


def test_position_dependent_flags_restored() -> None:
    comps = _descript("Aacute")._components
    assert comps[0].get_flags() & GlyfCompositeComp.MORE_COMPONENTS
    assert not comps[-1].get_flags() & GlyfCompositeComp.MORE_COMPONENTS


def test_word_args_flag_for_large_offsets() -> None:
    font = TTFont(str(_FONT))
    glyf = font["glyf"]
    for name in glyf.keys():  # noqa: SIM118 - glyf iterates glyph names via keys()
        glyph = glyf[name]
        if not glyph.isComposite():
            continue
        for component in glyph.components:
            if hasattr(component, "x") and not -128 <= component.x <= 127:
                comp = GlyfCompositeComp.from_fonttools(component)
                assert comp.get_flags() & GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS
                assert comp.get_x_translate() == component.x
                return
    raise AssertionError("no composite with a word-sized offset in the fixture")
