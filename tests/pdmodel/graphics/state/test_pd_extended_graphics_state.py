from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState


def test_fresh_has_type_ext_g_state() -> None:
    gs = PDExtendedGraphicsState()
    cos = gs.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name("Type") == "ExtGState"


def test_existing_dictionary_is_preserved() -> None:
    d = COSDictionary()
    d.set_name("Type", "ExtGState")
    d.set_int("LC", 2)
    gs = PDExtendedGraphicsState(d)
    assert gs.get_cos_object() is d
    assert gs.get_line_cap_style() == 2


def test_get_cos_object_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_cos_object() is gs.get_cos_object()


def test_round_trip_line_width() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_line_width() is None
    gs.set_line_width(2.0)
    assert gs.get_line_width() == 2.0


def test_round_trip_line_cap_style() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_line_cap_style() is None
    gs.set_line_cap_style(1)
    assert gs.get_line_cap_style() == 1


def test_round_trip_line_join_style() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_line_join_style() is None
    gs.set_line_join_style(2)
    assert gs.get_line_join_style() == 2


def test_round_trip_miter_limit() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_miter_limit() is None
    gs.set_miter_limit(10.0)
    assert gs.get_miter_limit() == 10.0


def test_round_trip_stroking_alpha_constant() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_stroking_alpha_constant() is None
    gs.set_stroking_alpha_constant(0.5)
    # 0.5 is exactly representable in IEEE-754 single precision.
    assert gs.get_stroking_alpha_constant() == 0.5


def test_round_trip_non_stroking_alpha_constant() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_non_stroking_alpha_constant() is None
    gs.set_non_stroking_alpha_constant(0.7)
    # COSFloat stores in IEEE-754 single precision (Java float parity);
    # 0.7 is not exactly representable, so use approx.
    assert gs.get_non_stroking_alpha_constant() == pytest.approx(0.7)


def test_round_trip_rendering_intent() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_rendering_intent() is None
    gs.set_rendering_intent("Perceptual")
    assert gs.get_rendering_intent() == "Perceptual"


def test_round_trip_blend_mode_cosname() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_blend_mode() is None
    multiply = COSName.get_pdf_name("Multiply")
    gs.set_blend_mode(multiply)
    bm = gs.get_blend_mode()
    assert isinstance(bm, BlendMode)
    assert bm is BlendMode.MULTIPLY
    assert bm.get_name() == "Multiply"
    assert gs.get_cos_object().get_item("BM") is multiply


def test_round_trip_blend_mode_string_stored_as_name() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_blend_mode("Screen")
    bm = gs.get_blend_mode()
    assert isinstance(bm, BlendMode)
    assert bm is BlendMode.SCREEN
    assert gs.get_cos_object().get_item("BM").get_name() == "Screen"


def test_round_trip_blend_mode_typed_wrapper() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_blend_mode(BlendMode.SOFT_LIGHT)
    bm = gs.get_blend_mode()
    assert bm is BlendMode.SOFT_LIGHT
    assert gs.get_cos_object().get_item("BM") == COSName.get_pdf_name("SoftLight")
    gs.set_blend_mode(None)
    assert gs.get_blend_mode() is None
    assert gs.get_cos_object().get_item("BM") is None


def test_blend_mode_array_picks_first_recognised_entry() -> None:
    gs = PDExtendedGraphicsState()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Bogus"))
    arr.add(COSName.get_pdf_name("Hue"))
    gs.get_cos_object().set_item("BM", arr)
    assert gs.get_blend_mode() is BlendMode.HUE


def test_blend_mode_compatible_aliases_to_normal() -> None:
    assert BlendMode.get("Compatible") is BlendMode.NORMAL


def test_blend_mode_separable_classification() -> None:
    assert BlendMode.MULTIPLY.is_separable()
    assert not BlendMode.HUE.is_separable()


def test_round_trip_alpha_source_flag() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_alpha_source_flag() is False
    gs.set_alpha_source_flag(True)
    assert gs.get_alpha_source_flag() is True
    gs.set_alpha_source_flag(False)
    assert gs.get_alpha_source_flag() is False


def test_round_trip_text_knockout_flag() -> None:
    gs = PDExtendedGraphicsState()
    # Upstream default for /TK when absent is True.
    assert gs.get_text_knockout_flag() is True
    gs.set_text_knockout_flag(False)
    assert gs.get_text_knockout_flag() is False
    gs.set_text_knockout_flag(True)
    assert gs.get_text_knockout_flag() is True


def test_round_trip_stroke_adjustment() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_stroke_adjustment() is False
    gs.set_stroke_adjustment(True)
    assert gs.get_stroke_adjustment() is True
    gs.set_stroke_adjustment(False)
    assert gs.get_stroke_adjustment() is False


def test_set_line_width_none_removes_entry() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_line_width(3.5)
    assert gs.get_line_width() == 3.5
    gs.set_line_width(None)
    assert gs.get_line_width() is None
    assert gs.get_cos_object().get_item("LW") is None


def test_overprint_mode_default_is_zero() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_overprint_mode() == 0
    gs.set_overprint_mode(1)
    assert gs.get_overprint_mode() == 1
    gs.set_overprint_mode(None)
    assert gs.get_overprint_mode() == 0
    assert gs.get_cos_object().get_item("OPM") is None


def test_stroke_overprint_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_strokeOverprint() is False
    gs.set_stroke_overprint(True)
    assert gs.get_strokeOverprint() is True


def test_non_stroking_overprint_falls_back_to_stroking() -> None:
    gs = PDExtendedGraphicsState()
    # When /op is absent, upstream falls back to /OP.
    gs.set_stroke_overprint(True)
    assert gs.get_non_stroking_overprint() is True
    gs.set_non_stroking_overprint(False)
    assert gs.get_non_stroking_overprint() is False


def test_smoothness_and_flatness_defaults_and_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_smoothness() == 0.0
    assert gs.get_flatness() == 1.0
    gs.set_smoothness(0.25)
    gs.set_flatness(2.0)
    assert gs.get_smoothness() == 0.25
    assert gs.get_flatness() == 2.0


def test_line_dash_pattern_round_trip_raw_array() -> None:
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    gs = PDExtendedGraphicsState()
    assert gs.get_line_dash_pattern() is None
    arr = COSArray()
    inner = COSArray()
    arr._items.append(inner)  # noqa: SLF001 - test exercises raw array shape
    arr._items.append(COSFloat(0.0))  # noqa: SLF001
    gs.set_line_dash_pattern(arr)
    rt = gs.get_line_dash_pattern()
    assert isinstance(rt, PDLineDashPattern)
    assert rt.get_phase() == 0.0
    gs.set_line_dash_pattern(None)
    assert gs.get_line_dash_pattern() is None


def test_font_size_helper() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_font_size() is None
    font = COSName.get_pdf_name("F1")
    gs.set_font(font)
    assert gs.get_font() is font
    gs.set_font_size(12.5)
    assert gs.get_font() is font
    assert gs.get_font_size() == 12.5
    # Setting again should overwrite the size slot, not append.
    gs.set_font_size(8.0)
    assert gs.get_font_size() == 8.0


def test_copy_into_graphics_state_uses_matching_setters() -> None:
    class TextState:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def set_font(self, font: object) -> None:
            self.calls.append(("font", font))

        def set_font_size(self, size: object) -> None:
            self.calls.append(("font_size", size))

        def set_knockout_flag(self, flag: object) -> None:
            self.calls.append(("knockout", flag))

    class GraphicsState:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []
            self.text_state = TextState()

        def set_line_width(self, value: object) -> None:
            self.calls.append(("line_width", value))

        def set_line_cap(self, value: object) -> None:
            self.calls.append(("line_cap", value))

        def set_line_join(self, value: object) -> None:
            self.calls.append(("line_join", value))

        def set_miter_limit(self, value: object) -> None:
            self.calls.append(("miter_limit", value))

        def set_rendering_intent(self, value: object) -> None:
            self.calls.append(("rendering_intent", value))

        def set_overprint_mode(self, value: object) -> None:
            self.calls.append(("overprint_mode", value))

        def set_alpha_constants(self, value: object) -> None:
            self.calls.append(("alpha_constants", value))

        def set_non_stroke_alpha_constants(self, value: object) -> None:
            self.calls.append(("non_stroke_alpha_constants", value))

        def set_alpha_source(self, value: object) -> None:
            self.calls.append(("alpha_source", value))

        def set_blend_mode(self, value: object) -> None:
            self.calls.append(("blend_mode", value))

        def get_text_state(self) -> TextState:
            return self.text_state

    gs = PDExtendedGraphicsState()
    gs.set_line_width(2.0)
    gs.set_line_cap_style(1)
    gs.set_line_join_style(2)
    gs.set_miter_limit(10.0)
    gs.set_rendering_intent("Perceptual")
    gs.set_overprint_mode(1)
    gs.set_stroking_alpha_constant(0.5)
    gs.set_non_stroking_alpha_constant(0.25)
    gs.set_alpha_source_flag(True)
    gs.set_text_knockout_flag(False)
    gs.set_font(COSName.get_pdf_name("F1"))
    gs.set_font_size(11.0)
    gs.set_blend_mode("Multiply")

    target = GraphicsState()
    gs.copy_into_graphics_state(target)

    assert ("line_width", 2.0) in target.calls
    assert ("line_cap", 1) in target.calls
    assert ("line_join", 2) in target.calls
    assert ("miter_limit", 10.0) in target.calls
    assert ("rendering_intent", "Perceptual") in target.calls
    assert ("overprint_mode", 1) in target.calls
    assert ("alpha_constants", 0.5) in target.calls
    assert ("non_stroke_alpha_constants", 0.25) in target.calls
    assert ("alpha_source", True) in target.calls
    assert ("blend_mode", BlendMode.MULTIPLY) in target.calls
    assert ("font", COSName.get_pdf_name("F1")) in target.text_state.calls
    assert ("font_size", 11.0) in target.text_state.calls
    assert ("knockout", False) in target.text_state.calls


def test_copy_into_graphics_state_uses_existing_attributes() -> None:
    class Target:
        def __init__(self) -> None:
            self.line_width = 1.0
            self.text_font = None
            self.text_font_size = 0.0

    gs = PDExtendedGraphicsState()
    font = COSName.get_pdf_name("F1")
    gs.set_line_width(3.0)
    gs.set_font(font)
    gs.set_font_size(9.0)

    target = Target()
    gs.copy_into_graphics_state(target)

    assert target.line_width == 3.0
    assert target.text_font is font
    assert target.text_font_size == 9.0


def test_copy_into_graphics_state_supports_dict_targets() -> None:
    gs = PDExtendedGraphicsState()
    font = COSName.get_pdf_name("F1")
    gs.set_stroke_adjustment(True)
    gs.set_font(font)
    gs.set_font_size(7.0)

    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)

    assert target["stroke_adjustment"] is True
    assert target["font"] is font
    assert target["font_size"] == 7.0


# ---------- Aliases mirroring upstream PDFBox 3.0.x naming ----------


def test_stroking_overprint_control_alias_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_stroking_overprint_control() is False
    gs.set_stroking_overprint_control(True)
    assert gs.get_stroking_overprint_control() is True
    # Alias must mutate the same underlying /OP entry as set_stroke_overprint.
    assert gs.get_strokeOverprint() is True


def test_non_stroking_overprint_control_alias_falls_back_to_stroking() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_stroking_overprint_control(True)
    # /op absent → falls back to /OP, mirroring upstream behaviour.
    assert gs.get_non_stroking_overprint_control() is True
    gs.set_non_stroking_overprint_control(False)
    assert gs.get_non_stroking_overprint_control() is False
    # Underlying /op entry written directly.
    assert gs.get_cos_object().get_item("op") is not None


def test_flatness_tolerance_alias_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_flatness_tolerance() == 1.0
    gs.set_flatness_tolerance(2.5)
    assert gs.get_flatness_tolerance() == 2.5
    assert gs.get_flatness() == 2.5
    gs.set_flatness_tolerance(None)
    assert gs.get_flatness_tolerance() == 1.0


def test_smoothness_tolerance_alias_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_smoothness_tolerance() == 0.0
    gs.set_smoothness_tolerance(0.125)
    assert gs.get_smoothness_tolerance() == 0.125
    assert gs.get_smoothness() == 0.125


def test_automatic_stroke_adjustment_alias_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_automatic_stroke_adjustment() is False
    gs.set_automatic_stroke_adjustment(True)
    assert gs.get_automatic_stroke_adjustment() is True
    assert gs.get_stroke_adjustment() is True


# ---------- SMask ----------


def test_soft_mask_round_trip_name_and_dict() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_soft_mask() is None
    none_name = COSName.get_pdf_name("None")
    gs.set_soft_mask(none_name)
    assert gs.get_soft_mask() is none_name
    # Replace with a dictionary-shaped soft mask.
    sm = COSDictionary()
    sm.set_name("S", "Luminosity")
    gs.set_soft_mask(sm)
    assert gs.get_soft_mask() is sm
    gs.set_soft_mask(None)
    assert gs.get_soft_mask() is None
    assert gs.get_cos_object().get_item("SMask") is None


# ---------- Transfer / Transfer2 ----------


def test_transfer_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_transfer() is None
    identity = COSName.get_pdf_name("Identity")
    gs.set_transfer(identity)
    assert gs.get_transfer() is identity
    gs.set_transfer(None)
    assert gs.get_transfer() is None
    assert gs.get_cos_object().get_item("TR") is None


def test_transfer2_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_transfer2() is None
    default = COSName.get_pdf_name("Default")
    gs.set_transfer2(default)
    assert gs.get_transfer2() is default
    gs.set_transfer2(None)
    assert gs.get_transfer2() is None


# ---------- Halftone ----------


def test_halftone_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_halftone() is None
    default = COSName.get_pdf_name("Default")
    gs.set_halftone(default)
    assert gs.get_halftone() is default
    # Replace with a halftone dict.
    ht = COSDictionary()
    ht.set_int("HalftoneType", 1)
    gs.set_halftone(ht)
    assert gs.get_halftone() is ht
    gs.set_halftone(None)
    assert gs.get_halftone() is None


def test_halftone_origin_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_halftone_origin() is None
    arr = COSArray()
    arr.add(COSFloat(0.0))
    arr.add(COSFloat(1.0))
    gs.set_halftone_origin(arr)
    rt = gs.get_halftone_origin()
    assert rt is arr
    gs.set_halftone_origin(None)
    assert gs.get_halftone_origin() is None


# ---------- Font setting typed wrapper ----------


def test_font_setting_typed_wrapper_round_trip() -> None:
    from pypdfbox.pdmodel.graphics.state.pd_font_setting import PDFontSetting

    gs = PDExtendedGraphicsState()
    assert gs.get_font_setting() is None
    setting = PDFontSetting()
    setting.set_font(COSName.get_pdf_name("F1"))
    setting.set_font_size(14.0)
    gs.set_font_setting(setting)
    rt = gs.get_font_setting()
    assert isinstance(rt, PDFontSetting)
    assert rt.get_font_size() == 14.0
    gs.set_font_setting(None)
    assert gs.get_font_setting() is None
    assert gs.get_cos_object().get_item("Font") is None


# ---------- Transfer (typed) ----------


def _make_type2_function() -> COSDictionary:
    from pypdfbox.cos import COSInteger

    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    fn.set_item("N", COSInteger.get(1))
    return fn


def test_transfer_array_size_not_four_returns_none() -> None:
    # Mirrors upstream: an array of size != 4 is filtered out at the raw
    # accessor (returns None) — only single-function or 4-function arrays
    # are valid per PDF 32000-1 §11.7.5.3.
    gs = PDExtendedGraphicsState()
    arr = COSArray()
    arr.add(_make_type2_function())
    arr.add(_make_type2_function())  # size 2 — invalid
    gs.get_cos_object().set_item("TR", arr)
    assert gs.get_transfer() is None


def test_transfer_typed_identity_returns_pd_function_identity() -> None:
    from pypdfbox.pdmodel.common.function.pd_function import PDFunctionTypeIdentity

    gs = PDExtendedGraphicsState()
    gs.set_transfer(COSName.get_pdf_name("Identity"))
    typed = gs.get_transfer_typed()
    assert isinstance(typed, PDFunctionTypeIdentity)


def test_transfer_typed_single_function() -> None:
    from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2

    gs = PDExtendedGraphicsState()
    gs.set_transfer(_make_type2_function())
    typed = gs.get_transfer_typed()
    assert isinstance(typed, PDFunctionType2)


def test_transfer_typed_four_array_returns_list_of_four() -> None:
    from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2

    gs = PDExtendedGraphicsState()
    arr = COSArray()
    for _ in range(4):
        arr.add(_make_type2_function())
    gs.get_cos_object().set_item("TR", arr)
    typed = gs.get_transfer_typed()
    assert isinstance(typed, list)
    assert len(typed) == 4
    assert all(isinstance(fn, PDFunctionType2) for fn in typed)


def test_transfer2_typed_default_returns_raw_name() -> None:
    gs = PDExtendedGraphicsState()
    default = COSName.get_pdf_name("Default")
    gs.set_transfer2(default)
    # /Default has no typed wrapper — caller gets the raw COSName.
    assert gs.get_transfer2_typed() is default


def test_transfer_typed_absent_returns_none() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_transfer_typed() is None
    assert gs.get_transfer2_typed() is None


# ---------- BG / BG2 (black generation) ----------


def test_black_generation_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_black_generation() is None
    fn = _make_type2_function()
    gs.set_black_generation(fn)
    assert gs.get_black_generation() is fn
    gs.set_black_generation(None)
    assert gs.get_black_generation() is None
    assert gs.get_cos_object().get_item("BG") is None


def test_black_generation_typed() -> None:
    from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2

    gs = PDExtendedGraphicsState()
    assert gs.get_black_generation_typed() is None
    gs.set_black_generation(_make_type2_function())
    typed = gs.get_black_generation_typed()
    assert isinstance(typed, PDFunctionType2)


def test_black_generation2_round_trip_and_default_name() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_black_generation2() is None
    default = COSName.get_pdf_name("Default")
    gs.set_black_generation2(default)
    assert gs.get_black_generation2() is default
    # /Default returns raw COSName from typed accessor (no wrapper).
    assert gs.get_black_generation2_typed() is default
    # Replace with a function — typed accessor wraps it.
    gs.set_black_generation2(_make_type2_function())
    from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2

    assert isinstance(gs.get_black_generation2_typed(), PDFunctionType2)
    gs.set_black_generation2(None)
    assert gs.get_black_generation2_typed() is None


# ---------- UCR / UCR2 (undercolor removal) ----------


def test_undercolor_removal_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_undercolor_removal() is None
    fn = _make_type2_function()
    gs.set_undercolor_removal(fn)
    assert gs.get_undercolor_removal() is fn
    gs.set_undercolor_removal(None)
    assert gs.get_undercolor_removal() is None


def test_undercolor_removal_typed() -> None:
    from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2

    gs = PDExtendedGraphicsState()
    gs.set_undercolor_removal(_make_type2_function())
    assert isinstance(gs.get_undercolor_removal_typed(), PDFunctionType2)


def test_undercolor_removal2_default_name() -> None:
    gs = PDExtendedGraphicsState()
    default = COSName.get_pdf_name("Default")
    gs.set_undercolor_removal2(default)
    assert gs.get_undercolor_removal2() is default
    assert gs.get_undercolor_removal2_typed() is default
    gs.set_undercolor_removal2(None)
    assert gs.get_undercolor_removal2() is None


# ---------- AAPL:AA (Apple advanced annotations) ----------


def test_advanced_annotations_round_trip() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_advanced_annotations() is None
    aa = COSDictionary()
    aa.set_int("Foo", 1)
    gs.set_advanced_annotations(aa)
    assert gs.get_advanced_annotations() is aa
    # Stored under the literal "AAPL:AA" key.
    assert gs.get_cos_object().get_dictionary_object("AAPL:AA") is aa
    gs.set_advanced_annotations(None)
    assert gs.get_advanced_annotations() is None
