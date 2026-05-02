"""Tests for upstream-named accessor methods on ``PDFRenderer``:
``get_annotations_filter`` / ``set_annotations_filter``,
``get_rendering_hints`` / ``set_rendering_hints``,
``get_page_image``, ``get_document``, ``is_group_enabled``.

Mirrors ``PDFRenderer.getAnnotationsFilter()`` etc. — these are plain
store/recall accessors except ``is_group_enabled``, which consults the
catalog's ``/OCProperties``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)
from pypdfbox.rendering import PDFRenderer


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
    doc.add_page(page)
    return doc, page


# ---------------------------------------------------------------------------
# annotation filter
# ---------------------------------------------------------------------------


def test_default_annotations_filter_accepts_every_annotation() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    filt = renderer.get_annotations_filter()
    assert callable(filt)
    # Default upstream filter returns True for any annotation.
    assert filt(object()) is True
    assert filt(None) is True


def test_set_annotations_filter_replaces_default() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    sentinel = object()
    captured: list[object] = []

    def my_filter(annotation: object) -> bool:
        captured.append(annotation)
        return False

    renderer.set_annotations_filter(my_filter)
    assert renderer.get_annotations_filter() is my_filter
    assert renderer.get_annotations_filter()(sentinel) is False
    assert captured == [sentinel]


# ---------------------------------------------------------------------------
# rendering hints
# ---------------------------------------------------------------------------


def test_rendering_hints_default_is_none() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.get_rendering_hints() is None


def test_set_rendering_hints_round_trips() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    hints = {"KEY_ANTIALIASING": "VALUE_ANTIALIAS_ON"}
    renderer.set_rendering_hints(hints)
    assert renderer.get_rendering_hints() is hints
    renderer.set_rendering_hints(None)
    assert renderer.get_rendering_hints() is None


# ---------------------------------------------------------------------------
# get_document
# ---------------------------------------------------------------------------


def test_get_document_returns_constructor_argument() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.get_document() is doc


# ---------------------------------------------------------------------------
# get_page_image
# ---------------------------------------------------------------------------


def test_get_page_image_is_none_before_first_render() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.get_page_image() is None


def test_get_page_image_returns_last_render_after_render_image() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)
    cached = renderer.get_page_image()
    assert cached is img


def test_get_page_image_updates_after_subsequent_render() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    first = renderer.render_image(0)
    second = renderer.render_image_with_dpi(0, dpi=144.0)
    cached = renderer.get_page_image()
    # Should always reflect the most recent render.
    assert cached is second
    assert cached is not first


# ---------------------------------------------------------------------------
# is_group_enabled
# ---------------------------------------------------------------------------


def test_is_group_enabled_returns_true_when_no_oc_properties() -> None:
    """Mirrors upstream:
        return ocProperties == null || ocProperties.isGroupEnabled(group);
    """
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    # No /OCProperties in a fresh document.
    assert doc.get_document_catalog().get_oc_properties() is None
    assert renderer.is_group_enabled(object()) is True


def test_is_group_enabled_consults_oc_properties_when_present() -> None:
    """When /OCProperties exists, the renderer must defer to its
    ``is_group_enabled``."""
    doc, _ = _make_doc()
    # Build a minimal /OCProperties with an OCG named "Layer1".
    ocg_dict = COSDictionary()
    ocg_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("OCG"))
    ocg_dict.set_item(
        COSName.get_pdf_name("Name"), COSName.get_pdf_name("Layer1")
    )
    ocg = PDOptionalContentGroup(ocg_dict)

    ocgs_array = COSArray()
    ocgs_array.add(ocg_dict)

    d_dict = COSDictionary()
    # /D /OFF includes our OCG → it must be reported as disabled.
    off_array = COSArray()
    off_array.add(ocg_dict)
    d_dict.set_item(COSName.get_pdf_name("OFF"), off_array)

    oc_dict = COSDictionary()
    oc_dict.set_item(COSName.get_pdf_name("OCGs"), ocgs_array)
    oc_dict.set_item(COSName.get_pdf_name("D"), d_dict)
    oc_props = PDOptionalContentProperties(oc_dict)
    doc.get_document_catalog().set_oc_properties(oc_props)

    renderer = PDFRenderer(doc)
    assert renderer.is_group_enabled(ocg) is False
