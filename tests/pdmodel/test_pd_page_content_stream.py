from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]
_RESOURCES: COSName = COSName.RESOURCES  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_X_OBJECT: COSName = COSName.get_pdf_name("XObject")


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


def _stream_bytes(page: PDPage) -> bytes:
    return page.get_contents()


# ------------------------------------------------------------------
# path drawing
# ------------------------------------------------------------------


def test_path_drawing_emits_expected_operators() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(10, 20)
        cs.line_to(30, 40)
        cs.stroke()
    body = _stream_bytes(page)
    assert body == b"10 20 m\n30 40 l\nS\n"


def test_curve_to_close_path_fill_and_stroke() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(0, 0)
        cs.curve_to(1, 2, 3, 4, 5, 6)
        cs.close_path()
        cs.fill_and_stroke()
    body = _stream_bytes(page)
    assert body == b"0 0 m\n1 2 3 4 5 6 c\nh\nB\n"


def test_add_rect_close_and_stroke_fill() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(10, 20, 30, 40)
        cs.close_and_stroke()
        cs.add_rect(0, 0, 5, 5)
        cs.fill()
    body = _stream_bytes(page)
    assert body == b"10 20 30 40 re\ns\n0 0 5 5 re\nf\n"


def test_floats_use_up_to_4_decimal_places_with_trim() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1.50000, 2.123456)
    body = _stream_bytes(page)
    # 1.5 trimmed; 2.123456 rounded to 4 dp -> 2.1235
    assert body == b"1.5 2.1235 m\n"


# ------------------------------------------------------------------
# color
# ------------------------------------------------------------------


def test_set_stroking_and_non_stroking_rgb() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_rgb(1, 0, 0)
        cs.set_non_stroking_color_rgb(0, 1, 0)
    body = _stream_bytes(page)
    assert body == b"1 0 0 RG\n0 1 0 rg\n"


def test_set_gray_and_cmyk() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_gray(0.5)
        cs.set_non_stroking_color_gray(0.25)
        cs.set_stroking_color_cmyk(0.1, 0.2, 0.3, 0.4)
        cs.set_non_stroking_color_cmyk(0.5, 0.6, 0.7, 0.8)
    body = _stream_bytes(page)
    assert body == (
        b"0.5 G\n0.25 g\n"
        b"0.1 0.2 0.3 0.4 K\n"
        b"0.5 0.6 0.7 0.8 k\n"
    )


# ------------------------------------------------------------------
# line width / cap / join / miter
# ------------------------------------------------------------------


def test_line_width_cap_join_miter() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_line_width(2.5)
        cs.set_line_cap_style(1)
        cs.set_line_join_style(2)
        cs.set_miter_limit(10)
    body = _stream_bytes(page)
    assert body == b"2.5 w\n1 J\n2 j\n10 M\n"


# ------------------------------------------------------------------
# text
# ------------------------------------------------------------------


def test_begin_text_set_font_show_text_end_text() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("Hi")
        cs.end_text()
    body = _stream_bytes(page)
    assert body == b"BT\n/F0 12 Tf\n(Hi) Tj\nET\n"
    # Font auto-registered on the page resources under "F0".
    res = page.get_resources()
    assert "F0" in [n.get_name() for n in res.get_font_names()]


def test_show_text_escapes_parens_and_backslash() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 10)
        cs.show_text("a(b)c\\d")
        cs.end_text()
    body = _stream_bytes(page)
    assert b"(a\\(b\\)c\\\\d) Tj" in body


def test_show_text_non_ascii_uses_hex_form() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 10)
        cs.show_text("中")  # CJK, not Latin-1
        cs.end_text()
    body = _stream_bytes(page)
    # UTF-16BE of U+4E2D = 4E2D
    assert b"<4E2D> Tj" in body


def test_text_state_setters() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_rise(2)
        cs.set_character_spacing(0.5)
        cs.set_word_spacing(1)
        cs.set_text_leading(14)
        cs.set_horizontal_scaling(95)
        cs.new_line_at_offset(10, 20)
        cs.new_line()
        cs.end_text()
    body = _stream_bytes(page)
    assert b"2 Ts\n" in body
    assert b"0.5 Tc\n" in body
    assert b"1 Tw\n" in body
    assert b"14 TL\n" in body
    assert b"95 Tz\n" in body
    assert b"10 20 Td\n" in body
    assert b"T*\n" in body


def test_set_font_reuses_existing_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.set_font(font, 10)
        cs.set_font(font, 12)  # second call should reuse F0, not allocate F1
    res = page.get_resources()
    assert [n.get_name() for n in res.get_font_names()] == ["F0"]


# ------------------------------------------------------------------
# graphics state
# ------------------------------------------------------------------


def test_save_restore_and_transform() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.save_graphics_state()
        cs.transform(1, 0, 0, 1, 50, 60)
        cs.restore_graphics_state()
    body = _stream_bytes(page)
    assert body == b"q\n1 0 0 1 50 60 cm\nQ\n"


# ------------------------------------------------------------------
# XObject
# ------------------------------------------------------------------


def _make_image() -> PDImageXObject:
    img = PDImageXObject(COSStream())
    img.set_width(100)
    img.set_height(50)
    return img


def test_draw_image_auto_assigns_im0() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, 10, 20)
    body = _stream_bytes(page)
    # Default w/h = intrinsic 100 x 50.
    assert body == b"q\n100 0 0 50 10 20 cm\n/Im0 Do\nQ\n"
    res = page.get_resources()
    assert [n.get_name() for n in res.get_xobject_names()] == ["Im0"]


def test_draw_image_assigns_im0_im1_for_two_images() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img1 = _make_image()
    img2 = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img1, 0, 0, 10, 10)
        cs.draw_image(img2, 20, 20, 5, 5)
    res = page.get_resources()
    assert sorted(n.get_name() for n in res.get_xobject_names()) == ["Im0", "Im1"]


def test_draw_image_reuses_existing_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, 0, 0, 10, 10)
        cs.draw_image(img, 50, 50, 10, 10)
    res = page.get_resources()
    assert [n.get_name() for n in res.get_xobject_names()] == ["Im0"]


def test_draw_form_emits_do_with_form_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    form = PDFormXObject(COSStream())
    with PDPageContentStream(doc, page) as cs:
        cs.draw_form(form, 5, 6)
    body = _stream_bytes(page)
    assert body == b"q\n1 0 0 1 5 6 cm\n/Form0 Do\nQ\n"


def test_draw_form_at_origin_skips_redundant_cm() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    form = PDFormXObject(COSStream())
    with PDPageContentStream(doc, page) as cs:
        cs.draw_form(form)
    body = _stream_bytes(page)
    assert body == b"q\n/Form0 Do\nQ\n"


# ------------------------------------------------------------------
# constructor / lifecycle
# ------------------------------------------------------------------


def test_context_manager_flushes_on_exit() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(0, 0)
    # On exit, the page's /Contents should be set with the buffered bytes.
    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSStream)
    assert contents.get_raw_data() == b"0 0 m\n"


def test_close_is_idempotent() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    cs.move_to(1, 2)
    cs.close()
    # Second close should not raise or duplicate writes.
    cs.close()
    assert _stream_bytes(page) == b"1 2 m\n"


def test_appending_to_existing_contents_promotes_to_array() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    # Stamp a pre-existing /Contents stream.
    initial = COSStream()
    initial.set_raw_data(b"q\nQ\n")
    page.set_contents(initial)

    with PDPageContentStream(doc, page) as cs:
        cs.move_to(0, 0)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 2
    assert contents.get(0) is initial
    second = contents.get(1)
    assert isinstance(second, COSStream)
    assert second.get_raw_data() == b"0 0 m\n"


def test_appending_to_existing_contents_array_extends_it() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    a = COSStream()
    a.set_raw_data(b"q\n")
    b = COSStream()
    b.set_raw_data(b"Q\n")
    arr = COSArray()
    arr.add(a)
    arr.add(b)
    page.get_cos_object().set_item(_CONTENTS, arr)

    with PDPageContentStream(doc, page) as cs:
        cs.move_to(0, 0)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 3


def test_form_xobject_target_writes_into_form_stream() -> None:
    doc = PDDocument()
    form = PDFormXObject(COSStream())
    with PDPageContentStream(doc, form) as cs:
        cs.move_to(0, 0)
        cs.line_to(1, 1)
        cs.stroke()
    assert form.get_cos_object().get_raw_data() == b"0 0 m\n1 1 l\nS\n"


def test_constructor_rejects_unsupported_target() -> None:
    doc = PDDocument()
    with pytest.raises(TypeError):
        PDPageContentStream(doc, "not a page")  # type: ignore[arg-type]


def test_constructor_rejects_none_target() -> None:
    doc = PDDocument()
    with pytest.raises(TypeError):
        PDPageContentStream(doc, None)
