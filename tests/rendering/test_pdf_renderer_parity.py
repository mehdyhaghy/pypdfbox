"""Parity tests for upstream-named public surface on ``PDFRenderer``.

Covers the flag-style setters/getters and ``is_page_image_with_annotations``
so downstream tooling that mirrors PDFBox call sites doesn't blow up on
``AttributeError``. Render-loop behaviour is exercised in
``test_pdf_renderer.py`` — these tests intentionally stay shallow.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    return doc, page


# ---------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------


def test_subsampling_allowed_default_is_false() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.is_subsampling_allowed() is False


def test_default_destination_default_is_view() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.get_default_destination() == "View"


def test_image_downscaling_optimization_threshold_default_is_half() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.get_image_downscaling_optimization_threshold() == 0.5


# ---------------------------------------------------------------------------
# setter / getter round-trip
# ---------------------------------------------------------------------------


def test_set_subsampling_allowed_round_trips() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer.set_subsampling_allowed(True)
    assert renderer.is_subsampling_allowed() is True
    renderer.set_subsampling_allowed(False)
    assert renderer.is_subsampling_allowed() is False


def test_set_default_destination_round_trips() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer.set_default_destination("Print")
    assert renderer.get_default_destination() == "Print"
    renderer.set_default_destination("Export")
    assert renderer.get_default_destination() == "Export"


def test_set_image_downscaling_optimization_threshold_round_trips() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer.set_image_downscaling_optimization_threshold(0.25)
    assert renderer.get_image_downscaling_optimization_threshold() == 0.25
    renderer.set_image_downscaling_optimization_threshold(1.0)
    assert renderer.get_image_downscaling_optimization_threshold() == 1.0


def test_image_downscaling_optimization_threshold_coerces_to_float() -> None:
    """Upstream takes ``float``; an int from a config layer should not
    silently break ``> threshold`` comparisons later."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    renderer.set_image_downscaling_optimization_threshold(1)
    value = renderer.get_image_downscaling_optimization_threshold()
    assert isinstance(value, float)
    assert value == 1.0


# ---------------------------------------------------------------------------
# is_page_image_with_annotations
# ---------------------------------------------------------------------------


def test_is_page_image_with_annotations_false_when_no_annots_entry() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    assert renderer.is_page_image_with_annotations(0) is False


def test_is_page_image_with_annotations_false_when_annots_empty() -> None:
    doc, page = _make_doc()
    # An empty /Annots array is allowed and should not count.
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), COSArray())
    renderer = PDFRenderer(doc)
    assert renderer.is_page_image_with_annotations(0) is False


def test_is_page_image_with_annotations_true_when_annots_present() -> None:
    doc, page = _make_doc()
    annots = COSArray()
    ann = COSDictionary()
    ann.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    ann.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    annots.add(ann)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    renderer = PDFRenderer(doc)
    assert renderer.is_page_image_with_annotations(0) is True
