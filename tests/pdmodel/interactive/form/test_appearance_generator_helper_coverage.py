"""Coverage-boost tests for
``pypdfbox.pdmodel.interactive.form.appearance_generator_helper``.

The upstream Java helper has a large private surface that is reduced to
thin façades in the pypdfbox port. These tests exercise the facade so
the line/branch coverage of that file rises above 60% — they target the
text-field, multiline, password, and comb branches plus the standalone
helpers (rotation matrix, padding, glyph height, bounding-box fallback,
font-size auto-fit, formatted-value newline collapse).
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDRectangle
from pypdfbox.pdmodel.font import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.appearance_generator_helper import (
    AppearanceGeneratorHelper,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources

_RECT = COSName.get_pdf_name("Rect")
_DA = COSName.get_pdf_name("DA")
_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_Q = COSName.get_pdf_name("Q")
_HELV = COSName.get_pdf_name("Helv")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _attach_default_resources(acro_form: PDAcroForm) -> None:
    """Install a /DR with a /Helv font so PDDefaultAppearanceString can
    resolve the /Helv alias from the /DA string."""
    dr = PDResources()
    dr.put(_HELV, PDFontFactory.create_default_font(Standard14Fonts.HELVETICA))
    acro_form.set_default_resources(dr)


def _make_text_field(
    acro_form: PDAcroForm,
    width: float = 200.0,
    height: float = 20.0,
    da: str = "/Helv 12 Tf 0 g",
    with_dr: bool = True,
) -> PDTextField:
    if with_dr and acro_form.get_default_resources() is None:
        _attach_default_resources(acro_form)
    tf = PDTextField(acro_form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, width, height))
    tf.get_cos_object().set_string(_DA, da)
    return tf


# ---------- constructor + accessors ----------


def test_constructor_resolves_default_appearance_for_text_field() -> None:
    acro_form = PDAcroForm()
    acro_form.set_default_appearance("/Helv 12 Tf 0 g")
    tf = _make_text_field(acro_form)
    helper = AppearanceGeneratorHelper(tf)
    da = helper.get_default_appearance()
    assert da is not None
    assert helper.get_field() is tf
    assert helper.get_value() == ""


def test_constructor_swallows_generic_exception_to_none() -> None:
    class _BadField:
        def get_default_appearance_string(self):
            raise RuntimeError("boom")

    helper = AppearanceGeneratorHelper(_BadField())  # type: ignore[arg-type]
    assert helper.get_default_appearance() is None


def test_constructor_propagates_oserror() -> None:
    class _IOField:
        def get_default_appearance_string(self):
            raise OSError("io")

    with pytest.raises(OSError, match="io"):
        AppearanceGeneratorHelper(_IOField())  # type: ignore[arg-type]


# ---------- set_appearance_value drives the generator ----------


def test_set_appearance_value_stores_value_and_emits_show_text() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    helper = AppearanceGeneratorHelper(tf)
    helper.set_appearance_value("Hello")
    assert helper.get_value() == "Hello"
    body = (
        tf.get_widgets()[0]
        .get_cos_object()
        .get_dictionary_object(_AP)
        .get_dictionary_object(_N)
        .create_input_stream()
        .read()
    )
    assert b"Hello" in body


def test_set_appearance_value_none_becomes_empty_string() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    helper = AppearanceGeneratorHelper(tf)
    helper.set_appearance_value(None)
    assert helper.get_value() == ""


# ---------- get_formatted_value newline collapse ----------


def test_formatted_value_collapses_lf_cr_and_crlf() -> None:
    assert (
        AppearanceGeneratorHelper.get_formatted_value("a\nb\r\nc\rd")
        == "a b c d"
    )


def test_formatted_value_passthrough_when_no_newline() -> None:
    assert AppearanceGeneratorHelper.get_formatted_value("plain") == "plain"


# ---------- validate_and_ensure_acro_form_resources ----------


def test_validate_and_ensure_acro_form_resources_no_acroform() -> None:
    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            raise AttributeError

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    # No exception is raised.
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_acroform_none() -> None:
    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            return None

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_with_real_field() -> None:
    """Wave 1372: regenerated widget appearances now key the font by the
    source ``/DA`` alias (``/Helv``) instead of an auto-allocated
    ``/F0``. ``validate_and_ensure_acro_form_resources`` sees the alias
    is already present in the form's ``/DR`` and skips the hoist — no
    ``TypeError`` reaches the call site.
    """
    acro_form = PDAcroForm()
    acro_form.set_default_appearance("/Helv 12 Tf 0 g")
    tf = _make_text_field(acro_form)
    tf.set_value("hi", regenerate_appearance=True)
    helper = AppearanceGeneratorHelper(tf)
    # No exception — the alias already lives in /DR (added by
    # ``_attach_default_resources``).
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_widget_stream_none() -> None:
    class _Widget:
        def get_normal_appearance_stream(self):
            return None

    class _AcroForm:
        def get_default_resources(self):
            class _R:
                pass

            return _R()

    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            return _AcroForm()

        def get_widgets(self):
            return [_Widget()]

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_widget_no_resources() -> None:
    class _Stream:
        def get_resources(self):
            return None

    class _Widget:
        def get_normal_appearance_stream(self):
            return _Stream()

    class _AcroForm:
        def get_default_resources(self):
            class _R:
                pass

            return _R()

    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            return _AcroForm()

        def get_widgets(self):
            return [_Widget()]

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_default_resources_none() -> None:
    class _AcroForm:
        def get_default_resources(self):
            return None

    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            return _AcroForm()

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_widget_attribute_error() -> None:
    class _Widget:
        def get_normal_appearance_stream(self):
            raise AttributeError

    class _AcroForm:
        def get_default_resources(self):
            class _R:
                pass

            return _R()

    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            return _AcroForm()

        def get_widgets(self):
            return [_Widget()]

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    helper.validate_and_ensure_acro_form_resources()


def test_validate_and_ensure_acro_form_resources_hoists_missing_font() -> None:
    """Walk into the inner ``put`` branch — widget has a font the form
    doesn't, so it gets copied over."""
    sentinel_font = object()

    class _AcroFormResources:
        def __init__(self) -> None:
            self.put_calls: list[tuple[str, object]] = []

        def get_font(self, name):
            return None

        def put(self, name, value):
            self.put_calls.append((name, value))

    class _WidgetResources:
        def get_font_names(self):
            return ["F1"]

        def get_font(self, name):
            return sentinel_font

    class _Stream:
        def get_resources(self):
            return _WidgetResources()

    class _Widget:
        def get_normal_appearance_stream(self):
            return _Stream()

    acro_form_resources = _AcroFormResources()

    class _AcroForm:
        def get_default_resources(self):
            return acro_form_resources

    class _Field:
        def get_default_appearance_string(self):
            return None

        def get_acro_form(self):
            return _AcroForm()

        def get_widgets(self):
            return [_Widget()]

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    helper.validate_and_ensure_acro_form_resources()
    assert acro_form_resources.put_calls == [("F1", sentinel_font)]


# ---------- is_valid_appearance_stream ----------


def test_is_valid_appearance_stream_none_is_false() -> None:
    assert AppearanceGeneratorHelper.is_valid_appearance_stream(None) is False


def test_is_valid_appearance_stream_non_stream_is_false() -> None:
    class _Obj:
        def is_stream(self):
            return False

    assert AppearanceGeneratorHelper.is_valid_appearance_stream(_Obj()) is False


def test_is_valid_appearance_stream_missing_bbox_is_false() -> None:
    class _Stream:
        def is_stream(self):
            return True

        def get_appearance_stream(self):
            class _AS:
                def get_b_box(self):
                    return None

            return _AS()

    assert AppearanceGeneratorHelper.is_valid_appearance_stream(_Stream()) is False


def test_is_valid_appearance_stream_with_real_rect_is_true() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 50.0)

    class _AS:
        def get_b_box(self):
            return rect

    class _Stream:
        def is_stream(self):
            return True

        def get_appearance_stream(self):
            return _AS()

    assert AppearanceGeneratorHelper.is_valid_appearance_stream(_Stream()) is True


def test_is_valid_appearance_stream_attribute_error_is_false() -> None:
    class _Stream:
        def is_stream(self):
            return True

        def get_appearance_stream(self):
            raise AttributeError

    assert AppearanceGeneratorHelper.is_valid_appearance_stream(_Stream()) is False


# ---------- prepare_normal_appearance_stream ----------


def test_prepare_normal_appearance_stream_returns_form_xobject() -> None:
    rect = PDRectangle(0.0, 0.0, 100.0, 20.0)

    class _Widget:
        def get_rectangle(self):
            return rect

    class _Field:
        def get_default_appearance_string(self):
            return None

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    appearance = helper.prepare_normal_appearance_stream(_Widget())
    # COSStream wrapping a /Form xobject.
    assert appearance.get_name(COSName.get_pdf_name("Subtype")) == "Form"


# ---------- get_widget_default_appearance_string ----------


def test_get_widget_default_appearance_string_resolves_widget_da() -> None:
    # Wave 1357 added COSName.DA to the predefine catalogue; the helper
    # now returns a real PDDefaultAppearanceString built from the
    # widget's /DA value.
    from pypdfbox.pdmodel.interactive.form.pd_default_appearance_string import (
        PDDefaultAppearanceString,
    )

    acro_form = PDAcroForm()
    acro_form.set_default_appearance("/Helv 12 Tf 0 g")
    tf = _make_text_field(acro_form)
    widget = tf.get_widgets()[0]
    widget.get_cos_object().set_string(_DA, "/Helv 18 Tf 0 g")
    helper = AppearanceGeneratorHelper(tf)
    result = helper.get_widget_default_appearance_string(widget)
    assert isinstance(result, PDDefaultAppearanceString)


# ---------- resolve_rotation ----------


def test_resolve_rotation_no_characteristics_returns_zero() -> None:
    class _Widget:
        def get_appearance_characteristics(self):
            return None

    assert AppearanceGeneratorHelper.resolve_rotation(_Widget()) == 0


def test_resolve_rotation_returns_widget_rotation() -> None:
    class _Chars:
        def get_rotation(self):
            return 270

    class _Widget:
        def get_appearance_characteristics(self):
            return _Chars()

    assert AppearanceGeneratorHelper.resolve_rotation(_Widget()) == 270


# ---------- initialize_appearance_content / set_appearance_content /
#            insert_generated_appearance stubs delegate to the generator ----


def test_initialize_set_insert_appearance_stubs_delegate() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    helper = AppearanceGeneratorHelper(tf)
    helper.set_appearance_value("delegated")
    # All three façades funnel through PDAppearanceGenerator and should
    # return without raising.
    helper.initialize_appearance_content(None, None, None)
    helper.set_appearance_content(None, None)
    helper.insert_generated_appearance(None, None, None)


# ---------- get_text_align ----------


def test_get_text_align_falls_back_to_field_q_when_widget_has_no_q() -> None:
    # Wave 1372 registered ``COSName.Q``. ``get_text_align`` now returns
    # the field's quadding value when the widget COS dict has no /Q.
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_q(2)
    helper = AppearanceGeneratorHelper(tf)
    widget = tf.get_widgets()[0]
    assert helper.get_text_align(widget) == 2


def test_get_text_align_returns_zero_when_field_lacks_get_q() -> None:
    class _Field:
        def get_default_appearance_string(self):
            return None

    class _Widget:
        def get_cos_object(self):
            return COSDictionary()

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    # field has no get_q → caught → fallback 0; widget has no /Q either.
    assert helper.get_text_align(_Widget()) == 0


# ---------- calculate_matrix ----------


def test_calculate_matrix_zero_rotation_is_identity() -> None:
    helper = AppearanceGeneratorHelper.__new__(AppearanceGeneratorHelper)
    bbox = PDRectangle(0.0, 0.0, 100.0, 50.0)
    assert helper.calculate_matrix(bbox, 0) == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_calculate_matrix_ninety_degrees_translates_y_to_x() -> None:
    helper = AppearanceGeneratorHelper.__new__(AppearanceGeneratorHelper)
    bbox = PDRectangle(0.0, 0.0, 100.0, 50.0)
    m = helper.calculate_matrix(bbox, 90)
    # cos(90)≈0, sin(90)=1, tx=ury=50, ty=0
    assert math.isclose(m[0], 0.0, abs_tol=1e-9)
    assert math.isclose(m[1], 1.0)
    assert math.isclose(m[2], -1.0)
    assert math.isclose(m[3], 0.0, abs_tol=1e-9)
    assert m[4] == 50.0
    assert m[5] == 0.0


def test_calculate_matrix_one_eighty_translates_both_axes() -> None:
    helper = AppearanceGeneratorHelper.__new__(AppearanceGeneratorHelper)
    bbox = PDRectangle(0.0, 0.0, 100.0, 50.0)
    m = helper.calculate_matrix(bbox, 180)
    assert m[4] == 50.0
    assert m[5] == 100.0


def test_calculate_matrix_two_seventy_translates_x_to_y() -> None:
    helper = AppearanceGeneratorHelper.__new__(AppearanceGeneratorHelper)
    bbox = PDRectangle(0.0, 0.0, 100.0, 50.0)
    m = helper.calculate_matrix(bbox, 270)
    assert m[4] == 0.0
    assert m[5] == 100.0


# ---------- is_multi_line ----------


def test_is_multi_line_true_for_multiline_text_field() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_multiline(True)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.is_multi_line() is True


def test_is_multi_line_false_for_single_line_text_field() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.is_multi_line() is False


def test_is_multi_line_false_for_non_text_field() -> None:
    class _Field:
        def get_default_appearance_string(self):
            return None

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    assert helper.is_multi_line() is False


# ---------- shall_comb ----------


def test_shall_comb_true_for_comb_text_field_with_max_len() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_comb(True)
    tf.set_max_len(5)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.shall_comb() is True


def test_shall_comb_false_when_no_max_len() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_comb(True)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.shall_comb() is False


def test_shall_comb_false_when_multiline() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_comb(True)
    tf.set_max_len(5)
    tf.set_multiline(True)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.shall_comb() is False


def test_shall_comb_false_when_password() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_comb(True)
    tf.set_max_len(5)
    tf.set_password(True)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.shall_comb() is False


def test_shall_comb_false_when_file_select() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_comb(True)
    tf.set_max_len(5)
    tf.set_file_select(True)
    helper = AppearanceGeneratorHelper(tf)
    assert helper.shall_comb() is False


def test_shall_comb_false_for_non_text_field() -> None:
    class _Field:
        def get_default_appearance_string(self):
            return None

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    assert helper.shall_comb() is False


# ---------- comb / listbox insertion stubs ----------


def test_insert_generated_comb_appearance_delegates() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    tf.set_comb(True)
    tf.set_max_len(4)
    helper = AppearanceGeneratorHelper(tf)
    helper.set_appearance_value("ABCD")
    helper.insert_generated_comb_appearance(None, None, None, 10.0)


def test_insert_generated_listbox_selection_highlight_returns_none() -> None:
    class _Field:
        def get_default_appearance_string(self):
            return None

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    assert (
        helper.insert_generated_listbox_selection_highlight(
            None, None, None, 10.0
        )
        is None
    )


def test_insert_generated_listbox_appearance_delegates() -> None:
    acro_form = PDAcroForm()
    tf = _make_text_field(acro_form)
    helper = AppearanceGeneratorHelper(tf)
    helper.set_appearance_value("opt")
    helper.insert_generated_listbox_appearance(None, None, None, None, 10.0)


# ---------- write_to_stream ----------


def test_write_to_stream_replaces_payload() -> None:
    class _AS:
        def __init__(self) -> None:
            self._cos = COSStream()

        def get_cos_object(self):
            return self._cos

    appearance = _AS()
    AppearanceGeneratorHelper.write_to_stream(b"Hello, world", appearance)
    assert appearance._cos.create_input_stream().read() == b"Hello, world"


# ---------- calculate_font_size ----------


def test_calculate_font_size_returns_default_when_no_default_appearance() -> (
    None
):
    class _Field:
        def get_default_appearance_string(self):
            return None

    helper = AppearanceGeneratorHelper(_Field())  # type: ignore[arg-type]
    assert (
        helper.calculate_font_size(None, PDRectangle(0, 0, 100, 30))
        == AppearanceGeneratorHelper.DEFAULT_FONT_SIZE
    )


def test_calculate_font_size_returns_explicit_size_from_da() -> None:
    acro_form = PDAcroForm()
    acro_form.set_default_appearance("/Helv 16 Tf 0 g")
    tf = _make_text_field(acro_form, da="/Helv 16 Tf 0 g")
    helper = AppearanceGeneratorHelper(tf)
    size = helper.calculate_font_size(None, PDRectangle(0, 0, 100, 30))
    assert size == 16.0


def test_calculate_font_size_auto_size_when_da_size_zero() -> None:
    acro_form = PDAcroForm()
    acro_form.set_default_appearance("/Helv 0 Tf 0 g")
    tf = _make_text_field(acro_form, da="/Helv 0 Tf 0 g")
    helper = AppearanceGeneratorHelper(tf)
    # height=30 → auto-sized; just ensure it's a sensible positive float
    size = helper.calculate_font_size(None, PDRectangle(0, 0, 100, 30))
    assert size > 0.0


def test_calculate_font_size_attribute_error_on_rect_returns_default() -> None:
    acro_form = PDAcroForm()
    acro_form.set_default_appearance("/Helv 0 Tf 0 g")
    tf = _make_text_field(acro_form, da="/Helv 0 Tf 0 g")
    helper = AppearanceGeneratorHelper(tf)
    assert (
        helper.calculate_font_size(None, object())
        == AppearanceGeneratorHelper.DEFAULT_FONT_SIZE
    )


# ---------- resolve_cap_height / resolve_descent / resolve_glyph_height ----


class _Bounds:
    def __init__(self, height: float) -> None:
        self._h = height

    def get_height(self):
        return self._h


class _Path:
    def __init__(self, height: float) -> None:
        self._h = height

    def get_bounds_2d(self):
        return _Bounds(self._h)


class _StubGlyphFont:
    def __init__(self, heights: dict[int, float]) -> None:
        self._heights = heights

    def get_path(self, code: int):
        return _Path(self._heights[code]) if code in self._heights else None


def test_resolve_glyph_height_returns_path_height() -> None:
    font = _StubGlyphFont({ord("H"): 700.0})
    assert (
        AppearanceGeneratorHelper.resolve_glyph_height(font, ord("H")) == 700.0
    )


def test_resolve_glyph_height_missing_path_returns_negative_one() -> None:
    font = _StubGlyphFont({})
    assert AppearanceGeneratorHelper.resolve_glyph_height(font, ord("H")) == -1.0


def test_resolve_glyph_height_oserror_path_returns_negative_one() -> None:
    class _BadFont:
        def get_path(self, code: int):
            raise OSError("io")

    assert (
        AppearanceGeneratorHelper.resolve_glyph_height(_BadFont(), ord("H"))
        == -1.0
    )


def test_resolve_glyph_height_attribute_error_path_returns_negative_one() -> (
    None
):
    class _NoPath:
        pass

    assert (
        AppearanceGeneratorHelper.resolve_glyph_height(_NoPath(), ord("H"))
        == -1.0
    )


def test_resolve_glyph_height_falls_back_to_height_attribute() -> None:
    class _SimplePath:
        height = 250.0

    class _Font:
        def get_path(self, code: int):
            return _SimplePath()

    assert (
        AppearanceGeneratorHelper.resolve_glyph_height(_Font(), ord("X"))
        == 250.0
    )


def test_resolve_glyph_height_path_with_no_height_attribute_returns_negative_one() -> (
    None
):
    class _UnknownPath:
        pass

    class _Font:
        def get_path(self, code: int):
            return _UnknownPath()

    assert (
        AppearanceGeneratorHelper.resolve_glyph_height(_Font(), ord("X"))
        == -1.0
    )


def test_resolve_cap_height_uses_h_glyph() -> None:
    font = _StubGlyphFont({ord("H"): 700.0})
    assert AppearanceGeneratorHelper.resolve_cap_height(font) == 700.0


def test_resolve_descent_subtracts_a_from_y() -> None:
    font = _StubGlyphFont({ord("y"): -200.0, ord("a"): 500.0})
    assert AppearanceGeneratorHelper.resolve_descent(font) == -700.0


# ---------- resolve_bounding_box ----------


def test_resolve_bounding_box_returns_stream_bbox_when_present() -> None:
    rect = PDRectangle(10.0, 20.0, 200.0, 100.0)

    class _AS:
        def get_b_box(self):
            return rect

    assert AppearanceGeneratorHelper.resolve_bounding_box(None, _AS()) is rect


def test_resolve_bounding_box_falls_back_to_widget_rectangle() -> None:
    rect = PDRectangle(10.0, 20.0, 200.0, 100.0)

    class _AS:
        def get_b_box(self):
            return None

    class _Widget:
        def get_rectangle(self):
            return rect

    out = AppearanceGeneratorHelper.resolve_bounding_box(_Widget(), _AS())
    # create_retranslated_rectangle yields origin-anchored copy.
    assert out.get_lower_left_x() == 0.0
    assert out.get_lower_left_y() == 0.0
    assert out.get_width() == 190.0
    assert out.get_height() == 80.0


# ---------- apply_padding ----------


def test_apply_padding_inset_returns_smaller_rectangle() -> None:
    # Wave 1357 re-exported PDRectangle from pypdfbox.pdmodel.common.
    # ``apply_padding`` now returns the inset rectangle.
    box = PDRectangle(0.0, 0.0, 100.0, 50.0)
    inset = AppearanceGeneratorHelper.apply_padding(box, 2.0)
    assert inset.get_lower_left_x() == 2.0
    assert inset.get_lower_left_y() == 2.0
    assert inset.get_width() == 96.0
    assert inset.get_height() == 46.0
