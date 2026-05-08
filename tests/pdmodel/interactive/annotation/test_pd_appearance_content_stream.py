from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_resources import PDResources


def _new_appearance() -> PDAppearanceStream:
    return PDAppearanceStream(COSStream())


def _decoded_body(appearance: PDAppearanceStream) -> bytes:
    return appearance.get_stream().to_byte_array()


# ---------- construction ----------


def test_constructor_rejects_non_appearance() -> None:
    with pytest.raises(TypeError):
        PDAppearanceContentStream(object())  # type: ignore[arg-type]


def test_constructor_attaches_default_resources_when_absent() -> None:
    appearance = _new_appearance()
    assert appearance.get_resources() is None
    cs = PDAppearanceContentStream(appearance)
    cs.close()
    assert appearance.get_resources() is not None
    # The writer's resources match the appearance's resources after init.
    assert cs.get_resources() is not None


def test_constructor_reuses_existing_resources() -> None:
    appearance = _new_appearance()
    res = PDResources()
    appearance.set_resources(res)
    cs = PDAppearanceContentStream(appearance)
    assert cs.get_resources().get_cos_object() is res.get_cos_object()
    cs.close()


def test_get_appearance_returns_target() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    assert cs.get_appearance() is appearance
    cs.close()


# ---------- writing operators ----------


def test_simple_path_emits_expected_operators() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.move_to(10, 20)
        cs.line_to(100, 200)
        cs.stroke()
    body = _decoded_body(appearance)
    assert b"10 20 m" in body
    assert b"100 200 l" in body
    assert b"S\n" in body


def test_compress_flag_routes_through_flate() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance, compress=True) as cs:
        cs.move_to(0, 0)
        cs.line_to(50, 50)
        cs.stroke()
    # With compression on, /Filter is set to FlateDecode and the
    # decoded bytes still surface the operators.
    cos = appearance.get_stream()
    filt = cos.get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
    assert filt == COSName.FLATE_DECODE  # type: ignore[attr-defined]
    decoded = cos.to_byte_array()
    assert b"0 0 m" in decoded
    assert b"S\n" in decoded


def test_explicit_output_stream_used_for_writes() -> None:
    appearance = _new_appearance()
    out = appearance.get_stream().create_output_stream()
    with PDAppearanceContentStream(appearance, output_stream=out) as cs:
        cs.move_to(1, 2)
        cs.line_to(3, 4)
    body = _decoded_body(appearance)
    assert b"1 2 m" in body
    assert b"3 4 l" in body


# ---------- color helpers ----------


def test_set_stroking_color_rgb_components() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_stroking_color([0.1, 0.2, 0.3])
    body = _decoded_body(appearance)
    assert b"0.1 0.2 0.3 RG" in body


def test_set_stroking_color_gray_and_cmyk() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_stroking_color([0.5])
        cs.set_stroking_color([0.1, 0.2, 0.3, 0.4])
    body = _decoded_body(appearance)
    assert b"0.5 G" in body
    assert b"0.1 0.2 0.3 0.4 K" in body


def test_set_non_stroking_color_emits_lowercase_operators() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_non_stroking_color([0.7])
        cs.set_non_stroking_color([0.1, 0.2, 0.3])
        cs.set_non_stroking_color([0.1, 0.2, 0.3, 0.4])
    body = _decoded_body(appearance)
    assert b"0.7 g" in body
    assert b"0.1 0.2 0.3 rg" in body
    assert b"0.1 0.2 0.3 0.4 k" in body


def test_set_color_two_components_is_silent_no_op() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_stroking_color([0.5, 0.5])  # 2 components — upstream skips
    body = _decoded_body(appearance)
    # Operands were written but no operator follows
    assert b" RG" not in body
    assert b" G\n" not in body
    assert b" K" not in body


def test_set_stroking_color_on_demand_with_color() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    color = PDColor([0.25, 0.5, 0.75], PDDeviceRGB.INSTANCE)
    assert cs.set_stroking_color_on_demand(color) is True
    cs.close()
    body = _decoded_body(appearance)
    assert b"0.25 0.5 0.75 RG" in body


def test_set_stroking_color_on_demand_with_none_returns_false() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    assert cs.set_stroking_color_on_demand(None) is False
    cs.close()
    assert _decoded_body(appearance) == b""


def test_set_stroking_color_on_demand_with_empty_components() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    color = PDColor([], PDPattern())
    assert cs.set_stroking_color_on_demand(color) is False
    cs.close()


def test_set_non_stroking_color_on_demand() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    color = PDColor([0.5], PDDeviceGray.INSTANCE)
    assert cs.set_non_stroking_color_on_demand(color) is True
    assert cs.set_non_stroking_color_on_demand(None) is False
    cs.close()
    body = _decoded_body(appearance)
    assert b"0.5 g" in body


# ---------- line width / border ----------


def test_set_line_width_on_demand_skips_default_width() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_line_width_on_demand(1.0)  # should NOT emit
        cs.set_line_width_on_demand(2.5)  # should emit
    body = _decoded_body(appearance)
    # Only the 2.5 path should appear.
    assert b"1 w" not in body
    assert b"2.5 w" in body


def test_set_line_width_on_demand_skips_within_epsilon() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_line_width_on_demand(1.0 + 1e-7)
    body = _decoded_body(appearance)
    assert b"w\n" not in body


def test_set_border_line_with_dashed_bs() -> None:
    appearance = _new_appearance()
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    bs.get_cos_object().set_item(
        COSName.get_pdf_name("D"),
        COSArray([COSFloat(3.0), COSFloat(2.0)]),
    )
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_border_line(2.0, bs, None)
    body = _decoded_body(appearance)
    assert b"[3 2] 0 d" in body
    assert b"2 w" in body


def test_set_border_line_with_dashed_bs_without_dash_array_uses_default() -> None:
    appearance = _new_appearance()
    bs = PDBorderStyleDictionary()
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)

    with PDAppearanceContentStream(appearance) as cs:
        cs.set_border_line(2.0, bs, None)

    body = _decoded_body(appearance)
    assert b"[3] 0 d" in body
    assert b"2 w" in body
    stored = bs.get_cos_object().get_dictionary_object(COSName.get_pdf_name("D"))
    assert isinstance(stored, COSArray)
    assert stored.to_float_array() == [3.0]


def test_set_border_line_solid_bs_skips_dash() -> None:
    appearance = _new_appearance()
    bs = PDBorderStyleDictionary()
    # Default style is "S" (solid). No /D entry.
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_border_line(3.0, bs, None)
    body = _decoded_body(appearance)
    assert b" d\n" not in body
    assert b"3 w" in body


def test_set_border_line_from_border_array() -> None:
    appearance = _new_appearance()
    border = COSArray(
        [
            COSFloat(0),
            COSFloat(0),
            COSFloat(1),
            COSArray([COSFloat(4.0), COSFloat(2.0)]),
        ]
    )
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_border_line(0.5, None, border)
    body = _decoded_body(appearance)
    assert b"[4 2] 0 d" in body
    assert b"0.5 w" in body


def test_set_border_line_invalid_border_dash_falls_back_invisible() -> None:
    # PDFBOX-5266: malformed border[3] must produce an invisible-dash array.
    appearance = _new_appearance()
    border = COSArray(
        [COSFloat(0), COSFloat(0), COSFloat(1), COSFloat(99.0)]
    )
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_border_line(2.0, None, border)
    body = _decoded_body(appearance)
    assert b"[0] 0 d" in body
    assert b"2 w" in body


# ---------- draw_shape ----------


def test_draw_shape_fill_and_stroke() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.add_rect(0, 0, 10, 10)
        cs.draw_shape(2.0, has_stroke=True, has_fill=True)
    body = _decoded_body(appearance)
    assert b"B\n" in body


def test_draw_shape_stroke_only() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.draw_shape(2.0, has_stroke=True, has_fill=False)
    body = _decoded_body(appearance)
    assert b"S\n" in body


def test_draw_shape_fill_only() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.draw_shape(2.0, has_stroke=False, has_fill=True)
    body = _decoded_body(appearance)
    assert b"f\n" in body


def test_draw_shape_neither_emits_endpath() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.draw_shape(2.0, has_stroke=False, has_fill=False)
    body = _decoded_body(appearance)
    assert b"n\n" in body


def test_draw_shape_thin_line_suppresses_stroke() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        # line width below 1e-6 should skip the stroke even when has_stroke
        cs.draw_shape(1e-9, has_stroke=True, has_fill=True)
    body = _decoded_body(appearance)
    # fill+stroke would be B; with stroke suppressed and fill on, get f.
    assert b"f\n" in body
    assert b"B\n" not in body


# ---------- text ----------


def test_text_block_in_appearance() -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.begin_text()
        cs.new_line_at_offset(5, 10)
        cs.show_text("Hi")
        cs.end_text()
    body = _decoded_body(appearance)
    assert b"BT\n" in body
    assert b"5 10 Td" in body
    assert b"(Hi) Tj" in body


# ---------- accessors ----------


def test_get_resources_returns_attached_resources() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    try:
        # Returns the /Resources the writer attached on construction —
        # comparing the underlying COS dict so wrapper identity is irrelevant.
        resources = cs.get_resources()
        assert isinstance(resources, PDResources)
        attached = appearance.get_resources()
        assert attached is not None
        assert resources.get_cos_object() is attached.get_cos_object()
    finally:
        cs.close()


def test_get_resources_reuses_existing_appearance_resources() -> None:
    appearance = _new_appearance()
    pre = PDResources()
    appearance.set_resources(pre)
    cs = PDAppearanceContentStream(appearance)
    try:
        # The writer must NOT replace pre-existing /Resources — the
        # underlying COS dict must be the same one the caller passed in.
        assert cs.get_resources().get_cos_object() is pre.get_cos_object()
    finally:
        cs.close()


def test_is_compress_default_false() -> None:
    cs = PDAppearanceContentStream(_new_appearance())
    try:
        assert cs.is_compress() is False
    finally:
        cs.close()


def test_is_compress_true_when_requested() -> None:
    cs = PDAppearanceContentStream(_new_appearance(), compress=True)
    try:
        assert cs.is_compress() is True
    finally:
        cs.close()


def test_is_compress_false_when_external_output_supplied() -> None:
    """External output overrides ``compress=True`` — the caller owns the
    filter chain in that case (matches the docstring guarantee)."""
    appearance = _new_appearance()
    output = appearance.get_stream().create_output_stream()
    cs = PDAppearanceContentStream(appearance, compress=True, output_stream=output)
    try:
        assert cs.is_compress() is False
    finally:
        cs.close()
