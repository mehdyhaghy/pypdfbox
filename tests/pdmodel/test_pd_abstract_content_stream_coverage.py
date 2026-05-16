"""Wave 1314 — coverage boost for ``PDAbstractContentStream``.

Targets the ~150 operator-emit helpers on the base class directly
(separate from :class:`PDPageContentStream`, which overrides many of
them with text-mode / path-state guards). Each test instantiates the
abstract base with a :class:`io.BytesIO` output stream and verifies
the exact bytes emitted match the PDF spec mnemonic and operand
order, mirroring the byte-level parity tests we use for the concrete
subclass.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDAbstractContentStream
from pypdfbox.pdmodel.pd_abstract_content_stream import _format_decimal


class _Concrete(PDAbstractContentStream):
    """Minimal concrete subclass — only needed because the base is abstract
    in spirit (it is not declared ``ABC`` but the upstream Java class is
    package-private)."""


class _FakeResources:
    """Stand-in for :class:`PDResources` that records added resources and
    returns deterministic :class:`COSName` keys, so we can verify ``Do``,
    ``gs``, ``sh``, ``BDC`` operand emission without pulling in the real
    resource dictionary plumbing."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.added_props: list[Any] = []
        self.added_ext: list[Any] = []

    def add(self, value: Any) -> COSName:  # noqa: D401
        self.added.append(value)
        return COSName.get_pdf_name(f"R{len(self.added)}")

    def add_property_list(self, value: Any) -> COSName:
        self.added_props.append(value)
        return COSName.get_pdf_name(f"P{len(self.added_props)}")

    def add_ext_g_state(self, value: Any) -> COSName:
        self.added_ext.append(value)
        return COSName.get_pdf_name(f"GS{len(self.added_ext)}")


def _make(resources: _FakeResources | None = None) -> tuple[_Concrete, io.BytesIO]:
    output = io.BytesIO()
    return _Concrete(None, output, resources), output


# ------------------------------------------------------------------
# _format_decimal helper
# ------------------------------------------------------------------


def test_format_decimal_int_unchanged() -> None:
    assert _format_decimal(5) == b"5"


def test_format_decimal_integer_float_drops_trailing_zero() -> None:
    assert _format_decimal(2.0) == b"2"


def test_format_decimal_trims_trailing_zeros() -> None:
    assert _format_decimal(2.5) == b"2.5"
    assert _format_decimal(0.12500) == b"0.125"


def test_format_decimal_respects_max_fraction_digits() -> None:
    assert _format_decimal(1.0 / 3.0, 2) == b"0.33"


def test_format_decimal_rejects_inf() -> None:
    with pytest.raises(ValueError):
        _format_decimal(float("inf"))


def test_format_decimal_rejects_nan() -> None:
    with pytest.raises(ValueError):
        _format_decimal(float("nan"))


def test_format_decimal_bool_handled_as_int_via_isinstance_guard() -> None:
    # The implementation explicitly excludes ``bool`` from the int branch.
    # True/False fall through to the float branch and round-trip as ``1``/``0``.
    assert _format_decimal(True) == b"1"
    assert _format_decimal(False) == b"0"


# ------------------------------------------------------------------
# Low-level emit helpers
# ------------------------------------------------------------------


def test_write_emits_iso_8859_1_bytes() -> None:
    cs, out = _make()
    cs.write("hello")
    assert out.getvalue() == b"hello"


def test_write_line_emits_lf() -> None:
    cs, out = _make()
    cs.write_line()
    assert out.getvalue() == b"\n"


def test_write_bytes_emits_raw() -> None:
    cs, out = _make()
    cs.write_bytes(b"\x01\x02\x03")
    assert out.getvalue() == b"\x01\x02\x03"


def test_write_operand_numeric_emits_value_and_space() -> None:
    cs, out = _make()
    cs.write_operand(3.14)
    assert out.getvalue() == b"3.14 "


def test_write_operand_int_emits_compact_form() -> None:
    cs, out = _make()
    cs.write_operand(42)
    assert out.getvalue() == b"42 "


def test_write_operand_cos_name_emits_slash_prefix() -> None:
    cs, out = _make()
    cs.write_operand(COSName.get_pdf_name("F1"))
    assert out.getvalue() == b"/F1 "


def test_write_operator_emits_text_and_lf() -> None:
    cs, out = _make()
    cs.write_operator("S")
    assert out.getvalue() == b"S\n"


def test_write_affine_transform_from_tuple() -> None:
    cs, out = _make()
    cs.write_affine_transform((1, 0, 0, 1, 10, 20))
    assert out.getvalue() == b"1 0 0 1 10 20 "


def test_write_affine_transform_from_object_with_getters() -> None:
    class FakeMatrix:
        def get_scale_x(self) -> float:
            return 2.0

        def get_shear_y(self) -> float:
            return 0.0

        def get_shear_x(self) -> float:
            return 0.0

        def get_scale_y(self) -> float:
            return 3.0

        def get_translate_x(self) -> float:
            return 5.0

        def get_translate_y(self) -> float:
            return 7.0

    cs, out = _make()
    cs.write_affine_transform(FakeMatrix())
    assert out.getvalue() == b"2 0 0 3 5 7 "


# ------------------------------------------------------------------
# Text-state operators (BT/ET, Td/Tm/T*, TL/Tc/Tw/Tz/Tr/Ts, Tf)
# ------------------------------------------------------------------


def test_begin_text_emits_BT_and_sets_mode() -> None:
    cs, out = _make()
    cs.begin_text()
    assert out.getvalue() == b"BT\n"
    assert cs.in_text_mode is True


def test_end_text_emits_ET_and_clears_mode() -> None:
    cs, out = _make()
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.end_text()
    assert out.getvalue() == b"ET\n"
    assert cs.in_text_mode is False


def test_begin_text_nested_raises() -> None:
    cs, _ = _make()
    cs.begin_text()
    with pytest.raises(RuntimeError):
        cs.begin_text()


def test_end_text_without_begin_raises() -> None:
    cs, _ = _make()
    with pytest.raises(RuntimeError):
        cs.end_text()


def test_set_leading_emits_TL() -> None:
    cs, out = _make()
    cs.set_leading(14.0)
    assert out.getvalue() == b"14 TL\n"


def test_new_line_emits_T_star() -> None:
    cs, out = _make()
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.new_line()
    assert out.getvalue() == b"T*\n"


def test_new_line_outside_text_mode_raises() -> None:
    cs, _ = _make()
    with pytest.raises(RuntimeError):
        cs.new_line()


def test_new_line_at_offset_emits_Td() -> None:
    cs, out = _make()
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.new_line_at_offset(10, 20)
    assert out.getvalue() == b"10 20 Td\n"


def test_new_line_at_offset_outside_text_mode_raises() -> None:
    cs, _ = _make()
    with pytest.raises(RuntimeError):
        cs.new_line_at_offset(1, 2)


def test_set_text_matrix_emits_Tm() -> None:
    cs, out = _make()
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.set_text_matrix((1, 0, 0, 1, 50, 60))
    assert out.getvalue() == b"1 0 0 1 50 60 Tm\n"


def test_set_text_matrix_outside_text_mode_raises() -> None:
    cs, _ = _make()
    with pytest.raises(RuntimeError):
        cs.set_text_matrix((1, 0, 0, 1, 0, 0))


def test_set_character_spacing_emits_Tc() -> None:
    cs, out = _make()
    cs.set_character_spacing(0.5)
    assert out.getvalue() == b"0.5 Tc\n"


def test_set_word_spacing_emits_Tw() -> None:
    cs, out = _make()
    cs.set_word_spacing(1.25)
    assert out.getvalue() == b"1.25 Tw\n"


def test_set_horizontal_scaling_emits_Tz() -> None:
    cs, out = _make()
    cs.set_horizontal_scaling(110)
    assert out.getvalue() == b"110 Tz\n"


def test_set_rendering_mode_int_emits_Tr() -> None:
    cs, out = _make()
    cs.set_rendering_mode(3)
    assert out.getvalue() == b"3 Tr\n"


def test_set_rendering_mode_enum_like_emits_value() -> None:
    class FakeMode:
        value = 7

    cs, out = _make()
    cs.set_rendering_mode(FakeMode())
    assert out.getvalue() == b"7 Tr\n"


def test_set_text_rise_emits_Ts() -> None:
    cs, out = _make()
    cs.set_text_rise(-2)
    assert out.getvalue() == b"-2 Ts\n"


# ------------------------------------------------------------------
# Font + show-text
# ------------------------------------------------------------------


class _FakeFont:
    def encode(self, text: str) -> bytes:
        return text.encode("latin-1")


def test_set_font_with_resources_emits_Tf() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    font = _FakeFont()
    cs.set_font(font, 12)
    assert out.getvalue() == b"/R1 12 Tf\n"
    assert resources.added == [font]


def test_set_font_replaces_top_of_stack() -> None:
    resources = _FakeResources()
    cs, _ = _make(resources)
    font_a, font_b = _FakeFont(), _FakeFont()
    cs.set_font(font_a, 10)
    cs.set_font(font_b, 12)
    assert list(cs._font_stack) == [font_b]


def test_show_text_requires_text_mode() -> None:
    cs, _ = _make()
    with pytest.raises(RuntimeError):
        cs.show_text("hi")


def test_show_text_requires_font_set() -> None:
    cs, _ = _make()
    cs.begin_text()
    with pytest.raises(RuntimeError):
        cs.show_text("hi")


def test_show_text_emits_hex_string_and_Tj() -> None:
    cs, out = _make()
    cs._font_stack.append(_FakeFont())
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.show_text("AB")
    # "AB" -> latin-1 0x41 0x42 -> hex "4142"
    assert out.getvalue() == b"<4142> Tj\n"


def test_show_text_with_positioning_emits_TJ() -> None:
    cs, out = _make()
    cs._font_stack.append(_FakeFont())
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.show_text_with_positioning(["A", -120, "B"])
    assert out.getvalue() == b"[<41>-120 <42>] TJ\n"


def test_show_text_with_positioning_rejects_other_types() -> None:
    cs, _ = _make()
    cs._font_stack.append(_FakeFont())
    cs.begin_text()
    with pytest.raises(ValueError):
        cs.show_text_with_positioning([object()])


# ------------------------------------------------------------------
# Image / form drawing
# ------------------------------------------------------------------


class _FakeImage:
    def get_width(self) -> int:
        return 100

    def get_height(self) -> int:
        return 50


def test_draw_image_with_dimensions_emits_cm_Do() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    image = _FakeImage()
    cs.draw_image(image, 10, 20, 100, 50)
    assert out.getvalue() == b"q\n100 0 0 50 10 20 cm\n/R1 Do\nQ\n"


def test_draw_image_uses_default_position_when_omitted() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    image = _FakeImage()
    cs.draw_image(image)
    # falls back to width/height from image, position (0,0)
    assert out.getvalue() == b"q\n100 0 0 50 0 0 cm\n/R1 Do\nQ\n"


def test_draw_image_without_resources_skips_name() -> None:
    cs, out = _make()
    cs.draw_image(_FakeImage(), 0, 0, 1, 1)
    assert out.getvalue() == b"q\n1 0 0 1 0 0 cm\nDo\nQ\n"


def test_draw_form_emits_resource_ref_and_Do() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    form = object()
    cs.draw_form(form)
    assert out.getvalue() == b"/R1 Do\n"


def test_draw_form_without_resources_emits_only_Do() -> None:
    cs, out = _make()
    cs.draw_form(object())
    assert out.getvalue() == b"Do\n"


# ------------------------------------------------------------------
# Graphics-state operators (q, Q, cm, gs)
# ------------------------------------------------------------------


def test_save_graphics_state_emits_q() -> None:
    cs, out = _make()
    cs.save_graphics_state()
    assert out.getvalue() == b"q\n"


def test_save_graphics_state_duplicates_stack_tops() -> None:
    cs, _ = _make()
    cs._stroking_color_space_stack.append("cs_s")
    cs._non_stroking_color_space_stack.append("cs_ns")
    cs._font_stack.append("F0")
    cs.save_graphics_state()
    assert list(cs._stroking_color_space_stack) == ["cs_s", "cs_s"]
    assert list(cs._non_stroking_color_space_stack) == ["cs_ns", "cs_ns"]
    assert list(cs._font_stack) == ["F0", "F0"]


def test_restore_graphics_state_emits_Q() -> None:
    cs, out = _make()
    cs.restore_graphics_state()
    assert out.getvalue() == b"Q\n"


def test_restore_graphics_state_pops_stacks() -> None:
    cs, _ = _make()
    cs._stroking_color_space_stack.extend(["a", "b"])
    cs._non_stroking_color_space_stack.extend(["c", "d"])
    cs._font_stack.extend(["x", "y"])
    cs.restore_graphics_state()
    assert list(cs._stroking_color_space_stack) == ["a"]
    assert list(cs._non_stroking_color_space_stack) == ["c"]
    assert list(cs._font_stack) == ["x"]


def test_transform_emits_cm() -> None:
    cs, out = _make()
    cs.transform((1, 0, 0, 1, 100, 200))
    assert out.getvalue() == b"1 0 0 1 100 200 cm\n"


def test_set_graphics_state_parameters_emits_gs() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    cs.set_graphics_state_parameters(object())
    assert out.getvalue() == b"/GS1 gs\n"


def test_set_graphics_state_parameters_without_resources_emits_only_gs() -> None:
    cs, out = _make()
    cs.set_graphics_state_parameters(object())
    assert out.getvalue() == b"gs\n"


# ------------------------------------------------------------------
# get_name colour-space resolution
# ------------------------------------------------------------------


def test_get_name_device_color_space_returns_cos_name() -> None:
    cs, _ = _make()

    class CS:
        def get_name(self) -> str:
            return "DeviceRGB"

    name = cs.get_name(CS())
    assert isinstance(name, COSName)
    assert name.get_name() == "DeviceRGB"


def test_get_name_non_device_uses_resources_add() -> None:
    resources = _FakeResources()
    cs, _ = _make(resources)

    class CS:
        def get_name(self) -> str:
            return "CustomCS"

    name = cs.get_name(CS())
    assert name == COSName.get_pdf_name("R1")


# ------------------------------------------------------------------
# Path-construction + painting operators
# ------------------------------------------------------------------


def test_add_rect_emits_re() -> None:
    cs, out = _make()
    cs.add_rect(10, 20, 30, 40)
    assert out.getvalue() == b"10 20 30 40 re\n"


def test_move_to_emits_m_with_operands() -> None:
    cs, out = _make()
    cs.move_to(1.5, 2.5)
    assert out.getvalue() == b"1.5 2.5 m\n"


def test_line_to_emits_l_with_operands() -> None:
    cs, out = _make()
    cs.line_to(3.0, 4.0)
    assert out.getvalue() == b"3 4 l\n"


def test_curve_to_emits_c_with_six_operands() -> None:
    cs, out = _make()
    cs.curve_to(1, 2, 3, 4, 5, 6)
    assert out.getvalue() == b"1 2 3 4 5 6 c\n"


def test_curve_to1_emits_y_with_four_operands() -> None:
    cs, out = _make()
    cs.curve_to1(1, 2, 5, 6)
    assert out.getvalue() == b"1 2 5 6 y\n"


def test_curve_to2_emits_v_with_four_operands() -> None:
    cs, out = _make()
    cs.curve_to2(3, 4, 5, 6)
    assert out.getvalue() == b"3 4 5 6 v\n"


def test_close_path_emits_h() -> None:
    cs, out = _make()
    cs.close_path()
    assert out.getvalue() == b"h\n"


def test_stroke_emits_S() -> None:
    cs, out = _make()
    cs.stroke()
    assert out.getvalue() == b"S\n"


def test_close_and_stroke_emits_s() -> None:
    cs, out = _make()
    cs.close_and_stroke()
    assert out.getvalue() == b"s\n"


def test_fill_emits_f() -> None:
    cs, out = _make()
    cs.fill()
    assert out.getvalue() == b"f\n"


def test_fill_even_odd_emits_f_star() -> None:
    cs, out = _make()
    cs.fill_even_odd()
    assert out.getvalue() == b"f*\n"


def test_fill_and_stroke_emits_B() -> None:
    cs, out = _make()
    cs.fill_and_stroke()
    assert out.getvalue() == b"B\n"


def test_fill_and_stroke_even_odd_emits_B_star() -> None:
    cs, out = _make()
    cs.fill_and_stroke_even_odd()
    assert out.getvalue() == b"B*\n"


def test_close_and_fill_and_stroke_emits_b() -> None:
    cs, out = _make()
    cs.close_and_fill_and_stroke()
    assert out.getvalue() == b"b\n"


def test_close_and_fill_and_stroke_even_odd_emits_b_star() -> None:
    cs, out = _make()
    cs.close_and_fill_and_stroke_even_odd()
    assert out.getvalue() == b"b*\n"


def test_clip_emits_W_then_n() -> None:
    cs, out = _make()
    cs.clip()
    assert out.getvalue() == b"W\nn\n"


def test_clip_even_odd_emits_W_star_then_n() -> None:
    cs, out = _make()
    cs.clip_even_odd()
    assert out.getvalue() == b"W*\nn\n"


def test_shading_fill_emits_sh_with_resource() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    cs.shading_fill(object())
    assert out.getvalue() == b"/R1 sh\n"


def test_shading_fill_without_resources_emits_only_sh() -> None:
    cs, out = _make()
    cs.shading_fill(object())
    assert out.getvalue() == b"sh\n"


# ------------------------------------------------------------------
# Line state operators (w, J, j, M, d)
# ------------------------------------------------------------------


def test_set_line_width_emits_w() -> None:
    cs, out = _make()
    cs.set_line_width(2.5)
    assert out.getvalue() == b"2.5 w\n"


def test_set_line_join_style_emits_j() -> None:
    cs, out = _make()
    cs.set_line_join_style(2)
    assert out.getvalue() == b"2 j\n"


def test_set_line_join_style_rejects_invalid() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_line_join_style(3)


def test_set_line_cap_style_emits_J() -> None:
    cs, out = _make()
    cs.set_line_cap_style(1)
    assert out.getvalue() == b"1 J\n"


def test_set_line_cap_style_rejects_invalid() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_line_cap_style(5)


def test_set_line_dash_pattern_emits_d() -> None:
    cs, out = _make()
    cs.set_line_dash_pattern([3, 1], 0)
    assert out.getvalue() == b"[3 1 ] 0 d\n"


def test_set_line_dash_pattern_empty_solid() -> None:
    cs, out = _make()
    cs.set_line_dash_pattern([], 0)
    assert out.getvalue() == b"[] 0 d\n"


def test_set_miter_limit_emits_M() -> None:
    cs, out = _make()
    cs.set_miter_limit(10)
    assert out.getvalue() == b"10 M\n"


def test_set_miter_limit_rejects_zero() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_miter_limit(0)


def test_set_miter_limit_rejects_negative() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_miter_limit(-1.5)


# ------------------------------------------------------------------
# Marked-content operators
# ------------------------------------------------------------------


def test_begin_marked_content_no_props_emits_BMC() -> None:
    cs, out = _make()
    cs.begin_marked_content("Span")
    assert out.getvalue() == b"/Span BMC\n"


def test_begin_marked_content_accepts_cos_name() -> None:
    cs, out = _make()
    cs.begin_marked_content(COSName.get_pdf_name("P"))
    assert out.getvalue() == b"/P BMC\n"


def test_begin_marked_content_with_mcid_emits_BDC() -> None:
    cs, out = _make()
    cs.begin_marked_content("Span", 5)
    assert out.getvalue() == b"/Span <</MCID 5 >> BDC\n"


def test_begin_marked_content_with_property_list_emits_BDC() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    cs.begin_marked_content("Span", object())
    assert out.getvalue() == b"/Span /P1 BDC\n"


def test_begin_marked_content_with_property_list_no_resources() -> None:
    cs, out = _make()
    cs.begin_marked_content("Span", object())
    assert out.getvalue() == b"/Span BDC\n"


def test_end_marked_content_emits_EMC() -> None:
    cs, out = _make()
    cs.end_marked_content()
    assert out.getvalue() == b"EMC\n"


def test_set_marked_content_point_emits_MP() -> None:
    cs, out = _make()
    cs.set_marked_content_point("Span")
    assert out.getvalue() == b"/Span MP\n"


def test_set_marked_content_point_with_properties_emits_DP() -> None:
    resources = _FakeResources()
    cs, out = _make(resources)
    cs.set_marked_content_point_with_properties("Span", object())
    assert out.getvalue() == b"/Span /P1 DP\n"


def test_set_marked_content_point_with_properties_no_resources() -> None:
    cs, out = _make()
    cs.set_marked_content_point_with_properties("Span", object())
    assert out.getvalue() == b"/Span DP\n"


# ------------------------------------------------------------------
# Comments
# ------------------------------------------------------------------


def test_add_comment_emits_percent_line() -> None:
    cs, out = _make()
    cs.add_comment("hello world")
    assert out.getvalue() == b"% hello world\n"


def test_add_comment_rejects_newline() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.add_comment("two\nlines")


def test_add_comment_rejects_carriage_return() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.add_comment("two\rlines")


# ------------------------------------------------------------------
# Colour operators (G/g, RG/rg, K/k, SCN/scn)
# ------------------------------------------------------------------


def test_set_stroking_color_gray_emits_G() -> None:
    cs, out = _make()
    cs.set_stroking_color(0.5)
    assert out.getvalue() == b"0.5 G\n"


def test_set_non_stroking_color_gray_emits_g() -> None:
    cs, out = _make()
    cs.set_non_stroking_color(0.25)
    assert out.getvalue() == b"0.25 g\n"


def test_set_stroking_color_rgb_emits_RG() -> None:
    cs, out = _make()
    cs.set_stroking_color(1.0, 0.0, 0.5)
    assert out.getvalue() == b"1 0 0.5 RG\n"


def test_set_non_stroking_color_rgb_emits_rg() -> None:
    cs, out = _make()
    cs.set_non_stroking_color(0.1, 0.2, 0.3)
    assert out.getvalue() == b"0.1 0.2 0.3 rg\n"


def test_set_stroking_color_cmyk_emits_K() -> None:
    cs, out = _make()
    cs.set_stroking_color(0.1, 0.2, 0.3, 0.4)
    assert out.getvalue() == b"0.1 0.2 0.3 0.4 K\n"


def test_set_non_stroking_color_cmyk_emits_k() -> None:
    cs, out = _make()
    cs.set_non_stroking_color(0.0, 0.0, 0.0, 1.0)
    assert out.getvalue() == b"0 0 0 1 k\n"


def test_set_stroking_color_rgb_rejects_out_of_range() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_stroking_color(1.5, 0, 0)


def test_set_non_stroking_color_cmyk_rejects_out_of_range() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_non_stroking_color(-0.1, 0, 0, 0)


def test_set_stroking_color_gray_rejects_out_of_range() -> None:
    cs, _ = _make()
    with pytest.raises(ValueError):
        cs.set_stroking_color(2.0)


def test_set_color_wrong_arg_count_raises() -> None:
    cs, _ = _make()
    with pytest.raises(TypeError):
        cs.set_stroking_color(0.1, 0.2)
    with pytest.raises(TypeError):
        cs.set_non_stroking_color(0.1, 0.2, 0.3, 0.4, 0.5)


def test_set_color_unsupported_argument_type_raises() -> None:
    cs, _ = _make()
    with pytest.raises(TypeError):
        cs.set_stroking_color(object())


def test_set_color_with_pd_color_emits_scn() -> None:
    cs, out = _make()

    class FakeCS:
        def get_name(self) -> str:
            return "DeviceRGB"

    class FakeColor:
        def get_components(self) -> list[float]:
            return [0.1, 0.2, 0.3]

        def get_color_space(self) -> FakeCS:
            return FakeCS()

    cs.set_stroking_color(FakeColor())
    assert out.getvalue() == b"0.1 0.2 0.3 /DeviceRGB SCN\n"


def test_set_color_with_pd_color_no_cs_emits_scn_without_name() -> None:
    cs, out = _make()

    class FakeColor:
        def get_components(self) -> list[float]:
            return [0.5]

        def get_color_space(self) -> None:
            return None

    cs.set_non_stroking_color(FakeColor())
    assert out.getvalue() == b"0.5 scn\n"


# ------------------------------------------------------------------
# Range guards
# ------------------------------------------------------------------


def test_is_outside_255_interval() -> None:
    cs, _ = _make()
    assert cs.is_outside255_interval(-1) is True
    assert cs.is_outside255_interval(256) is True
    assert cs.is_outside255_interval(0) is False
    assert cs.is_outside255_interval(255) is False


def test_is_outside_one_interval() -> None:
    cs, _ = _make()
    assert cs.is_outside_one_interval(-0.01) is True
    assert cs.is_outside_one_interval(1.01) is True
    assert cs.is_outside_one_interval(0.0) is False
    assert cs.is_outside_one_interval(1.0) is False


# ------------------------------------------------------------------
# Colour-space stack management
# ------------------------------------------------------------------


def test_set_stroking_color_space_stack_initial_push() -> None:
    cs, _ = _make()
    cs.set_stroking_color_space_stack("rgb")
    assert list(cs._stroking_color_space_stack) == ["rgb"]


def test_set_stroking_color_space_stack_replaces_top() -> None:
    cs, _ = _make()
    cs.set_stroking_color_space_stack("rgb")
    cs.set_stroking_color_space_stack("gray")
    assert list(cs._stroking_color_space_stack) == ["gray"]


def test_set_non_stroking_color_space_stack_initial_push() -> None:
    cs, _ = _make()
    cs.set_non_stroking_color_space_stack("cmyk")
    assert list(cs._non_stroking_color_space_stack) == ["cmyk"]


def test_set_non_stroking_color_space_stack_replaces_top() -> None:
    cs, _ = _make()
    cs.set_non_stroking_color_space_stack("cmyk")
    cs.set_non_stroking_color_space_stack("rgb")
    assert list(cs._non_stroking_color_space_stack) == ["rgb"]


# ------------------------------------------------------------------
# GSUB helpers
# ------------------------------------------------------------------


def test_encode_for_gsub_no_worker_uses_font_encoder() -> None:
    cs, _ = _make()
    result = cs.encode_for_gsub(None, _FakeFont(), "hi")
    assert result == b"hi"


def test_encode_for_gsub_no_encoder_falls_back_to_latin1() -> None:
    cs, _ = _make()

    class FontNoEncode:
        pass

    result = cs.encode_for_gsub(None, FontNoEncode(), "abc")
    assert result == b"abc"


def test_encode_for_gsub_with_worker_applies_per_word() -> None:
    cs, _ = _make()

    class Worker:
        def __init__(self) -> None:
            self.words: list[str] = []

        def apply_transformations(self, word: str) -> list[int]:
            self.words.append(word)
            return []

    worker = Worker()
    font = _FakeFont()
    result = cs.encode_for_gsub(worker, font, "foo bar")
    assert worker.words == ["foo", "bar"]
    # No glyph IDs returned ⇒ falls back to per-word encoding, with a
    # space inserted between words.
    assert result == b"foo bar"


def test_apply_gsub_rules_no_worker_appends_encoded_word() -> None:
    cs, _ = _make()
    out = bytearray()
    result = cs.apply_gsub_rules(None, out, _FakeFont(), "abc")
    assert bytes(out) == b"abc"
    assert result == []


def test_apply_gsub_rules_no_encoder_returns_empty() -> None:
    cs, _ = _make()

    class FontNoEncode:
        pass

    out = bytearray()
    result = cs.apply_gsub_rules(object(), out, FontNoEncode(), "abc")
    assert result == []
    assert bytes(out) == b""


def test_apply_gsub_rules_with_glyph_ids_calls_encode_glyph_id() -> None:
    cs, _ = _make()

    class Worker:
        def apply_transformations(self, word: str) -> list[int]:
            return [10, 20]

    class FontWithGlyph(_FakeFont):
        def encode_glyph_id(self, gid: int) -> bytes:
            return bytes([gid])

    out = bytearray()
    result = cs.apply_gsub_rules(Worker(), out, FontWithGlyph(), "ab")
    assert result == [10, 20]
    assert bytes(out) == b"\x0a\x14"


def test_apply_gsub_rules_falls_back_when_encode_glyph_id_missing() -> None:
    cs, _ = _make()

    class Worker:
        def apply_transformations(self, word: str) -> list[int]:
            return [10]

    out = bytearray()
    cs.apply_gsub_rules(Worker(), out, _FakeFont(), "hi")
    # encode_glyph_id missing ⇒ falls back to encoder("hi")
    assert bytes(out) == b"hi"


def test_apply_gsub_rules_worker_without_apply_transformations() -> None:
    cs, _ = _make()
    out = bytearray()
    result = cs.apply_gsub_rules(object(), out, _FakeFont(), "abc")
    assert result == []
    # AttributeError is swallowed, no glyphs ⇒ falls through to encoder
    assert bytes(out) == b"abc"


# ------------------------------------------------------------------
# Property accessors + small odds and ends
# ------------------------------------------------------------------


def test_property_accessors_return_constructor_args() -> None:
    output = io.BytesIO()
    resources = _FakeResources()
    cs = _Concrete(None, output, resources)
    assert cs.document is None
    assert cs.output_stream is output
    assert cs.resources is resources


def test_fraction_digit_getters_and_setters() -> None:
    cs, _ = _make()
    assert cs.get_maximum_fraction_digits() == PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS
    cs.set_maximum_fraction_digits(2)
    assert cs.get_maximum_fraction_digits() == 2


def test_draw_image_handles_image_without_dimensions() -> None:
    """When ``draw_image`` is called with neither explicit width/height nor
    an image object that exposes ``get_width``/``get_height``, the base
    falls back to ``1.0`` for both."""
    cs, out = _make()
    cs.draw_image(object())
    assert out.getvalue() == b"q\n1 0 0 1 0 0 cm\nDo\nQ\n"


def test_get_name_no_resources_returns_raw_name() -> None:
    cs, _ = _make()

    class CS:
        def get_name(self) -> str:
            return "MyCustomCS"

    # No resources + non-device CS ⇒ returns the raw string name.
    assert cs.get_name(CS()) == "MyCustomCS"


def test_close_closes_underlying_stream() -> None:
    output = io.BytesIO()
    cs = _Concrete(None, output, None)
    cs.close()
    assert output.closed


def test_context_manager_enter_returns_self_and_exit_closes() -> None:
    output = io.BytesIO()
    cs = _Concrete(None, output, None)
    with cs as entered:
        assert entered is cs
    assert output.closed
