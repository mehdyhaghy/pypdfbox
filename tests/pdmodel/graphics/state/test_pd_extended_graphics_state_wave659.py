from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState


def _make_type2_function() -> COSDictionary:
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    fn.set_item("N", COSInteger.get(1))
    return fn


def test_wave659_copy_skips_none_values_and_missing_soft_mask_slots() -> None:
    class Target:
        pass

    gs = PDExtendedGraphicsState()
    gs.get_cos_object().set_item("RI", COSArray())
    gs.set_soft_mask(COSName.get_pdf_name("None"))

    target = Target()
    gs.copy_into_graphics_state(target)

    assert not hasattr(target, "rendering_intent")
    assert not hasattr(target, "soft_mask")


def test_wave659_soft_mask_ctm_falls_back_to_ctm_attribute_and_copies() -> None:
    class Matrix:
        def __init__(self) -> None:
            self.copy_calls = 0

        def copy(self) -> Matrix:
            self.copy_calls += 1
            return Matrix()

    class Target:
        def __init__(self) -> None:
            self.ctm = Matrix()
            self.soft_mask = None

    sm_dict = COSDictionary()
    sm_dict.set_name("S", "Alpha")
    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(sm_dict)

    target = Target()
    gs.copy_into_graphics_state(target)

    assert target.soft_mask.get_cos_object() is sm_dict
    assert target.soft_mask.get_initial_transformation_matrix() is not target.ctm
    assert target.ctm.copy_calls == 1


def test_wave659_font_helpers_cover_empty_remove_and_size_first_paths() -> None:
    gs = PDExtendedGraphicsState()
    empty_font_array = COSArray()
    gs.get_cos_object().set_item("Font", empty_font_array)

    assert gs.get_font() is None

    gs.set_font(COSName.get_pdf_name("F1"))
    gs.set_font(None)
    assert gs.get_cos_object().get_item("Font") is None

    gs.set_font_size(9.5)
    raw = gs.get_cos_object().get_dictionary_object("Font")
    assert isinstance(raw, COSArray)
    assert gs.get_font() is None
    assert gs.get_font_size() == 9.5


def test_wave659_line_dash_pattern_accepts_typed_wrapper() -> None:
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    raw = COSArray()
    raw.add(COSArray())
    raw.add(COSFloat(2.0))
    pattern = PDLineDashPattern.from_cos_array(raw)

    gs = PDExtendedGraphicsState()
    gs.set_line_dash_pattern(pattern)

    stored = gs.get_cos_object().get_dictionary_object("D")
    assert isinstance(stored, COSArray)
    assert stored.size() == 2
    assert gs.get_line_dash_pattern().get_phase() == 2.0


def test_wave659_undercolor_removal2_typed_none_default_and_function() -> None:
    from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2

    gs = PDExtendedGraphicsState()
    assert gs.get_undercolor_removal2_typed() is None

    default = COSName.get_pdf_name("Default")
    gs.set_undercolor_removal2(default)
    assert gs.get_undercolor_removal2_typed() is default

    gs.set_undercolor_removal2(_make_type2_function())
    assert isinstance(gs.get_undercolor_removal2_typed(), PDFunctionType2)
