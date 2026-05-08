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
    item = gs.get_cos_object().get_item("BM")
    assert isinstance(item, COSName)
    assert item.get_name() == "Screen"


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


def test_get_stroke_overprint_snake_case_alias() -> None:
    """``get_stroke_overprint()`` is the PEP 8 spelling of the legacy
    ``get_strokeOverprint()`` accessor — both must read the same /OP
    boolean and stay in sync after each setter.
    """
    gs = PDExtendedGraphicsState()
    assert gs.get_stroke_overprint() is False
    assert gs.get_stroke_overprint() == gs.get_strokeOverprint()
    gs.set_stroke_overprint(True)
    assert gs.get_stroke_overprint() is True
    assert gs.get_stroke_overprint() == gs.get_strokeOverprint()


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


def test_copy_into_graphics_state_copies_soft_mask_and_initial_ctm() -> None:
    from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask

    class Matrix:
        def __init__(self, label: str) -> None:
            self.label = label
            self.clone_calls = 0

        def clone(self) -> Matrix:
            self.clone_calls += 1
            return Matrix(f"{self.label}-clone")

    class Target:
        def __init__(self, matrix: Matrix) -> None:
            self._matrix = matrix
            self.soft_masks: list[object] = []

        def get_current_transformation_matrix(self) -> Matrix:
            return self._matrix

        def set_soft_mask(self, soft_mask: object) -> None:
            self.soft_masks.append(soft_mask)

    sm_dict = COSDictionary()
    sm_dict.set_name("S", "Alpha")
    matrix = Matrix("active")
    target = Target(matrix)
    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(sm_dict)

    gs.copy_into_graphics_state(target)

    assert len(target.soft_masks) == 1
    soft_mask = target.soft_masks[0]
    assert isinstance(soft_mask, PDSoftMask)
    assert soft_mask.get_cos_object() is sm_dict
    initial = soft_mask.get_initial_transformation_matrix()
    assert isinstance(initial, Matrix)
    assert initial is not matrix
    assert initial.label == "active-clone"
    assert matrix.clone_calls == 1


def test_copy_into_graphics_state_none_soft_mask_clears_mapping_target() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(COSName.get_pdf_name("None"))

    existing = object()
    target: dict[str, object | None] = {"soft_mask": existing}
    gs.copy_into_graphics_state(target)

    assert target["soft_mask"] is None


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


# ---------- resource cache (upstream two-arg constructor) ----------


def test_default_constructor_resource_cache_is_none() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_resource_cache() is None


def test_constructor_accepts_resource_cache() -> None:
    cache = object()  # opaque sentinel
    gs = PDExtendedGraphicsState(COSDictionary(), cache)
    assert gs.get_resource_cache() is cache


def test_resource_cache_propagates_to_typed_soft_mask() -> None:
    from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask

    cache = object()
    gs = PDExtendedGraphicsState(COSDictionary(), cache)
    sm_dict = COSDictionary()
    sm_dict.set_name("S", "Luminosity")
    gs.set_soft_mask(sm_dict)
    sm = gs.get_soft_mask_typed()
    assert isinstance(sm, PDSoftMask)
    # Resource cache plumbed through PDSoftMask.create.
    assert sm.get_resource_cache() is cache


# ---------- RenderingIntent (typed enum) ----------


def test_rendering_intent_enum_string_value_round_trip() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingIntent

    assert RenderingIntent.PERCEPTUAL.string_value() == "Perceptual"
    assert (
        RenderingIntent.ABSOLUTE_COLORIMETRIC.string_value()
        == "AbsoluteColorimetric"
    )
    assert (
        RenderingIntent.RELATIVE_COLORIMETRIC.string_value()
        == "RelativeColorimetric"
    )
    assert RenderingIntent.SATURATION.string_value() == "Saturation"


def test_rendering_intent_from_string_known_values() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingIntent

    assert RenderingIntent.from_string("Perceptual") is RenderingIntent.PERCEPTUAL
    assert (
        RenderingIntent.from_string("Saturation") is RenderingIntent.SATURATION
    )
    assert (
        RenderingIntent.from_string("AbsoluteColorimetric")
        is RenderingIntent.ABSOLUTE_COLORIMETRIC
    )
    assert (
        RenderingIntent.from_string("RelativeColorimetric")
        is RenderingIntent.RELATIVE_COLORIMETRIC
    )


def test_rendering_intent_from_string_unknown_falls_back() -> None:
    """Per PDF 32000-1 §8.6.5.8 — an unrecognised name maps to
    RelativeColorimetric. Mirrors upstream ``RenderingIntent.fromString``.
    """
    from pypdfbox.pdmodel.graphics.state import RenderingIntent

    assert (
        RenderingIntent.from_string("Bogus")
        is RenderingIntent.RELATIVE_COLORIMETRIC
    )
    assert (
        RenderingIntent.from_string("")
        is RenderingIntent.RELATIVE_COLORIMETRIC
    )
    assert (
        RenderingIntent.from_string(None)
        is RenderingIntent.RELATIVE_COLORIMETRIC
    )


def test_get_rendering_intent_typed_round_trip() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingIntent

    gs = PDExtendedGraphicsState()
    assert gs.get_rendering_intent_typed() is None
    gs.set_rendering_intent("Saturation")
    assert gs.get_rendering_intent_typed() is RenderingIntent.SATURATION


def test_get_rendering_intent_typed_unknown_uses_default() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingIntent

    gs = PDExtendedGraphicsState()
    # Force an unrecognised /RI value through the dict layer.
    gs.get_cos_object().set_name("RI", "Bogus")
    assert (
        gs.get_rendering_intent_typed() is RenderingIntent.RELATIVE_COLORIMETRIC
    )


def test_set_rendering_intent_accepts_enum() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingIntent

    gs = PDExtendedGraphicsState()
    gs.set_rendering_intent(RenderingIntent.PERCEPTUAL)
    # Stored as the spec name string.
    assert gs.get_rendering_intent() == "Perceptual"
    assert gs.get_rendering_intent_typed() is RenderingIntent.PERCEPTUAL
    gs.set_rendering_intent(RenderingIntent.ABSOLUTE_COLORIMETRIC)
    assert gs.get_rendering_intent() == "AbsoluteColorimetric"
    gs.set_rendering_intent(None)
    assert gs.get_rendering_intent() is None
    assert gs.get_rendering_intent_typed() is None
    assert gs.get_cos_object().get_item("RI") is None


# ---------- Wave 180: line cap / join constants ----------


def test_line_cap_constants_match_spec_codes() -> None:
    """PDF 32000-1 §8.4.3.3 (Table 54): /LC entry is 0/1/2 for
    butt/round/projecting-square. Constants should match those codes
    so downstream code can avoid magic numbers."""
    assert PDExtendedGraphicsState.BUTT_CAP == 0
    assert PDExtendedGraphicsState.ROUND_CAP == 1
    assert PDExtendedGraphicsState.PROJECTING_SQUARE_CAP == 2


def test_line_join_constants_match_spec_codes() -> None:
    """PDF 32000-1 §8.4.3.4 (Table 55): /LJ entry is 0/1/2 for
    miter/round/bevel."""
    assert PDExtendedGraphicsState.MITER_JOIN == 0
    assert PDExtendedGraphicsState.ROUND_JOIN == 1
    assert PDExtendedGraphicsState.BEVEL_JOIN == 2


def test_line_cap_constants_round_trip_through_setter() -> None:
    """Setting and reading via the named constants stores the matching
    integer code in the dictionary — i.e. constants are interchangeable
    with their literal int values."""
    gs = PDExtendedGraphicsState()
    gs.set_line_cap_style(PDExtendedGraphicsState.PROJECTING_SQUARE_CAP)
    assert gs.get_line_cap_style() == 2
    assert gs.get_line_cap_style() == PDExtendedGraphicsState.PROJECTING_SQUARE_CAP


def test_line_join_constants_round_trip_through_setter() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_line_join_style(PDExtendedGraphicsState.BEVEL_JOIN)
    assert gs.get_line_join_style() == 2
    assert gs.get_line_join_style() == PDExtendedGraphicsState.BEVEL_JOIN


# ---------- Wave 180: get_line_dash_pattern defensive shape check ----------


def test_get_line_dash_pattern_returns_none_when_d_is_not_array() -> None:
    """Upstream's getLineDashPattern silently returns null for any
    malformed /D entry — the rest of the ExtGState dictionary stays
    usable. We must mirror that defensive behaviour rather than raising."""
    gs = PDExtendedGraphicsState()
    gs.get_cos_object().set_name("D", "BadValue")
    assert gs.get_line_dash_pattern() is None


def test_get_line_dash_pattern_returns_none_when_size_not_two() -> None:
    """Per PDF 32000-1 §8.4.3.6 the on-disk form is exactly
    [dash_array, phase] (size 2). A wrong-size COSArray must be treated
    as absent, matching upstream's ``dp.size() == 2`` guard."""
    gs = PDExtendedGraphicsState()
    arr = COSArray()
    inner = COSArray()
    inner.add(COSFloat(3.0))
    arr.add(inner)
    arr.add(COSFloat(0.0))
    arr.add(COSName.get_pdf_name("Extra"))  # makes size 3
    gs.get_cos_object().set_item("D", arr)
    assert gs.get_line_dash_pattern() is None


def test_get_line_dash_pattern_returns_none_when_inner_not_array() -> None:
    """Upstream's instanceof guard rejects /D entries whose first slot
    isn't a COSArray; ours must do the same instead of raising."""
    gs = PDExtendedGraphicsState()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("BadInner"))
    arr.add(COSFloat(0.0))
    gs.get_cos_object().set_item("D", arr)
    assert gs.get_line_dash_pattern() is None


def test_get_line_dash_pattern_returns_none_when_phase_not_number() -> None:
    """Upstream rejects entries whose phase slot isn't a COSNumber."""
    gs = PDExtendedGraphicsState()
    arr = COSArray()
    inner = COSArray()
    inner.add(COSFloat(3.0))
    arr.add(inner)
    arr.add(COSName.get_pdf_name("NotANumber"))
    gs.get_cos_object().set_item("D", arr)
    assert gs.get_line_dash_pattern() is None


def test_get_line_dash_pattern_well_formed_round_trips() -> None:
    """Sanity check: the defensive guards don't break the well-formed
    case — a [[3, 2], 0] pattern still resolves to a typed wrapper."""
    from pypdfbox.cos import COSInteger
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

    gs = PDExtendedGraphicsState()
    arr = COSArray()
    inner = COSArray()
    inner.add(COSFloat(3.0))
    inner.add(COSFloat(2.0))
    arr.add(inner)
    arr.add(COSInteger.get(0))
    gs.get_cos_object().set_item("D", arr)
    pattern = gs.get_line_dash_pattern()
    assert isinstance(pattern, PDLineDashPattern)
    assert pattern.get_dash_array() == [3.0, 2.0]
    assert pattern.get_phase() == 0


# ---------- Wave 180: copy_into_graphics_state TR / TR2 precedence ----------


def test_copy_into_graphics_state_copies_transfer() -> None:
    """When only /TR is present, copy_into_graphics_state should forward
    the function to the target's set_transfer setter."""
    gs = PDExtendedGraphicsState()
    identity = COSName.get_pdf_name("Identity")
    gs.set_transfer(identity)
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert target.get("transfer") is identity


def test_copy_into_graphics_state_copies_transfer2() -> None:
    """When only /TR2 is present, copy_into_graphics_state forwards
    /TR2's value to set_transfer (upstream uses the same setter for
    both — TR2 just carries the spec-allowed /Default name)."""
    gs = PDExtendedGraphicsState()
    default_name = COSName.get_pdf_name("Default")
    gs.set_transfer2(default_name)
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert target.get("transfer") is default_name


def test_copy_into_graphics_state_tr2_takes_precedence_over_tr() -> None:
    """PDF 32000-1 §11.7.5.3: 'If both TR and TR2 are present in the
    same graphics state parameter dictionary, TR2 shall take
    precedence.' The /TR branch must skip when /TR2 is also present so
    the /TR2 value wins regardless of dictionary key order."""
    gs = PDExtendedGraphicsState()
    tr_value = COSName.get_pdf_name("Identity")
    tr2_value = COSName.get_pdf_name("Default")
    gs.set_transfer(tr_value)
    gs.set_transfer2(tr2_value)
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    # /TR2 wins — final value must be tr2_value, never tr_value.
    assert target.get("transfer") is tr2_value


# ---------------------------------------------------------------------------
# _default_if_none — spec defaults for /LW, /ML, /CA, /CA_NS during copy
# ---------------------------------------------------------------------------


def test_default_if_none_returns_value_when_present() -> None:
    assert PDExtendedGraphicsState._default_if_none(2.5, 1.0) == 2.5
    # 0.0 is a valid value — must not be replaced with the default.
    assert PDExtendedGraphicsState._default_if_none(0.0, 99.0) == 0.0


def test_default_if_none_returns_default_when_none() -> None:
    assert PDExtendedGraphicsState._default_if_none(None, 1.0) == 1.0
    assert PDExtendedGraphicsState._default_if_none(None, 10.0) == 10.0


def test_copy_into_graphics_state_lw_uses_spec_default_when_value_missing() -> None:
    """Mirror upstream ``defaultIfNull(getLineWidth(), 1)`` — a /LW key
    present with a non-numeric value still pushes the spec default 1.0
    into the target, matching Java's null-safe unboxing."""
    gs = PDExtendedGraphicsState()
    # Set /LW key to something non-numeric so get_line_width() returns None.
    gs.get_cos_object().set_item(COSName.get_pdf_name("LW"), COSName.get_pdf_name("Bogus"))
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert target.get("line_width") == 1.0


def test_copy_into_graphics_state_lw_well_formed_passes_through() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_line_width(2.5)
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert target.get("line_width") == 2.5


def test_copy_into_graphics_state_ml_uses_spec_default_when_value_missing() -> None:
    """Upstream miter-limit default is 10.0 (PDF 32000-1 §8.4.3.5)."""
    gs = PDExtendedGraphicsState()
    gs.get_cos_object().set_item(COSName.get_pdf_name("ML"), COSName.get_pdf_name("Bogus"))
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert target.get("miter_limit") == 10.0


def test_copy_into_graphics_state_ml_well_formed_passes_through() -> None:
    gs = PDExtendedGraphicsState()
    gs.set_miter_limit(7.5)
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert target.get("miter_limit") == 7.5


def test_copy_into_graphics_state_ca_uses_spec_default_when_value_missing() -> None:
    """Upstream stroking-alpha default is 1.0 (PDF 32000-1 §11.6.4.4)."""
    gs = PDExtendedGraphicsState()
    gs.get_cos_object().set_item(COSName.get_pdf_name("CA"), COSName.get_pdf_name("Bogus"))
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    # /CA copies into either alpha_constants or stroking_alpha_constant
    # (depending on which setter shape the target exposes).
    assert (
        target.get("alpha_constants") == 1.0
        or target.get("stroking_alpha_constant") == 1.0
    )


def test_copy_into_graphics_state_ca_zero_value_is_preserved() -> None:
    """Alpha 0.0 is a valid (fully transparent) value — the default
    fallback must not clobber it. Regression guard for the
    ``defaultIfNull`` semantics: only ``None`` triggers the default."""
    gs = PDExtendedGraphicsState()
    gs.set_stroking_alpha_constant(0.0)
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    # 0.0 must round-trip — not be replaced with 1.0.
    assert (
        target.get("alpha_constants") == 0.0
        or target.get("stroking_alpha_constant") == 0.0
    )


def test_copy_into_graphics_state_ca_ns_uses_spec_default_when_value_missing() -> None:
    """Non-stroking-alpha default 1.0 (PDF 32000-1 §11.6.4.4)."""
    gs = PDExtendedGraphicsState()
    gs.get_cos_object().set_item(
        COSName.get_pdf_name("ca"), COSName.get_pdf_name("Bogus")
    )
    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)
    assert (
        target.get("non_stroke_alpha_constants") == 1.0
        or target.get("non_stroking_alpha_constant") == 1.0
    )


def test_copy_into_graphics_state_lw_uses_default_with_object_target() -> None:
    """Same default-fallback path, but routed through a target that
    exposes a ``set_line_width`` setter (object form, not dict). Verifies
    the default propagates regardless of which copy-target shape the
    caller picked."""

    class Target:
        line_width: float | None = None

        def set_line_width(self, v: float) -> None:
            self.line_width = v

    gs = PDExtendedGraphicsState()
    gs.get_cos_object().set_item(COSName.get_pdf_name("LW"), COSName.get_pdf_name("Bogus"))
    target = Target()
    gs.copy_into_graphics_state(target)
    assert target.line_width == 1.0
