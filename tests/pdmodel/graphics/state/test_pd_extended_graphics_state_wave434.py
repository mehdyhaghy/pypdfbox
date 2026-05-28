from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState


def test_copy_into_graphics_state_covers_remaining_mapping_entries() -> None:
    gs = PDExtendedGraphicsState()
    dash = COSArray()
    dash_inner = COSArray()
    dash_inner.add(COSFloat(2.0))
    dash.add(dash_inner)
    dash.add(COSFloat(1.0))

    gs.set_line_dash_pattern(dash)
    gs.set_stroking_overprint_control(True)
    gs.set_non_stroking_overprint_control(False)
    gs.set_flatness_tolerance(0.5)
    gs.set_smoothness_tolerance(0.25)
    gs.set_blend_mode(BlendMode.SCREEN)

    target: dict[str, object] = {}
    gs.copy_into_graphics_state(target)

    assert target["line_dash_pattern"] is not None
    # Mirrors upstream PDGraphicsState.setOverprint / setNonStrokingOverprint.
    assert target["overprint"] is True
    assert target["non_stroking_overprint"] is False
    assert target["flatness"] == 0.5
    assert target["smoothness"] == 0.25
    assert target["blend_mode"] is BlendMode.SCREEN


def test_copy_into_graphics_state_uses_fallback_alpha_and_text_setters() -> None:
    class Target:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        # Upstream PDGraphicsState method names — setAlphaConstant /
        # setNonStrokeAlphaConstant; the merge prefers these over the
        # earlier ``*_constants`` fallbacks.
        def set_alpha_constant(self, value: object) -> None:
            self.calls.append(("stroking_alpha", value))

        def set_non_stroke_alpha_constant(self, value: object) -> None:
            self.calls.append(("non_stroking_alpha", value))

        def set_alpha_source_flag(self, value: object) -> None:
            self.calls.append(("alpha_source_flag", value))

        def set_text_knockout_flag(self, value: object) -> None:
            self.calls.append(("text_knockout_flag", value))

    gs = PDExtendedGraphicsState()
    gs.set_stroking_alpha_constant(0.75)
    gs.set_non_stroking_alpha_constant(0.5)
    gs.set_alpha_source_flag(True)
    gs.set_text_knockout_flag(False)

    target = Target()
    gs.copy_into_graphics_state(target)

    assert ("stroking_alpha", 0.75) in target.calls
    assert ("non_stroking_alpha", 0.5) in target.calls
    assert ("alpha_source_flag", True) in target.calls
    assert ("text_knockout_flag", False) in target.calls


def test_copy_font_setting_falls_back_to_text_font_setters() -> None:
    class Target:
        def __init__(self) -> None:
            self.calls: list[tuple[str, object]] = []

        def set_text_font(self, value: object) -> None:
            self.calls.append(("text_font", value))

        def set_text_font_size(self, value: object) -> None:
            self.calls.append(("text_font_size", value))

    font = COSName.get_pdf_name("F433")
    gs = PDExtendedGraphicsState()
    gs.set_font(font)
    gs.set_font_size(13.0)

    target = Target()
    gs.copy_into_graphics_state(target)

    assert ("text_font", font) in target.calls
    assert ("text_font_size", 13.0) in target.calls


def test_copy_soft_mask_allows_none_on_attribute_target() -> None:
    class Target:
        def __init__(self) -> None:
            self.soft_mask: object = object()

    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(COSName.get_pdf_name("None"))
    target = Target()

    gs.copy_into_graphics_state(target)

    assert target.soft_mask is None


def test_soft_mask_ctm_uses_copy_when_clone_is_absent() -> None:
    class CopyOnlyMatrix:
        def __init__(self, label: str) -> None:
            self.label = label
            self.copy_calls = 0

        def copy(self) -> CopyOnlyMatrix:
            self.copy_calls += 1
            return CopyOnlyMatrix(f"{self.label}-copy")

    matrix = CopyOnlyMatrix("ctm")
    target: dict[str, object] = {"ctm": matrix}
    soft_mask = COSDictionary()
    soft_mask.set_name("S", "Alpha")
    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(soft_mask)

    gs.copy_into_graphics_state(target)

    copied_mask = target["soft_mask"]
    initial = copied_mask.get_initial_transformation_matrix()  # type: ignore[attr-defined]
    assert isinstance(initial, CopyOnlyMatrix)
    assert initial.label == "ctm-copy"
    assert matrix.copy_calls == 1


def test_soft_mask_ctm_falls_back_to_raw_value_without_copy_protocol() -> None:
    matrix = object()
    target: dict[str, object] = {"current_transformation_matrix": matrix}
    soft_mask = COSDictionary()
    soft_mask.set_name("S", "Luminosity")
    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(soft_mask)

    gs.copy_into_graphics_state(target)

    copied_mask = target["soft_mask"]
    assert copied_mask.get_initial_transformation_matrix() is matrix  # type: ignore[attr-defined]


def test_current_transformation_matrix_uses_camel_case_getter() -> None:
    class Target:
        def __init__(self) -> None:
            self.matrix = object()
            self.soft_mask = None

        def getCurrentTransformationMatrix(self) -> object:  # noqa: N802
            return self.matrix

        def set_soft_mask(self, value: object) -> None:
            self.soft_mask = value

    soft_mask = COSDictionary()
    soft_mask.set_name("S", "Alpha")
    gs = PDExtendedGraphicsState()
    gs.set_soft_mask(soft_mask)
    target = Target()

    gs.copy_into_graphics_state(target)

    assert target.soft_mask.get_initial_transformation_matrix() is target.matrix


def test_setters_remove_entries_when_none_for_less_common_functions() -> None:
    gs = PDExtendedGraphicsState()
    fn = COSDictionary()
    fn.set_int("FunctionType", 4)

    gs.set_transfer(fn)
    gs.set_transfer2(fn)
    gs.set_black_generation(fn)
    gs.set_black_generation2(fn)
    gs.set_undercolor_removal(fn)
    gs.set_undercolor_removal2(fn)
    gs.set_advanced_annotations(fn)
    gs.set_halftone(fn)
    gs.set_halftone_origin(COSArray())

    gs.set_transfer(None)
    gs.set_transfer2(None)
    gs.set_black_generation(None)
    gs.set_black_generation2(None)
    gs.set_undercolor_removal(None)
    gs.set_undercolor_removal2(None)
    gs.set_advanced_annotations(None)
    gs.set_halftone(None)
    gs.set_halftone_origin(None)

    for key in ("TR", "TR2", "BG", "BG2", "UCR", "UCR2", "AAPL:AA", "HT", "HTO"):
        assert gs.get_cos_object().get_dictionary_object(key) is None
