from __future__ import annotations

import sys
import types

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.pd_page_content_stream import (
    AppendMode,
    PDPageContentStream,
    _coerce_append_mode,
    _format_number,
)
from pypdfbox.pdmodel.pd_resources import PDResources

_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


def _stream_bytes(page: PDPage) -> bytes:
    return page.get_contents()


def test_wave396_form_content_stream_reuses_existing_resources() -> None:
    doc = PDDocument()
    form = PDFormXObject(COSStream())
    resources = PDResources()
    form.set_resources(resources)

    with PDPageContentStream(doc, form) as cs:
        assert cs.get_resources().get_cos_object() is resources.get_cos_object()
        cs.move_to(1, 2)

    assert form.get_cos_object().get_raw_data() == b"1 2 m\n"


def test_wave396_prepend_to_existing_contents_array_inserts_at_zero() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    first = COSStream()
    first.set_raw_data(b"first\n")
    second = COSStream()
    second.set_raw_data(b"second\n")
    arr = COSArray([first, second])
    page.get_cos_object().set_item(_CONTENTS, arr)

    with PDPageContentStream(doc, page, AppendMode.PREPEND) as cs:
        cs.move_to(3, 4)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 3
    prepended = contents.get(0)
    assert isinstance(prepended, COSStream)
    assert prepended.get_raw_data() == b"3 4 m\n"
    assert contents.get(1) is first
    assert contents.get(2) is second


def test_wave396_get_resources_returns_page_resources() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        assert cs.get_resources().get_cos_object() is page.get_resources().get_cos_object()


def test_wave396_nonstroking_pdcolor_device_rgb_and_cmyk_paths() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE))
        cs.set_non_stroking_color(
            PDColor([0.4, 0.5, 0.6, 0.7], PDDeviceCMYK.INSTANCE)
        )

    assert _stream_bytes(page) == b"0.1 0.2 0.3 rg\n0.4 0.5 0.6 0.7 k\n"


def test_wave396_pdcolor_pattern_name_emits_scn_without_resource_registration() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    pattern_name = COSName.get_pdf_name("P1")
    stroking = PDColor([0.5], pattern_name, PDPattern(PDDeviceGray.INSTANCE))
    nonstroking = PDColor(pattern_name, PDPattern())

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(stroking)
        cs.set_non_stroking_color(nonstroking)

    assert _stream_bytes(page) == b"0.5 /P1 SCN\n/P1 scn\n"


def test_wave396_set_font_rejects_non_font() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with (
        PDPageContentStream(doc, page) as cs,
        pytest.raises(TypeError, match="PDFont"),
    ):
        cs.set_font(object(), 12)  # type: ignore[arg-type]


def test_wave396_soft_mask_and_pattern_aliases_emit_expected_resources() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    smask = COSDictionary()
    pattern = COSDictionary()

    with PDPageContentStream(doc, page) as cs:
        cs.set_soft_mask(smask)
        cs.set_pattern_stroke(pattern)
        cs.set_pattern_fill(pattern)
        cs.set_stroking_pattern(pattern, [0.25])

    body = _stream_bytes(page)
    assert b"/gs0 gs\n" in body
    assert body.count(b"/p0") == 3
    assert b"/Pattern CS\n/p0 SCN\n" in body
    assert b"/Pattern cs\n/p0 scn\n" in body
    assert b"/Pattern CS\n0.25 /p0 SCN\n" in body


@pytest.mark.parametrize(
    ("line_width", "has_stroke", "has_fill", "expected"),
    [
        (2.0, True, True, b"B\n"),
        (2.0, True, False, b"S\n"),
        (2.0, False, True, b"f\n"),
        (2.0, False, False, b"n\n"),
        (0.0, True, True, b"f\n"),
    ],
)
def test_wave396_draw_shape_operator_dispatch(
    line_width: float,
    has_stroke: bool,
    has_fill: bool,
    expected: bytes,
) -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.draw_shape(line_width, has_stroke, has_fill)

    assert _stream_bytes(page) == expected


def test_wave396_draw_image_matrix_overload_rejects_extra_operands() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    img = _make_fontless_image()

    with (
        PDPageContentStream(doc, page) as cs,
        pytest.raises(TypeError, match="transform_matrix overload"),
    ):
        cs.draw_image(img, [1, 0, 0, 1, 0, 0], 0)


def _make_fontless_image():
    from pypdfbox.pdmodel.graphics.image import PDImageXObject

    image = PDImageXObject(COSStream())
    image.set_width(1)
    image.set_height(1)
    return image


def test_wave396_image_factory_import_errors_raise_guidance(monkeypatch) -> None:
    import pypdfbox.pdmodel.pd_page_content_stream as pcs

    def missing_factories(name: str):
        if name.startswith("pypdfbox.pdmodel.graphics.image."):
            raise ImportError(name)
        return __import__(name)

    assert missing_factories("math").__name__ == "math"

    monkeypatch.setattr(pcs.importlib, "import_module", missing_factories)

    with pytest.raises(NotImplementedError, match="JPEGFactory"):
        PDPageContentStream._coerce_to_image_xobject(b"raw", PDDocument())


def test_wave396_image_factory_pil_import_error_reaches_lossless_guidance(
    monkeypatch,
) -> None:
    import pypdfbox.pdmodel.pd_page_content_stream as pcs

    lossless_module = types.SimpleNamespace(
        LosslessFactory=types.SimpleNamespace(
            create_from_image=lambda document, image: None
        )
    )

    def fake_import(name: str):
        if name.endswith("jpeg_factory"):
            return types.SimpleNamespace()
        if name.endswith("lossless_factory"):
            return lossless_module
        if name == "PIL.Image":
            raise ImportError(name)
        return __import__(name)

    assert fake_import("math").__name__ == "math"

    monkeypatch.setattr(pcs.importlib, "import_module", fake_import)

    with pytest.raises(NotImplementedError, match="JPEGFactory"):
        PDPageContentStream._coerce_to_image_xobject("not-jpeg.png", PDDocument())


def test_wave396_jpeg_path_and_bytes_raise_when_jpeg_factory_missing(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_image_factories(monkeypatch, jpeg=False, lossless=True)
    jpg = tmp_path / "sample.jpg"
    jpg.write_bytes(b"\xff\xd8fake")

    with pytest.raises(NotImplementedError, match="JPEGFactory"):
        PDPageContentStream._coerce_to_image_xobject(jpg, PDDocument())

    with pytest.raises(NotImplementedError, match="JPEGFactory"):
        PDPageContentStream._coerce_to_image_xobject(b"\xff\xd8fake", PDDocument())


def test_wave396_png_path_and_non_jpeg_bytes_raise_when_lossless_missing(
    tmp_path,
    monkeypatch,
) -> None:
    _install_fake_image_factories(monkeypatch, jpeg=True, lossless=False)
    png = tmp_path / "sample.png"
    png.write_bytes(b"not a real png")

    with pytest.raises(NotImplementedError, match="JPEGFactory"):
        PDPageContentStream._coerce_to_image_xobject(png, PDDocument())

    with pytest.raises(NotImplementedError, match="JPEGFactory"):
        PDPageContentStream._coerce_to_image_xobject(b"not-jpeg", PDDocument())


def _install_fake_image_factories(
    monkeypatch: pytest.MonkeyPatch,
    *,
    jpeg: bool,
    lossless: bool,
) -> None:
    jpeg_module = types.ModuleType("pypdfbox.pdmodel.graphics.image.jpeg_factory")
    lossless_module = types.ModuleType(
        "pypdfbox.pdmodel.graphics.image.lossless_factory"
    )
    if jpeg:
        jpeg_module.JPEGFactory = types.SimpleNamespace(  # type: ignore[attr-defined]
            create_from_byte_array=lambda document, data: None
        )
    if lossless:
        lossless_module.LosslessFactory = types.SimpleNamespace(  # type: ignore[attr-defined]
            create_from_image=lambda document, image: None
        )
    monkeypatch.setitem(sys.modules, jpeg_module.__name__, jpeg_module)
    monkeypatch.setitem(sys.modules, lossless_module.__name__, lossless_module)


def test_wave396_draw_image_rejects_unknown_object_after_factory_probe() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with (
        PDPageContentStream(doc, page) as cs,
        pytest.raises(TypeError, match="PDImageXObject"),
    ):
        cs.draw_image(object(), 0, 0)


def test_wave396_draw_form_rejects_wrong_type() -> None:
    doc = PDDocument()
    page = _make_page(doc)

    with (
        PDPageContentStream(doc, page) as cs,
        pytest.raises(TypeError, match="PDFormXObject"),
    ):
        cs.draw_form(object())  # type: ignore[arg-type]


def test_wave396_marked_content_point_registers_property_list_once() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    prop = PDPropertyList(COSDictionary())

    with PDPageContentStream(doc, page) as cs:
        cs.add_marked_content_point_with_dict("Span", prop)
        cs.add_marked_content_point_with_dict("Span", prop)

    assert _stream_bytes(page) == b"/Span /Prop0 DP\n/Span /Prop0 DP\n"


def test_wave396_color_space_pattern_name_and_missing_cos_paths() -> None:
    class PatternNameOnly:
        def get_name(self) -> str:
            return "Pattern"

    class MissingCOS:
        def get_name(self) -> str:
            return "Custom"

    doc = PDDocument()
    page = _make_page(doc)

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_space(PatternNameOnly())
        with pytest.raises(TypeError, match="no COS representation"):
            cs.set_non_stroking_color_space(MissingCOS())

    assert _stream_bytes(page) == b"/Pattern CS\n"


def test_wave396_append_mode_string_and_error_coercions() -> None:
    assert _coerce_append_mode("append") is AppendMode.APPEND
    assert _coerce_append_mode("PREPEND") is AppendMode.PREPEND
    assert _coerce_append_mode(True) is AppendMode.APPEND
    assert _coerce_append_mode(False) is AppendMode.OVERWRITE

    with pytest.raises(ValueError, match="unknown AppendMode"):
        _coerce_append_mode("sideways")
    with pytest.raises(TypeError, match="append_mode"):
        _coerce_append_mode(1)  # type: ignore[arg-type]


def test_wave396_nonfinite_number_rejected_and_existing_font_key_reused() -> None:
    with pytest.raises(ValueError, match="finite"):
        _format_number(float("inf"))

    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")

    resources = PDResources()
    resources.add(COSName.get_pdf_name("Font"), font.get_cos_object())
    page.set_resources(resources)

    with PDPageContentStream(doc, page) as cs:
        cs.set_font(font, 9)

    assert _stream_bytes(page) == b"/F0 9 Tf\n"
