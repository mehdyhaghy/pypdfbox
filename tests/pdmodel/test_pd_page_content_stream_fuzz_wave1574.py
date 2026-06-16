"""Fuzz / parity hardening for the content-stream *writer*
:class:`pypdfbox.pdmodel.pd_page_content_stream.PDPageContentStream`.

These cases hammer the exact operator bytes emitted by the writer and
compare them to what upstream ``org.apache.pdfbox.pdmodel.PDPageContentStream``
(via ``PDAbstractContentStream``) produces:

- ``BT``/``ET`` state machine — nested ``begin_text``, unmatched ``end_text``,
  text-only operators outside a block, path operators inside a block.
- ``show_text`` guards — upstream raises ``IllegalStateException`` both when
  not inside a text block ("Must call beginText() before showText()") and
  when no font has been selected ("Must call setFont() before showText()").
- numeric operand formatting — ``1.5`` → ``1.5``, ``2.0`` → ``2`` (no ``.0``),
  no scientific notation for tiny/huge magnitudes, float32 narrowing.
- ``set_(non_)stroking_color`` device-shorthand overloads selecting
  ``g``/``rg``/``k`` by component count.
- string escaping for ``(``/``)``/``\\`` and hex form for non-Latin-1.
- ``Td`` / ``Tm`` operand order.
- append vs overwrite vs prepend attachment.
- ``close()`` flush + idempotency.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_page_content_stream import (
    AppendMode,
    PDPageContentStream,
)

_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


def _make_font() -> PDType1Font:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return font


def _body(page: PDPage) -> bytes:
    return page.get_contents()


# ------------------------------------------------------------------
# BT / ET state machine
# ------------------------------------------------------------------


def test_nested_begin_text_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.begin_text()
        cs.end_text()


def test_end_text_without_begin_text_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(RuntimeError):
        cs.end_text()


def test_begin_text_leaves_text_mode_flag_set() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    assert cs.is_in_text_mode() is False
    cs.begin_text()
    assert cs.is_in_text_mode() is True
    cs.end_text()
    assert cs.is_in_text_mode() is False
    cs.close()


def test_path_op_inside_text_block_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.move_to(1, 2)
        with pytest.raises(RuntimeError):
            cs.add_rect(0, 0, 1, 1)
        with pytest.raises(RuntimeError):
            cs.save_graphics_state()
        cs.end_text()


def test_text_position_op_outside_text_block_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(RuntimeError):
            cs.new_line_at_offset(1, 2)
        with pytest.raises(RuntimeError):
            cs.new_line()
        with pytest.raises(RuntimeError):
            cs.set_text_matrix(1, 0, 0, 1, 0, 0)
        with pytest.raises(RuntimeError):
            cs.move_text_position_and_set_leading(1, 2)


# ------------------------------------------------------------------
# show_text guards (must call beginText + setFont)
# ------------------------------------------------------------------


def test_show_text_before_begin_text_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(RuntimeError):
        cs.show_text("hi")


def test_show_text_before_set_font_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.show_text("hi")
        # selecting a font unblocks show_text
        cs.set_font(_make_font(), 12)
        cs.show_text("hi")
        cs.end_text()
    assert b"(hi) Tj" in _body(page)


def test_show_text_with_positioning_before_font_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.show_text_with_positioning(["a", -10, "b"])
        cs.end_text()


def test_apostrophe_op_before_font_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.move_to_next_line_show_text("x")
        cs.end_text()


def test_quote_op_before_font_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.set_spacings_show_text(1, 2, "x")
        cs.end_text()


# ------------------------------------------------------------------
# numeric operand formatting (no .0, no sci-notation)
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (2.0, b"2"),
        (1.5, b"1.5"),
        (0.0, b"0"),
        (-3.0, b"-3"),
        (10.25, b"10.25"),
        (100, b"100"),
        (0.5, b"0.5"),
    ],
    ids=[
        "two_point_zero",
        "one_point_five",
        "zero",
        "neg_three",
        "ten_quarter",
        "int_100",
        "half",
    ],
)
def test_line_width_operand_formatting(value: float, expected: bytes) -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_line_width(value)
    assert _body(page) == expected + b" w\n"


def test_no_scientific_notation_for_tiny_value() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_line_width(0.0000001)  # 1e-7
    body = _body(page)
    assert b"E" not in body.upper().replace(b"RE", b"")  # no exponent marker
    # float32 half-up at 5 digits truncates 1e-7 to 0.
    assert body == b"0 w\n"


def test_no_scientific_notation_for_large_value() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1234567.0, 0)
        cs.line_to(0, 0)
        cs.stroke()
    body = _body(page)
    assert b"E+" not in body
    assert b"1234567 0 m" in body


def test_coordinate_operand_order_td() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.new_line_at_offset(5, 10)
        cs.end_text()
    assert b"5 10 Td\n" in _body(page)


def test_set_text_matrix_six_operand_order() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix(1, 2, 3, 4, 5, 6)
        cs.end_text()
    assert b"1 2 3 4 5 6 Tm\n" in _body(page)


def test_set_text_matrix_accepts_six_element_iterable() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix([1.0, 0.0, 0.0, 1.0, 72.0, 144.0])
        cs.end_text()
    assert b"1 0 0 1 72 144 Tm\n" in _body(page)


# ------------------------------------------------------------------
# color overloads: g / rg / k by component count
# ------------------------------------------------------------------


def test_set_non_stroking_color_gray_emits_g() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.5)
    assert _body(page) == b"0.5 g\n"


def test_set_non_stroking_color_rgb_emits_rg() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.0, 0.5, 1.0)
    assert _body(page) == b"0 0.5 1 rg\n"


def test_set_non_stroking_color_cmyk_emits_k() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.1, 0.2, 0.3, 0.4)
    assert _body(page) == b"0.1 0.2 0.3 0.4 k\n"


def test_set_stroking_color_uppercase_ops() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(0.25)
        cs.set_stroking_color(1.0, 0.0, 0.0)
        cs.set_stroking_color(0.0, 0.0, 0.0, 1.0)
    assert _body(page) == b"0.25 G\n1 0 0 RG\n0 0 0 1 K\n"


def test_color_component_out_of_range_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        with pytest.raises(ValueError):
            cs.set_non_stroking_color(1.5)
        with pytest.raises(ValueError):
            cs.set_stroking_color(-0.1, 0.0, 0.0)


def test_color_arg_count_rejected() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.set_non_stroking_color(0.1, 0.2)


# ------------------------------------------------------------------
# string escaping
# ------------------------------------------------------------------


def test_show_text_escapes_parens_and_backslash_exact() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 10)
        cs.show_text("a(b)c\\d")
        cs.end_text()
    assert b"(a\\(b\\)c\\\\d) Tj\n" in _body(page)


def test_show_text_non_latin1_uses_hex_form() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 10)
        cs.show_text("中")  # CJK, not Latin-1 -> UTF-16BE hex
        cs.end_text()
    assert b"<4E2D> Tj\n" in _body(page)


def test_show_text_latin1_high_byte_stays_literal() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 10)
        # é is U+00E9, encodable as Latin-1 (0xE9) which is not ASCII-safe
        # -> hex form per the lite encoder.
        cs.show_text("é")
        cs.end_text()
    assert b"<E9> Tj\n" in _body(page)


# ------------------------------------------------------------------
# set_font key allocation
# ------------------------------------------------------------------


def test_set_font_emits_tf_and_registers_resource() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 14)
        cs.end_text()
    assert b"/F1 14 Tf\n" in _body(page)
    names = [n.get_name() for n in page.get_resources().get_font_names()]
    assert "F1" in names


def test_set_font_reuses_key_for_same_font() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = _make_font()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 10)
        cs.set_font(font, 12)
        cs.end_text()
    body = _body(page)
    assert b"/F1 10 Tf\n" in body
    assert b"/F1 12 Tf\n" in body
    assert b"/F2" not in body


def test_set_font_rejects_non_font() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.set_font("not a font", 12)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# graphics ops byte parity
# ------------------------------------------------------------------


def test_path_construction_and_painting_bytes() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(0, 0)
        cs.line_to(100, 0)
        cs.curve_to(1, 2, 3, 4, 5, 6)
        cs.close_path()
        cs.fill_and_stroke()
    assert _body(page) == (
        b"0 0 m\n100 0 l\n1 2 3 4 5 6 c\nh\nB\n"
    )


def test_line_cap_join_and_dash_bytes() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_line_cap_style(1)
        cs.set_line_join_style(2)
        cs.set_dash_pattern([3, 2], 0)
    assert _body(page) == b"1 J\n2 j\n[3 2 ] 0 d\n"


def test_line_cap_out_of_range_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(ValueError):
        cs.set_line_cap_style(5)


def test_transform_cm_six_operands() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.transform(2, 0, 0, 2, 10, 20)
    assert _body(page) == b"2 0 0 2 10 20 cm\n"


# ------------------------------------------------------------------
# append / overwrite / prepend attachment
# ------------------------------------------------------------------


def test_overwrite_replaces_existing_contents() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1, 1)
        cs.line_to(2, 2)
        cs.stroke()
    with PDPageContentStream(doc, page, AppendMode.OVERWRITE) as cs:
        cs.move_to(9, 9)
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert not isinstance(contents, COSArray)
    assert _body(page) == b"9 9 m\n"


def test_append_keeps_existing_and_adds_last() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1, 1)
    with PDPageContentStream(doc, page, AppendMode.APPEND) as cs:
        cs.move_to(2, 2)
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 2
    assert b"1 1 m" in _body(page)
    assert b"2 2 m" in _body(page)


def test_prepend_puts_new_first() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1, 1)
    with PDPageContentStream(doc, page, AppendMode.PREPEND) as cs:
        cs.move_to(2, 2)
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    first = contents.get(0)
    assert first.get_raw_data() == b"2 2 m\n"


def test_append_mode_string_coercion() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1, 1)
    with PDPageContentStream(doc, page, "append") as cs:
        cs.move_to(2, 2)
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)


def test_unknown_append_mode_string_raises() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with pytest.raises(ValueError):
        PDPageContentStream(doc, page, "sideways")


# ------------------------------------------------------------------
# close() flush + idempotency
# ------------------------------------------------------------------


def test_close_flushes_buffer_into_stream() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    cs.move_to(7, 8)
    # Nothing committed before close.
    assert cs.get_target_stream().get_raw_data() == b""
    cs.close()
    assert cs.get_target_stream().get_raw_data() == b"7 8 m\n"


def test_close_is_idempotent() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    cs.move_to(7, 8)
    cs.close()
    cs.close()  # no error, no double-write
    assert _body(page) == b"7 8 m\n"


def test_construction_requires_page_or_form() -> None:
    doc = PDDocument()
    with pytest.raises(TypeError):
        PDPageContentStream(doc, None)
    with pytest.raises(TypeError):
        PDPageContentStream(doc, "not a page")  # type: ignore[arg-type]


# ------------------------------------------------------------------
# show_text_with_positioning full byte parity
# ------------------------------------------------------------------


def test_show_text_with_positioning_byte_parity() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(["AB", -120.0, "C"])
        cs.end_text()
    assert b"[(AB)-120 (C)] TJ\n" in _body(page)


def test_show_text_with_positioning_rejects_bool() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        with pytest.raises(TypeError):
            cs.show_text_with_positioning(["A", True])
        cs.end_text()
