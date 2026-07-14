from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream

_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]


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


def _image(width: int = 7, height: int = 11) -> PDImageXObject:
    image = PDImageXObject(COSStream())
    image.set_width(width)
    image.set_height(height)
    return image


def test_wave438_form_without_resources_creates_and_attaches_resources() -> None:
    doc = PDDocument()
    form = PDFormXObject(COSStream())
    assert form.get_resources() is None

    with PDPageContentStream(doc, form) as cs:
        resources = cs.get_resources()
        cs.move_to(1, 2)

    assert form.get_resources().get_cos_object() is resources.get_cos_object()
    assert form.get_cos_object().get_raw_data() == b"1 2 m\n"
    doc.close()


def test_wave438_append_reset_context_wraps_existing_contents() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    existing = COSStream()
    existing.set_raw_data(b"2 w\n")
    page.get_cos_object().set_item(_CONTENTS, existing)

    with PDPageContentStream(
        doc, page, AppendMode.APPEND, reset_context=True
    ) as cs:
        cs.move_to(3, 4)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 3
    prefix = contents.get(0)
    appended = contents.get(2)
    assert isinstance(prefix, COSStream)
    assert isinstance(appended, COSStream)
    assert prefix.to_byte_array() == b"q\n"
    assert contents.get(1) is existing
    assert appended.to_byte_array() == b"Q\n3 4 m\n"
    doc.close()


def test_wave438_text_overloads_escape_hex_and_positioning() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_font(), 12)
        cs.show_text(r"a(b)\c")
        cs.move_to_next_line_show_text("next")
        cs.set_spacings_show_text(1, 2, b"\xff")
        cs.show_text_with_positioning(["A", -120, b"\x00B"])
        cs.end_text()

    assert _stream_bytes(page) == (
        b"BT\n"
        b"/F1 12 Tf\n"
        b"(a\\(b\\)\\\\c) Tj\n"
        b"(next) '\n"
        b"1 2 <FF> \"\n"
        b"[(A)-120 <0042>] TJ\n"
        b"ET\n"
    )
    doc.close()


def test_wave438_show_text_with_positioning_rejects_bool_item() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    cs.begin_text()
    cs.set_font(_make_font(), 12)

    with pytest.raises(TypeError, match="bool"):
        cs.show_text_with_positioning(["A", True])

    cs.close()
    doc.close()


def test_wave438_set_text_matrix_accepts_getters_and_get_value_objects() -> None:
    class GetterMatrix:
        def get_a(self) -> float:
            return 1.0

        def get_b(self) -> float:
            return 2.0

        def get_c(self) -> float:
            return 3.0

        def get_d(self) -> float:
            return 4.0

        def get_e(self) -> float:
            return 5.0

        def get_f(self) -> float:
            return 6.0

    class IndexedMatrix:
        def get_value(self, row: int, col: int) -> float:
            values = {
                (0, 0): 7.0,
                (0, 1): 8.0,
                (1, 0): 9.0,
                (1, 1): 10.0,
                (2, 0): 11.0,
                (2, 1): 12.0,
            }
            return values[(row, col)]

    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix(GetterMatrix())
        cs.set_text_matrix(IndexedMatrix())
        cs.end_text()

    assert _stream_bytes(page) == (
        b"BT\n1 2 3 4 5 6 Tm\n7 8 9 10 11 12 Tm\nET\n"
    )
    doc.close()


def test_wave438_text_state_guards_cover_nested_and_outside_calls() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)

    with pytest.raises(RuntimeError, match="matching begin_text"):
        cs.end_text()
    with pytest.raises(RuntimeError, match="begin_text"):
        cs.new_line()
    cs.begin_text()
    with pytest.raises(RuntimeError, match="Nested"):
        cs.begin_text()
    with pytest.raises(RuntimeError, match="not allowed within a text block"):
        cs.stroke()
    cs.end_text()
    cs.close()
    doc.close()


def test_wave438_non_device_color_space_registers_and_reuses_key() -> None:
    class FakeColorSpace:
        def __init__(self) -> None:
            self.cos = COSArray()

        def get_name(self) -> str:
            return "Lab"

        def get_cos_object(self) -> COSArray:
            return self.cos

    doc = PDDocument()
    page = _make_page(doc)
    color_space = FakeColorSpace()

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_space(color_space)
        cs.set_non_stroking_color_space(color_space)

    assert _stream_bytes(page) == b"/cs1 CS\n/cs1 cs\n"
    doc.close()


def test_wave438_color_space_without_cos_object_is_rejected() -> None:
    class NoCosColorSpace:
        def get_name(self) -> str:
            return "Lab"

    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)

    with pytest.raises(TypeError, match="no COS representation"):
        cs.set_stroking_color_space(NoCosColorSpace())

    cs.close()
    doc.close()


def test_wave438_draw_image_uses_intrinsic_size_and_reuses_xobject_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    image = _image()

    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, 2, 3)
        cs.draw_image(image, (1, 0, 0, 1, 4, 5))

    assert _stream_bytes(page) == (
        b"q\n7 0 0 11 2 3 cm\n/Im1 Do\nQ\n"
        b"q\n1 0 0 1 4 5 cm\n/Im1 Do\nQ\n"
    )
    doc.close()


def test_wave438_draw_image_rejects_bad_transform_shape() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)

    with pytest.raises(ValueError, match="6 components"):
        cs.draw_image(_image(), (1, 2, 3))
    with pytest.raises(TypeError, match="requires either"):
        cs.draw_image(_image(), 1)

    cs.close()
    doc.close()


def test_wave438_draw_form_offset_and_error_paths() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    form = PDFormXObject(COSStream())

    with PDPageContentStream(doc, page) as cs:
        cs.draw_form(form, 9, 10)

    assert _stream_bytes(page) == b"q\n1 0 0 1 9 10 cm\n/Form1 Do\nQ\n"

    cs = PDPageContentStream(doc, page)
    with pytest.raises(TypeError, match="PDFormXObject"):
        cs.draw_form(object())  # type: ignore[arg-type]
    cs.begin_text()
    with pytest.raises(RuntimeError, match="draw_form"):
        cs.draw_form(form)
    cs.end_text()
    cs.close()
    doc.close()


def test_wave438_marked_content_property_list_reuses_resource_key() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    property_list = PDPropertyList(COSDictionary())

    with PDPageContentStream(doc, page) as cs:
        cs.begin_marked_content_with_dict("Span", property_list)
        cs.add_marked_content_point_with_dict("Span", property_list)
        cs.set_marked_content_point_with_properties(
            COSName.get_pdf_name("P"), COSName.get_pdf_name("Direct")
        )
        cs.end_marked_content()

    assert _stream_bytes(page) == (
        b"/Span /Prop1 BDC\n/Span /Prop1 DP\n/P /Direct DP\nEMC\n"
    )
    doc.close()
