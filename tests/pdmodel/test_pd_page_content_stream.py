from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import (
    AppendMode,
    PDPageContentStream,
)

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


def _make_font() -> PDType1Font:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return font


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


def test_floats_use_up_to_5_decimal_places_with_trim() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1.50000, 2.123456)
    body = _stream_bytes(page)
    # 1.5 trimmed; 2.123456 rounded to 5 dp (HALF_EVEN) -> 2.12346
    # (matches PDFBox formatDecimal.setMaximumFractionDigits(5)).
    assert body == b"1.5 2.12346 m\n"


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
    assert body == b"BT\n/F1 12 Tf\n(Hi) Tj\nET\n"
    # Font auto-registered on the page resources under "F1".
    res = page.get_resources()
    assert "F1" in [n.get_name() for n in res.get_font_names()]


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
        cs.set_font(font, 12)  # second call should reuse F1, not allocate F2
    res = page.get_resources()
    assert [n.get_name() for n in res.get_font_names()] == ["F1"]


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
    assert body == b"q\n100 0 0 50 10 20 cm\n/Im1 Do\nQ\n"
    res = page.get_resources()
    assert [n.get_name() for n in res.get_xobject_names()] == ["Im1"]


def test_draw_image_assigns_im0_im1_for_two_images() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img1 = _make_image()
    img2 = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img1, 0, 0, 10, 10)
        cs.draw_image(img2, 20, 20, 5, 5)
    res = page.get_resources()
    assert sorted(n.get_name() for n in res.get_xobject_names()) == ["Im1", "Im2"]


def test_draw_image_reuses_existing_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, 0, 0, 10, 10)
        cs.draw_image(img, 50, 50, 10, 10)
    res = page.get_resources()
    assert [n.get_name() for n in res.get_xobject_names()] == ["Im1"]


def test_draw_image_native_size_two_arg_position() -> None:
    """``draw_image(image, x, y)`` overload: width/height default to the
    image's intrinsic ``/Width`` × ``/Height`` (1 pt per pixel)."""
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()  # 100 x 50
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, 7, 8)
    body = _stream_bytes(page)
    assert body == b"q\n100 0 0 50 7 8 cm\n/Im1 Do\nQ\n"


def test_draw_image_with_explicit_scaled_dimensions() -> None:
    """``draw_image(image, x, y, width, height)`` overload — scaled CTM."""
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, 1.5, 2.5, 200, 100)
    body = _stream_bytes(page)
    # CTM order matches ``a b c d e f cm`` (= width 0 0 height x y).
    assert body == b"q\n200 0 0 100 1.5 2.5 cm\n/Im1 Do\nQ\n"


def test_draw_image_full_custom_ctm_tuple() -> None:
    """``draw_image(image, transform_matrix)`` overload — passes the full
    affine ``(a, b, c, d, e, f)`` straight through to ``cm``."""
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    matrix = (50, 0, 0, 25, 100, 200)  # 50x25 anchored at (100,200)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, matrix)
    body = _stream_bytes(page)
    # CTM bytes preserve the input matrix verbatim, wrapped in q/Q.
    assert body == b"q\n50 0 0 25 100 200 cm\n/Im1 Do\nQ\n"


def test_draw_image_full_custom_ctm_list_with_rotation() -> None:
    """List form is accepted and rotation/skew components round-trip."""
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    # 90° rotation + 100x100 scale anchored at (50,60):
    # (a,b,c,d,e,f) = (0, 100, -100, 0, 50, 60)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(img, [0, 100, -100, 0, 50, 60])
    body = _stream_bytes(page)
    assert body == b"q\n0 100 -100 0 50 60 cm\n/Im1 Do\nQ\n"


def test_draw_image_matrix_overload_rejects_wrong_arity() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs, pytest.raises(ValueError):
        cs.draw_image(img, (1, 0, 0, 1, 0))  # only 5 components


def test_draw_image_inside_text_block_raises() -> None:
    """Mirrors upstream's ``IllegalStateException`` when drawing between
    BT and ET — translated to :class:`RuntimeError`."""
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        with pytest.raises(RuntimeError):
            cs.draw_image(img, 0, 0)
        cs.end_text()


def test_draw_image_requires_x_or_matrix() -> None:
    """Calling ``draw_image(image)`` with no positional info is rejected."""
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_image()
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.draw_image(img)  # type: ignore[call-arg]


def test_draw_image_path_without_factories_raises_not_implemented(
    tmp_path,
) -> None:
    """When neither JPEGFactory nor LosslessFactory ship, passing a
    non-PDImageXObject (here, a path) must raise NotImplementedError
    with the documented guidance string."""
    import sys
    import types

    # Stub out both factory modules with empty namespaces so the
    # lazy-import lands on a module that has no factory symbol.
    saved = {
        name: sys.modules.get(name)
        for name in (
            "pypdfbox.pdmodel.graphics.image.jpeg_factory",
            "pypdfbox.pdmodel.graphics.image.lossless_factory",
        )
    }
    dummy_jpeg = types.ModuleType(
        "pypdfbox.pdmodel.graphics.image.jpeg_factory"
    )
    dummy_lossless = types.ModuleType(
        "pypdfbox.pdmodel.graphics.image.lossless_factory"
    )
    # Module exists but the JPEGFactory / LosslessFactory attributes are
    # absent — matches the "modules import but factories not yet wired"
    # state the lazy-import path is designed to handle.
    sys.modules["pypdfbox.pdmodel.graphics.image.jpeg_factory"] = dummy_jpeg
    sys.modules["pypdfbox.pdmodel.graphics.image.lossless_factory"] = dummy_lossless
    try:
        src = tmp_path / "pretend.png"
        src.write_bytes(b"\x89PNG\r\n\x1a\n")
        doc = PDDocument()
        page = _make_page(doc)
        with PDPageContentStream(doc, page) as cs:
            with pytest.raises(NotImplementedError) as excinfo:
                cs.draw_image(src, 0, 0)
            assert "JPEGFactory" in str(excinfo.value)
    finally:
        # Restore whatever was there originally.
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def test_draw_image_with_path_uses_lossless_factory(tmp_path) -> None:
    """End-to-end: passing a PNG path to ``draw_image`` lazy-imports the
    factories, builds a PDImageXObject under the hood, and emits the
    expected ``q ... cm /Im1 Do Q`` byte sequence."""
    from PIL import Image as _PILImage

    src = tmp_path / "tile.png"
    _PILImage.new("RGB", (10, 4), (200, 0, 100)).save(src, format="PNG")

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(src, 5, 5, 100, 50)
    body = _stream_bytes(page)
    # Width 100, height 50, anchor (5,5) — single XObject auto-named Im1.
    assert body == b"q\n100 0 0 50 5 5 cm\n/Im1 Do\nQ\n"
    res = page.get_resources()
    names = [n.get_name() for n in res.get_xobject_names()]
    assert names == ["Im1"]


def test_draw_image_with_jpeg_bytes_uses_jpeg_factory(tmp_path) -> None:
    """Sniffing the JPEG SOI marker routes raw bytes through the
    JPEG factory (verbatim ``/DCTDecode`` embed)."""
    from PIL import Image as _PILImage

    buf = tmp_path / "tile.jpg"
    _PILImage.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="JPEG")
    raw = buf.read_bytes()

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(raw, 0, 0)  # native size (8x8)
    body = _stream_bytes(page)
    assert body == b"q\n8 0 0 8 0 0 cm\n/Im1 Do\nQ\n"
    img = page.get_resources().get_x_object(
        COSName.get_pdf_name("Im1")
    )
    filters = [n.get_name() for n in img.get_cos_object().get_filter_list()]
    assert filters == ["DCTDecode"]


def test_draw_form_emits_do_with_form_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    form = PDFormXObject(COSStream())
    with PDPageContentStream(doc, page) as cs:
        cs.draw_form(form, 5, 6)
    body = _stream_bytes(page)
    assert body == b"q\n1 0 0 1 5 6 cm\n/Form1 Do\nQ\n"


def test_draw_form_at_origin_emits_bare_do() -> None:
    # Upstream parity: drawForm(PDFormXObject) emits a bare ``/<key> Do`` with
    # no surrounding q/cm/Q (the caller owns the graphics state). pypdfbox's
    # x/y placement params are a convenience extension that DOES wrap.
    doc = PDDocument()
    page = _make_page(doc)
    form = PDFormXObject(COSStream())
    with PDPageContentStream(doc, page) as cs:
        cs.draw_form(form)
    body = _stream_bytes(page)
    assert body == b"/Form1 Do\n"


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

    with PDPageContentStream(doc, page, AppendMode.APPEND) as cs:
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

    with PDPageContentStream(doc, page, AppendMode.APPEND) as cs:
        cs.move_to(0, 0)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 3
    assert page.get_contents() == b"q\n\nQ\n\n0 0 m\n"


def test_default_append_mode_overwrites_existing_contents() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    initial = COSStream()
    initial.set_raw_data(b"old\n")
    page.set_contents(initial)

    with PDPageContentStream(doc, page) as cs:
        cs.move_to(1, 2)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSStream)
    assert contents is not initial
    assert page.get_contents() == b"1 2 m\n"


def test_prepending_to_existing_contents_preserves_order() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    initial = COSStream()
    initial.set_raw_data(b"old\n")
    page.set_contents(initial)

    with PDPageContentStream(doc, page, AppendMode.PREPEND) as cs:
        cs.move_to(3, 4)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 2
    first = contents.get(0)
    assert isinstance(first, COSStream)
    assert first.get_raw_data() == b"3 4 m\n"
    assert contents.get(1) is initial
    assert page.get_contents() == b"3 4 m\n\nold\n"


def test_append_reset_context_wraps_existing_graphics_state() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    initial = COSStream()
    initial.set_raw_data(b"2 0 0 2 0 0 cm\n")
    page.set_contents(initial)

    with PDPageContentStream(
        doc,
        page,
        AppendMode.APPEND,
        reset_context=True,
    ) as cs:
        cs.move_to(1, 2)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 3
    prefix = contents.get(0)
    appended = contents.get(2)
    assert isinstance(prefix, COSStream)
    assert isinstance(appended, COSStream)
    assert prefix.get_raw_data() == b"q\n"
    assert contents.get(1) is initial
    assert appended.get_raw_data() == b"Q\n1 2 m\n"
    assert page.get_contents() == b"q\n\n2 0 0 2 0 0 cm\n\nQ\n1 2 m\n"


def test_append_reset_context_is_ignored_without_existing_contents() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(
        doc,
        page,
        AppendMode.APPEND,
        reset_context=True,
    ) as cs:
        cs.move_to(1, 2)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSStream)
    assert contents.get_raw_data() == b"1 2 m\n"
    assert page.get_contents() == b"1 2 m\n"


def test_compression_flag_writes_flate_filtered_stream() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page, compress=True)
    cs.move_to(5, 6)
    target = cs.get_target_stream()
    cs.close()

    assert target.get_filter_list() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]
    assert target.get_raw_data() != b"5 6 m\n"
    assert target.to_byte_array() == b"5 6 m\n"
    assert page.get_contents() == b"5 6 m\n"


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


# ------------------------------------------------------------------
# show_text bytes overload
# ------------------------------------------------------------------


def test_show_text_accepts_bytes_ascii_safe() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text(b"hi")
        cs.end_text()
    assert _stream_bytes(page) == b"BT\n/F1 12 Tf\n(hi) Tj\nET\n"


def test_show_text_bytes_with_high_bytes_uses_hex_form() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text(b"\x00H\x00i")
        cs.end_text()
    assert _stream_bytes(page) == b"BT\n/F1 12 Tf\n<00480069> Tj\nET\n"


def test_show_text_bytes_escapes_special_characters() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text(b"a(b)c\\d")
        cs.end_text()
    assert b"(a\\(b\\)c\\\\d) Tj\n" in _stream_bytes(page)


# ------------------------------------------------------------------
# marked content (BMC / BDC / EMC / MP / DP)
# ------------------------------------------------------------------


def test_begin_marked_content_emits_bmc() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content("P")
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text("hi")
        cs.end_text()
        cs.end_marked_content()
    assert (
        _stream_bytes(page)
        == b"/P BMC\nBT\n/F1 12 Tf\n(hi) Tj\nET\nEMC\n"
    )


def test_marked_content_accepts_cos_name() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content(COSName.get_pdf_name("Span"))
        cs.end_marked_content()
    assert _stream_bytes(page) == b"/Span BMC\nEMC\n"


def test_begin_marked_content_with_dict_string_property_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content_with_dict("P", "MC0")
        cs.end_marked_content()
    assert _stream_bytes(page) == b"/P /MC0 BDC\nEMC\n"


def test_begin_marked_content_with_property_list_registers_resource() -> None:
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )

    doc = PDDocument()
    page = _make_page(doc)
    ocg = PDOptionalContentGroup("Layer1")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content_with_dict("OC", ocg)
        cs.end_marked_content()

    body = _stream_bytes(page)
    assert b"/OC /Prop1 BDC" in body
    res = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Properties")
    )
    assert res is not None
    assert res.get_dictionary_object(COSName.get_pdf_name("Prop1")) is ocg.get_cos_object()


def test_marked_content_point_emits_mp_and_dp() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_marked_content_point("Artifact")
        cs.add_marked_content_point_with_dict("Span", "MC9")
    assert _stream_bytes(page) == b"/Artifact MP\n/Span /MC9 DP\n"


def test_marked_content_property_list_reuses_existing_key() -> None:
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
        PDOptionalContentGroup,
    )

    doc = PDDocument()
    page = _make_page(doc)
    ocg = PDOptionalContentGroup("Layer1")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content_with_dict("OC", ocg)
        cs.end_marked_content()
        cs.begin_marked_content_with_dict("OC", ocg)
        cs.end_marked_content()

    body = _stream_bytes(page)
    # Both entries reuse MC0 — only one Properties slot allocated.
    assert body.count(b"/OC /Prop1 BDC") == 2
    res = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Properties")
    )
    assert len(list(res.key_set())) == 1


# ------------------------------------------------------------------
# text positioning operators (Td / TD / T* / ' / " / TJ)
# ------------------------------------------------------------------


def test_move_text_position_by_amount_emits_td() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.move_text_position_by_amount(15, 25)
        cs.end_text()
    assert _stream_bytes(page) == b"BT\n15 25 Td\nET\n"


def test_move_text_position_and_set_leading_emits_td_uppercase() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.move_text_position_and_set_leading(10, -14)
        cs.end_text()
    assert _stream_bytes(page) == b"BT\n10 -14 TD\nET\n"


def test_move_to_next_line_emits_t_star() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.move_to_next_line()
        cs.end_text()
    assert _stream_bytes(page) == b"BT\nT*\nET\n"


def test_move_to_next_line_show_text_emits_apostrophe() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.move_to_next_line_show_text("Hi")
        cs.end_text()
    body = _stream_bytes(page)
    assert b"(Hi) '\n" in body


def test_move_to_next_line_show_text_escapes_specials() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.move_to_next_line_show_text("a(b)c\\d")
        cs.end_text()
    assert b"(a\\(b\\)c\\\\d) '\n" in _stream_bytes(page)


def test_move_to_next_line_show_text_non_ascii_uses_hex() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.move_to_next_line_show_text("中")
        cs.end_text()
    assert b"<4E2D> '\n" in _stream_bytes(page)


def test_set_spacings_show_text_emits_double_quote() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.set_spacings_show_text(2, 0.5, "Hi")
        cs.end_text()
    body = _stream_bytes(page)
    assert b'2 0.5 (Hi) "\n' in body


def test_set_spacings_show_text_with_bytes_payload() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.set_spacings_show_text(1, 2, b"ok")
        cs.end_text()
    assert b'1 2 (ok) "\n' in _stream_bytes(page)


def test_show_text_with_positioning_string_only() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(["Hello"])
        cs.end_text()
    assert b"[(Hello)] TJ\n" in _stream_bytes(page)


def test_show_text_with_positioning_mixed_strings_and_offsets() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(["Hel", -120, "lo", 250.5, "!"])
        cs.end_text()
    # Numeric items emit number + space; strings emit a parenthesized
    # literal directly. Outer bracket pair plus trailing " TJ".
    assert b"[(Hel)-120 (lo)250.5 (!)] TJ\n" in _stream_bytes(page)


def test_show_text_with_positioning_accepts_tuple() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(("a", -10, "b"))
        cs.end_text()
    assert b"[(a)-10 (b)] TJ\n" in _stream_bytes(page)


def test_show_text_with_positioning_rejects_non_sequence() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.show_text_with_positioning("not a list")  # type: ignore[arg-type]


def test_show_text_with_positioning_rejects_invalid_item_type() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(["ok", object()])  # type: ignore[list-item]


def test_show_text_with_positioning_rejects_bool_item() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(["ok", True])  # type: ignore[list-item]


def test_show_text_with_positioning_non_ascii_uses_hex_form() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text_with_positioning(["中", -100, "国"])
        cs.end_text()
    assert b"[<4E2D>-100 <56FD>] TJ\n" in _stream_bytes(page)


def test_show_text_with_positioning_empty_list() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.show_text_with_positioning([])
    assert _stream_bytes(page) == b"[] TJ\n"


# ------------------------------------------------------------------
# extended graphics state — alpha, blend mode, soft mask
# ------------------------------------------------------------------


def test_set_graphics_state_parameters_emits_gs_with_registered_key() -> None:
    """``set_graphics_state_parameters(PDExtendedGraphicsState)`` registers
    the dictionary under /Resources/ExtGState (key ``gs1``) and emits
    ``/gs1 gs``."""
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    doc = PDDocument()
    page = _make_page(doc)
    ext = PDExtendedGraphicsState()
    ext.set_stroking_alpha_constant(0.5)

    with PDPageContentStream(doc, page) as cs:
        cs.set_graphics_state_parameters(ext)

    assert _stream_bytes(page) == b"/gs1 gs\n"
    res = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    assert res is not None
    assert res.get_dictionary_object(COSName.get_pdf_name("gs1")) is ext.get_cos_object()


def test_set_graphics_state_parameters_reuses_existing_key() -> None:
    """A second call with the same ExtGState reuses the existing slot
    (no new gs2 is allocated)."""
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    doc = PDDocument()
    page = _make_page(doc)
    ext = PDExtendedGraphicsState()
    ext.set_non_stroking_alpha_constant(0.3)

    with PDPageContentStream(doc, page) as cs:
        cs.set_graphics_state_parameters(ext)
        cs.set_graphics_state_parameters(ext)

    assert _stream_bytes(page) == b"/gs1 gs\n/gs1 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    assert [n.get_name() for n in sub.key_set()] == ["gs1"]


def test_set_stroking_alpha_constant_creates_extgstate_with_ca() -> None:
    """``set_stroking_alpha_constant(0.5)`` registers a fresh ExtGState
    carrying ``/CA 0.5`` and emits ``/gs1 gs``."""
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_alpha_constant(0.5)

    assert _stream_bytes(page) == b"/gs1 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    gs = sub.get_dictionary_object(COSName.get_pdf_name("gs1"))
    assert gs.get_float(COSName.get_pdf_name("CA")) == 0.5
    # Non-stroking key not set.
    assert gs.get_dictionary_object(COSName.get_pdf_name("ca")) is None


def test_set_non_stroking_alpha_constant_creates_extgstate_with_ca_lower() -> None:
    """``set_non_stroking_alpha_constant(0.25)`` writes ``/ca 0.25``."""
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_alpha_constant(0.25)

    assert _stream_bytes(page) == b"/gs1 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    gs = sub.get_dictionary_object(COSName.get_pdf_name("gs1"))
    assert gs.get_float(COSName.get_pdf_name("ca")) == 0.25
    assert gs.get_dictionary_object(COSName.get_pdf_name("CA")) is None


def test_set_stroking_then_non_stroking_alpha_allocates_two_extgstates() -> None:
    """Two separate alpha calls allocate two distinct ExtGState slots
    (``gs1``, ``gs2``) — each helper builds a fresh ExtGState."""
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_alpha_constant(0.7)
        cs.set_non_stroking_alpha_constant(0.4)

    assert _stream_bytes(page) == b"/gs1 gs\n/gs2 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    assert sorted(n.get_name() for n in sub.key_set()) == ["gs1", "gs2"]


def test_set_blend_mode_with_blend_mode_instance() -> None:
    """``set_blend_mode(BlendMode.MULTIPLY)`` registers an ExtGState
    carrying ``/BM /Multiply`` and emits ``/gs1 gs``."""
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_blend_mode(BlendMode.MULTIPLY)

    assert _stream_bytes(page) == b"/gs1 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    gs = sub.get_dictionary_object(COSName.get_pdf_name("gs1"))
    assert gs.get_name(COSName.get_pdf_name("BM")) == "Multiply"


def test_set_blend_mode_with_string_name() -> None:
    """``set_blend_mode("Screen")`` accepts a plain string."""
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_blend_mode("Screen")

    assert _stream_bytes(page) == b"/gs1 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    gs = sub.get_dictionary_object(COSName.get_pdf_name("gs1"))
    assert gs.get_name(COSName.get_pdf_name("BM")) == "Screen"


def test_set_softmask_with_dict_writes_smask_entry() -> None:
    """``set_softmask(dict)`` registers an ExtGState carrying ``/SMask``
    pointing at the supplied COSDictionary."""
    from pypdfbox.cos import COSDictionary

    doc = PDDocument()
    page = _make_page(doc)
    smask_dict = COSDictionary()
    smask_dict.set_name(COSName.get_pdf_name("S"), "Alpha")

    with PDPageContentStream(doc, page) as cs:
        cs.set_softmask(smask_dict)

    assert _stream_bytes(page) == b"/gs1 gs\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ExtGState")
    )
    gs = sub.get_dictionary_object(COSName.get_pdf_name("gs1"))
    assert gs.get_dictionary_object(COSName.get_pdf_name("SMask")) is smask_dict


# ------------------------------------------------------------------
# pattern colour
# ------------------------------------------------------------------


def _make_tiling_pattern():  # type: ignore[no-untyped-def]
    """Build a minimal coloured tiling pattern dictionary for tests."""
    from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import (
        PDTilingPattern,
    )

    pat = PDTilingPattern()
    return pat


def _make_shading_pattern():  # type: ignore[no-untyped-def]
    from pypdfbox.pdmodel.graphics.pattern.pd_shading_pattern import (
        PDShadingPattern,
    )

    return PDShadingPattern()


def test_set_stroking_pattern_emits_pattern_cs_and_scn() -> None:
    """``set_stroking_pattern(pattern)`` emits
    ``/Pattern CS /p1 SCN`` and registers under /Resources/Pattern."""
    doc = PDDocument()
    page = _make_page(doc)
    pat = _make_tiling_pattern()

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_pattern(pat)

    assert _stream_bytes(page) == b"/Pattern CS\n/p1 SCN\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Pattern")
    )
    assert sub.get_dictionary_object(COSName.get_pdf_name("p1")) is pat.get_cos_object()


def test_set_non_stroking_pattern_emits_lowercase_operators() -> None:
    """Non-stroking variant emits ``/Pattern cs`` + ``/p1 scn``."""
    doc = PDDocument()
    page = _make_page(doc)
    pat = _make_shading_pattern()

    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_pattern(pat)

    assert _stream_bytes(page) == b"/Pattern cs\n/p1 scn\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Pattern")
    )
    assert sub.get_dictionary_object(COSName.get_pdf_name("p1")) is pat.get_cos_object()


def test_set_non_stroking_pattern_with_color_components_uncolored_tiling() -> None:
    """Optional ``color_components`` are emitted before the pattern key —
    used for uncolored tiling patterns to colour each tile from the
    underlying device-RGB / DeviceGray space."""
    doc = PDDocument()
    page = _make_page(doc)
    pat = _make_tiling_pattern()

    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_pattern(pat, [1.0, 0.0, 0.0])

    # Components emitted as bare numeric operands; pattern name follows.
    assert _stream_bytes(page) == b"/Pattern cs\n1 0 0 /p1 scn\n"


def test_set_stroking_pattern_reuses_existing_key() -> None:
    """A second call with the same pattern reuses ``p1`` rather than
    allocating a fresh slot."""
    doc = PDDocument()
    page = _make_page(doc)
    pat = _make_tiling_pattern()

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_pattern(pat)
        cs.set_stroking_pattern(pat)

    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Pattern")
    )
    assert [n.get_name() for n in sub.key_set()] == ["p1"]


def test_two_distinct_patterns_get_separate_keys() -> None:
    """Two distinct PDAbstractPattern objects → ``p1`` and ``p2``."""
    doc = PDDocument()
    page = _make_page(doc)
    pat_a = _make_tiling_pattern()
    pat_b = _make_shading_pattern()

    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_pattern(pat_a)
        cs.set_non_stroking_pattern(pat_b)

    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Pattern")
    )
    assert sorted(n.get_name() for n in sub.key_set()) == ["p1", "p2"]


def test_set_stroking_pattern_rejects_non_pattern() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.set_stroking_pattern("not a pattern")  # type: ignore[arg-type]


# ------------------------------------------------------------------
# shading fill
# ------------------------------------------------------------------


def _make_shading():  # type: ignore[no-untyped-def]
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import (
        PDShadingType2,
    )

    return PDShadingType2()


def test_shading_fill_emits_sh_with_registered_key() -> None:
    """``shading_fill(shading)`` registers the shading under
    /Resources/Shading (key ``sh1``) and emits ``/sh1 sh``."""
    doc = PDDocument()
    page = _make_page(doc)
    sh = _make_shading()

    with PDPageContentStream(doc, page) as cs:
        cs.shading_fill(sh)

    assert _stream_bytes(page) == b"/sh1 sh\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Shading")
    )
    assert sub.get_dictionary_object(COSName.get_pdf_name("sh1")) is sh.get_cos_object()


def test_shading_fill_reuses_existing_key() -> None:
    """A second shading_fill with the same shading reuses ``sh1``."""
    doc = PDDocument()
    page = _make_page(doc)
    sh = _make_shading()

    with PDPageContentStream(doc, page) as cs:
        cs.shading_fill(sh)
        cs.shading_fill(sh)

    assert _stream_bytes(page) == b"/sh1 sh\n/sh1 sh\n"
    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Shading")
    )
    assert [n.get_name() for n in sub.key_set()] == ["sh1"]


def test_two_distinct_shadings_get_separate_keys() -> None:
    """Two distinct shadings → ``sh1`` and ``sh2``."""
    doc = PDDocument()
    page = _make_page(doc)
    sh_a = _make_shading()
    sh_b = _make_shading()

    with PDPageContentStream(doc, page) as cs:
        cs.shading_fill(sh_a)
        cs.shading_fill(sh_b)

    sub = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Shading")
    )
    assert sorted(n.get_name() for n in sub.key_set()) == ["sh1", "sh2"]


def test_shading_fill_rejects_non_shading() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs, pytest.raises(TypeError):
        cs.shading_fill(42)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# combined alpha / blend / pattern / shading round-trip through PDPage
# ------------------------------------------------------------------


def test_alpha_blend_pattern_shading_combined_round_trip() -> None:
    """Mix alpha, blend, pattern, and shading in one content stream and
    verify both operator order and that resources land under their
    expected /Resources sub-dictionaries."""
    from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

    doc = PDDocument()
    page = _make_page(doc)
    pat = _make_tiling_pattern()
    sh = _make_shading()

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_alpha_constant(0.5)
        cs.set_blend_mode(BlendMode.MULTIPLY)
        cs.set_non_stroking_pattern(pat)
        cs.add_rect(0, 0, 100, 100)
        cs.fill()
        cs.shading_fill(sh)

    body = _stream_bytes(page)
    # Two ExtGState slots (gs1=alpha, gs2=blend), one pattern (p1),
    # one shading (sh1). gs3 etc. not allocated.
    assert b"/gs1 gs" in body  # alpha
    assert b"/gs2 gs" in body  # blend
    assert b"/Pattern cs" in body
    assert b"/p1 scn" in body
    assert b"0 0 100 100 re" in body
    assert b"f\n" in body
    assert b"/sh1 sh" in body

    res = page.get_resources().get_cos_object()
    ext = res.get_dictionary_object(COSName.get_pdf_name("ExtGState"))
    assert sorted(n.get_name() for n in ext.key_set()) == ["gs1", "gs2"]
    pat_sub = res.get_dictionary_object(COSName.get_pdf_name("Pattern"))
    assert [n.get_name() for n in pat_sub.key_set()] == ["p1"]
    sh_sub = res.get_dictionary_object(COSName.get_pdf_name("Shading"))
    assert [n.get_name() for n in sh_sub.key_set()] == ["sh1"]


# ------------------------------------------------------------------
# AppendMode predicates / new aliases / raw-write helpers
# ------------------------------------------------------------------


def test_append_mode_is_overwrite_and_is_prepend() -> None:
    assert AppendMode.OVERWRITE.is_overwrite() is True
    assert AppendMode.OVERWRITE.is_prepend() is False
    assert AppendMode.APPEND.is_overwrite() is False
    assert AppendMode.APPEND.is_prepend() is False
    assert AppendMode.PREPEND.is_overwrite() is False
    assert AppendMode.PREPEND.is_prepend() is True


def test_set_rendering_mode_alias_emits_tr() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_rendering_mode(2)
    assert _stream_bytes(page) == b"2 Tr\n"


def test_set_rendering_mode_alias_validates_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_rendering_mode(8)
    cs.close()


def test_begin_marked_content_with_mcid_emits_bdc() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content_with_mcid("P", 7)
        cs.end_marked_content()
    assert _stream_bytes(page) == b"/P <</MCID 7>> BDC\nEMC\n"


def test_begin_marked_content_with_mcid_rejects_negative() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.begin_marked_content_with_mcid("P", -1)
    cs.close()


def test_begin_marked_content_with_mcid_zero_allowed() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content_with_mcid(COSName.get_pdf_name("Span"), 0)
    assert _stream_bytes(page) == b"/Span <</MCID 0>> BDC\n"


def test_add_comment_writes_percent_and_newline() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_comment("hello world")
        cs.move_to(0, 0)
    assert _stream_bytes(page) == b"%hello world\n0 0 m\n"


def test_add_comment_rejects_embedded_newline() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.add_comment("first\nsecond")
    with pytest.raises(ValueError):
        cs.add_comment("first\rsecond")
    cs.close()


def test_append_raw_commands_str_bytes_and_numeric() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.append_raw_commands("BT\n")
        cs.append_raw_commands(b"/F0 12 Tf\n")
        cs.append_raw_commands(7)
        cs.append_raw_commands(2.5)
        cs.append_raw_commands("ET\n")
    assert _stream_bytes(page) == b"BT\n/F0 12 Tf\n7 2.5 ET\n"


def test_append_raw_commands_rejects_bool_and_other_types() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(TypeError):
        cs.append_raw_commands(True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cs.append_raw_commands(object())  # type: ignore[arg-type]
    cs.close()


def test_set_line_dash_pattern_alias_emits_d() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_line_dash_pattern([3, 2], 0)
    # Each element is a writeOperand call (trailing space), matching PDFBox.
    assert _stream_bytes(page) == b"[3 2 ] 0 d\n"


def test_close_and_fill_and_stroke_aliases_emit_b_and_b_star() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.close_and_fill_and_stroke()
        cs.close_and_fill_and_stroke_even_odd()
    assert _stream_bytes(page) == b"b\nb*\n"


def test_set_marked_content_point_alias_emits_mp() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_marked_content_point("Span")
    assert _stream_bytes(page) == b"/Span MP\n"


def test_set_marked_content_point_with_properties_alias_emits_dp() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_marked_content_point_with_properties("Span", "MC0")
    assert _stream_bytes(page) == b"/Span /MC0 DP\n"


# ------------------------------------------------------------------
# RenderingMode enum + set_text_rendering_mode acceptance
# ------------------------------------------------------------------


def test_set_text_rendering_mode_accepts_rendering_mode_enum() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingMode

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_text_rendering_mode(RenderingMode.FILL_STROKE)
    assert _stream_bytes(page) == b"2 Tr\n"


def test_set_rendering_mode_accepts_rendering_mode_enum() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingMode

    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_rendering_mode(RenderingMode.NEITHER)
    assert _stream_bytes(page) == b"3 Tr\n"


def test_set_text_rendering_mode_int_path_still_works() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_text_rendering_mode(7)
    assert _stream_bytes(page) == b"7 Tr\n"


def test_rendering_mode_enum_int_value_round_trip() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingMode

    for member in RenderingMode:
        assert RenderingMode.from_int(member.int_value()) is member


def test_rendering_mode_enum_predicates() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingMode

    assert RenderingMode.FILL.is_fill()
    assert not RenderingMode.FILL.is_stroke()
    assert not RenderingMode.FILL.is_clip()

    assert RenderingMode.STROKE.is_stroke()
    assert not RenderingMode.STROKE.is_fill()
    assert not RenderingMode.STROKE.is_clip()

    assert RenderingMode.FILL_STROKE.is_fill()
    assert RenderingMode.FILL_STROKE.is_stroke()
    assert not RenderingMode.FILL_STROKE.is_clip()

    assert not RenderingMode.NEITHER.is_fill()
    assert not RenderingMode.NEITHER.is_stroke()
    assert not RenderingMode.NEITHER.is_clip()

    assert RenderingMode.FILL_CLIP.is_fill()
    assert RenderingMode.FILL_CLIP.is_clip()
    assert not RenderingMode.FILL_CLIP.is_stroke()

    assert RenderingMode.STROKE_CLIP.is_stroke()
    assert RenderingMode.STROKE_CLIP.is_clip()
    assert not RenderingMode.STROKE_CLIP.is_fill()

    assert RenderingMode.FILL_STROKE_CLIP.is_fill()
    assert RenderingMode.FILL_STROKE_CLIP.is_stroke()
    assert RenderingMode.FILL_STROKE_CLIP.is_clip()

    assert RenderingMode.NEITHER_CLIP.is_clip()
    assert not RenderingMode.NEITHER_CLIP.is_fill()
    assert not RenderingMode.NEITHER_CLIP.is_stroke()


def test_rendering_mode_from_int_unknown_raises() -> None:
    from pypdfbox.pdmodel.graphics.state import RenderingMode

    with pytest.raises(IndexError):
        RenderingMode.from_int(8)


# ------------------------------------------------------------------
# 0..1 range validation on RGB / Gray / CMYK setters
# ------------------------------------------------------------------


def test_set_stroking_color_rgb_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_stroking_color_rgb(1.5, 0.0, 0.0)
    with pytest.raises(ValueError):
        cs.set_stroking_color_rgb(0.0, -0.1, 0.0)
    with pytest.raises(ValueError):
        cs.set_stroking_color_rgb(0.0, 0.0, 2.0)
    cs.close()


def test_set_non_stroking_color_rgb_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_non_stroking_color_rgb(-0.5, 0.5, 0.5)
    cs.close()


def test_set_stroking_color_rgb_boundary_values_accepted() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.set_stroking_color_rgb(1.0, 1.0, 1.0)
    assert _stream_bytes(page) == b"0 0 0 RG\n1 1 1 RG\n"


def test_set_stroking_color_gray_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_stroking_color_gray(1.01)
    with pytest.raises(ValueError):
        cs.set_stroking_color_gray(-0.01)
    cs.close()


def test_set_non_stroking_color_gray_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_non_stroking_color_gray(-0.5)
    cs.close()


def test_set_stroking_color_cmyk_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_stroking_color_cmyk(1.5, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        cs.set_stroking_color_cmyk(0.0, 0.0, 0.0, -0.5)
    cs.close()


def test_set_non_stroking_color_cmyk_rejects_out_of_range() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    with pytest.raises(ValueError):
        cs.set_non_stroking_color_cmyk(0.0, 1.5, 0.0, 0.0)
    cs.close()


def test_set_color_cmyk_boundary_values_accepted() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_cmyk(0.0, 0.0, 0.0, 0.0)
        cs.set_non_stroking_color_cmyk(1.0, 1.0, 1.0, 1.0)
    assert _stream_bytes(page) == b"0 0 0 0 K\n1 1 1 1 k\n"


# ------------------------------------------------------------------
# private interval helpers
# ------------------------------------------------------------------


def test_is_outside_one_interval_helper() -> None:
    from pypdfbox.pdmodel.pd_page_content_stream import (
        _is_outside_one_interval,
    )

    assert not _is_outside_one_interval(0.0)
    assert not _is_outside_one_interval(0.5)
    assert not _is_outside_one_interval(1.0)
    assert _is_outside_one_interval(-0.0001)
    assert _is_outside_one_interval(1.0001)
    assert _is_outside_one_interval(-1.0)
    assert _is_outside_one_interval(2.0)


def test_is_outside_255_interval_helper() -> None:
    from pypdfbox.pdmodel.pd_page_content_stream import (
        _is_outside_255_interval,
    )

    assert not _is_outside_255_interval(0)
    assert not _is_outside_255_interval(128)
    assert not _is_outside_255_interval(255)
    assert _is_outside_255_interval(-1)
    assert _is_outside_255_interval(256)
    assert _is_outside_255_interval(1000)
