"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/rendering/TestRendering.java

Plus parity coverage for the renderer's private/protected helpers
(``has_blend_mode`` / ``is_bitonal`` / ``create_default_rendering_hints``
/ ``create_page_drawer`` / ``transform`` / ``render_page_to_graphics``).
Upstream tests for these helpers live behind a
disabled-cross-JVM-comparison gate (TestPDFToImage), so we cover them
here against synthesised in-memory documents that don't depend on
JVM-rendered fixtures.
"""

from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.rendering import PDFRenderer, RenderDestination


def _make_doc(
    width: float = 100.0, height: float = 100.0
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


# ---------------------------------------------------------------------------
# render() — the only enabled upstream test (TestRendering.render).
# Upstream loads every PDF in src/test/resources/input/rendering and asserts
# renderImage(0) does not throw. We mirror that with a synthesised in-memory
# document since fixture-laden cross-JVM rendering files are not in scope.
# ---------------------------------------------------------------------------


def test_render() -> None:
    doc, _ = _make_doc(80.0, 60.0)
    renderer = PDFRenderer(doc)
    image = renderer.render_image(0)
    assert image is not None
    assert image.size == (80, 60)


# ---------------------------------------------------------------------------
# has_blend_mode (Java 559–582)
# ---------------------------------------------------------------------------


def test_has_blend_mode_returns_false_when_no_resources() -> None:
    doc, page = _make_doc()
    page.get_cos_object().remove_item(COSName.RESOURCES)
    renderer = PDFRenderer(doc)
    assert renderer.has_blend_mode(page) is False


def test_has_blend_mode_returns_false_for_normal_blends() -> None:
    doc, page = _make_doc()
    resources = page.get_or_create_resources()
    extg = PDExtendedGraphicsState()
    extg.set_blend_mode(BlendMode.NORMAL)
    resources.put(COSName.get_pdf_name("ExtG1"), extg)
    page.set_resources(resources)
    renderer = PDFRenderer(doc)
    assert renderer.has_blend_mode(page) is False


def test_has_blend_mode_returns_true_when_any_extg_is_non_normal() -> None:
    doc, page = _make_doc()
    resources = page.get_or_create_resources()
    extg_normal = PDExtendedGraphicsState()
    extg_normal.set_blend_mode(BlendMode.NORMAL)
    extg_multiply = PDExtendedGraphicsState()
    extg_multiply.set_blend_mode(BlendMode.MULTIPLY)
    resources.put(COSName.get_pdf_name("ExtN"), extg_normal)
    resources.put(COSName.get_pdf_name("ExtM"), extg_multiply)
    page.set_resources(resources)
    renderer = PDFRenderer(doc)
    assert renderer.has_blend_mode(page) is True


def test_has_blend_mode_skips_null_extg_entries() -> None:
    # PDFBOX-3950: an /ExtGState key may exist with no value — upstream
    # silently skips. We do too.
    doc, page = _make_doc()
    # Inject a stub /ExtGState entry that has no /BM key (BlendMode is
    # None on the PDExtendedGraphicsState wrapping it).
    resources = page.get_or_create_resources()
    extg = PDExtendedGraphicsState()  # default → no /BM in the dict
    resources.put(COSName.get_pdf_name("Empty"), extg)
    page.set_resources(resources)
    renderer = PDFRenderer(doc)
    # No blend mode on the only /ExtGState → upstream returns False
    # (the loop continues and finds nothing non-Normal).
    assert renderer.has_blend_mode(page) is False


# ---------------------------------------------------------------------------
# is_bitonal (Java 510–528)
# ---------------------------------------------------------------------------


def test_is_bitonal_returns_false_for_none() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.is_bitonal(None) is False


def test_is_bitonal_returns_true_for_one_bit_pillow_image() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    one_bit = Image.new("1", (1, 1), 0)
    assert renderer.is_bitonal(one_bit) is True


def test_is_bitonal_returns_false_for_rgb_pillow_image() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    rgb = Image.new("RGB", (1, 1), (255, 255, 255))
    assert renderer.is_bitonal(rgb) is False


def test_is_bitonal_honours_get_bit_depth_duck_type() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)

    class FakeDevice:
        def get_bit_depth(self) -> int:
            return 1

    assert renderer.is_bitonal(FakeDevice()) is True


# ---------------------------------------------------------------------------
# create_default_rendering_hints (Java 530–542)
# ---------------------------------------------------------------------------


def test_create_default_rendering_hints_for_non_bitonal() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    hints = renderer.create_default_rendering_hints(Image.new("RGB", (1, 1)))
    assert hints["KEY_INTERPOLATION"] == "VALUE_INTERPOLATION_BICUBIC"
    assert hints["KEY_RENDERING"] == "VALUE_RENDER_QUALITY"
    assert hints["KEY_ANTIALIASING"] == "VALUE_ANTIALIAS_ON"


def test_create_default_rendering_hints_for_bitonal() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    hints = renderer.create_default_rendering_hints(Image.new("1", (1, 1)))
    assert hints["KEY_INTERPOLATION"] == "VALUE_INTERPOLATION_NEAREST_NEIGHBOR"
    assert hints["KEY_ANTIALIASING"] == "VALUE_ANTIALIAS_OFF"


# ---------------------------------------------------------------------------
# create_page_drawer (Java 552–557)
# ---------------------------------------------------------------------------


def test_create_page_drawer_returns_renderer_when_no_separate_drawer() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    drawer = renderer.create_page_drawer(parameters=None)
    # Lite renderer is its own page drawer.
    assert drawer is renderer


def test_create_page_drawer_stamps_annotation_filter_on_parameters() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    captured: list[Any] = []

    class FakeParameters:
        def set_annotation_filter(self, fn: Any) -> None:
            captured.append(fn)

    def custom_filter(_annotation: Any) -> bool:
        return False

    renderer.set_annotations_filter(custom_filter)
    renderer.create_page_drawer(FakeParameters())
    assert captured == [custom_filter]


# ---------------------------------------------------------------------------
# transform (Java 481–508)
# ---------------------------------------------------------------------------


def test_transform_unrotated_returns_pure_scale_matrix() -> None:
    doc, _ = _make_doc(100.0, 50.0)
    renderer = PDFRenderer(doc)
    crop_box = PDRectangle(0.0, 0.0, 100.0, 50.0)
    matrix = renderer.transform(None, 0, crop_box, 2.0, 3.0)
    assert matrix == (2.0, 0.0, 0.0, 3.0, 0.0, 0.0)


def test_transform_90_translates_by_height() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    crop_box = PDRectangle(0.0, 0.0, 100.0, 50.0)
    matrix = renderer.transform(None, 90, crop_box, 1.0, 1.0)
    # The translate-then-rotate composition lands the lower-left at (0, 0)
    # post-rotation. Map (0, 0) through ``matrix`` to verify.
    a, b, c, d, e, f = matrix
    x, y = (a * 0 + c * 0 + e, b * 0 + d * 0 + f)
    assert (round(x, 6), round(y, 6)) == (50.0, 0.0)


def test_transform_invokes_graphics_methods_when_present() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    calls: list[tuple[str, tuple[Any, ...]]] = []

    class FakeGraphics:
        def scale(self, sx: float, sy: float) -> None:
            calls.append(("scale", (sx, sy)))

        def translate(self, tx: float, ty: float) -> None:
            calls.append(("translate", (tx, ty)))

        def rotate(self, theta: float) -> None:
            calls.append(("rotate", (theta,)))

    crop_box = PDRectangle(0.0, 0.0, 100.0, 50.0)
    renderer.transform(FakeGraphics(), 90, crop_box, 2.0, 2.0)
    names = [c[0] for c in calls]
    assert names == ["scale", "translate", "rotate"]
    assert calls[0][1] == (2.0, 2.0)
    assert calls[1][1] == (50.0, 0.0)


# ---------------------------------------------------------------------------
# render_page_to_graphics (Java 383–467)
# ---------------------------------------------------------------------------


def test_render_page_to_graphics_pastes_into_pillow_target() -> None:
    doc, _ = _make_doc(40.0, 30.0)
    renderer = PDFRenderer(doc)
    target = Image.new("RGB", (40, 30), (0, 255, 0))  # green canvas
    renderer.render_page_to_graphics(0, target)
    # After paste, the (now-white) page render should have replaced
    # the green canvas.
    assert target.getpixel((0, 0)) == (255, 255, 255)
    assert target.getpixel((20, 15)) == (255, 255, 255)


def test_render_page_to_graphics_defaults_scale_y_to_scale_x() -> None:
    doc, _ = _make_doc(40.0, 30.0)
    renderer = PDFRenderer(doc)
    target = Image.new("RGB", (80, 60), (0, 0, 0))
    renderer.render_page_to_graphics(0, target, scale_x=2.0)
    # Doubled dims fully overwrite the black canvas.
    assert target.getpixel((0, 0)) == (255, 255, 255)
    assert target.getpixel((79, 59)) == (255, 255, 255)


def test_render_page_to_graphics_rejects_nonpositive_scale() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    target = Image.new("RGB", (40, 30))
    with pytest.raises(ValueError):
        renderer.render_page_to_graphics(0, target, scale_x=0.0)


def test_render_page_to_graphics_destination_defaults_to_view() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    # Just exercise the default-destination resolution path. No exception.
    renderer.render_page_to_graphics(0, Image.new("RGB", (50, 50)))
    assert renderer.get_default_destination() in {
        RenderDestination.VIEW.value,
        "View",
    }
