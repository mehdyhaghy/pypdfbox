"""Wave 1385 — annotation iteration + ``_render_annotation``.

Before this wave, ``PDFRenderer.render_image`` walked the page content
stream and stopped. AcroForm widgets, stamps, links, highlights, and
free-text annotations were silently dropped because nothing called
``show_annotation`` / ``_render_annotation``.

These tests build small in-memory PDFs whose only painted content lives
inside an annotation's Normal Appearance stream and assert that pixels
land in the expected area after a full ``render_image`` cycle. They
also exercise the visibility-flag skip path (Hidden annotations stay
invisible) and the upstream-fixture sanity check
(AcroFormsBasicFields.pdf renders something non-blank now).
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLink,
    PDAnnotationRubberStamp,
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc_with_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    # PDDocument's default constructor seeds a 612x792 page; strip it so
    # the test owns the only page and the coordinate system stays small.
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return doc, page


def _make_appearance_stream(
    bbox: PDRectangle, content: bytes
) -> PDAppearanceStream:
    """Build a minimal Form-XObject appearance stream containing
    ``content`` (raw page-content-stream bytes) with the given bbox."""
    cos_stream = COSStream()
    cos_stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    cos_stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    cos_stream.set_item(COSName.get_pdf_name("FormType"), COSName.get_pdf_name("1"))
    # /BBox = [llx lly urx ury]
    bbox_array = COSArray(
        [
            COSFloat(bbox.get_lower_left_x()),
            COSFloat(bbox.get_lower_left_y()),
            COSFloat(bbox.get_upper_right_x()),
            COSFloat(bbox.get_upper_right_y()),
        ]
    )
    cos_stream.set_item(COSName.get_pdf_name("BBox"), bbox_array)
    cos_stream.set_data(content)
    # Empty /Resources dict so the renderer's resources scope flips off
    # the page resources for the duration of the appearance walk.
    cos_stream.set_item(COSName.get_pdf_name("Resources"), COSDictionary())
    return PDAppearanceStream(cos_stream)


def _attach_normal_appearance(
    annotation: PDAnnotationWidget | PDAnnotationRubberStamp | PDAnnotationLink,
    stream: PDAppearanceStream,
) -> None:
    """Stamp ``stream`` onto ``annotation``'s ``/AP /N``."""
    ap = PDAppearanceDictionary(COSDictionary())
    ap.set_normal_appearance(stream)
    annotation.set_appearance_dictionary(ap)


def _pixels_in_rect_are_non_white(
    image, rect: PDRectangle, page_height: float
) -> bool:
    """Return True when any pixel inside ``rect`` (in PDF user space) is
    not pure white. The image's y-axis is flipped vs PDF user space."""
    llx = int(rect.get_lower_left_x())
    lly = int(rect.get_lower_left_y())
    urx = int(rect.get_upper_right_x())
    ury = int(rect.get_upper_right_y())
    # Convert to PIL coordinates (y-flip around page_height).
    img_w, img_h = image.size
    pdf_h = page_height
    scale_x = img_w / 200.0  # we know page width is 200
    scale_y = img_h / pdf_h
    px0 = max(0, int(llx * scale_x))
    px1 = min(img_w, int(urx * scale_x))
    # PDF lly maps to top in PIL; PDF ury maps to bottom in PIL after flip.
    py0 = max(0, int((pdf_h - ury) * scale_y))
    py1 = min(img_h, int((pdf_h - lly) * scale_y))
    pixels = image.load()
    for y in range(py0, py1):
        for x in range(px0, px1):
            p = pixels[x, y]
            r, g, b = (p[0], p[1], p[2]) if isinstance(p, tuple) else (p, p, p)
            if (r, g, b) != (255, 255, 255):
                return True
    return False


# ---------------------------------------------------------------------------
# widget annotation with colored rect appearance
# ---------------------------------------------------------------------------


def test_widget_annotation_appearance_paints_pixels() -> None:
    doc, page = _make_doc_with_page()
    # Black-filled rectangle in the appearance content stream — 50x40
    # local-space rectangle that fills the entire bbox.
    content = b"0 0 0 rg\n0 0 50 40 re\nf\n"
    bbox = PDRectangle(0.0, 0.0, 50.0, 40.0)
    appearance = _make_appearance_stream(bbox, content)
    widget = PDAnnotationWidget()
    rect = PDRectangle(20.0, 60.0, 70.0, 100.0)  # 50x40 on the page
    widget.set_rectangle(rect)
    _attach_normal_appearance(widget, appearance)
    page.add_annotation(widget)

    renderer = PDFRenderer(doc)
    image = renderer.render_image(0)
    assert _pixels_in_rect_are_non_white(image, rect, page_height=200.0)


# ---------------------------------------------------------------------------
# rubber stamp annotation
# ---------------------------------------------------------------------------


def test_stamp_annotation_appearance_paints_pixels() -> None:
    doc, page = _make_doc_with_page()
    # Red fill.
    content = b"1 0 0 rg\n0 0 60 30 re\nf\n"
    bbox = PDRectangle(0.0, 0.0, 60.0, 30.0)
    appearance = _make_appearance_stream(bbox, content)
    stamp = PDAnnotationRubberStamp()
    rect = PDRectangle(100.0, 120.0, 160.0, 150.0)
    stamp.set_rectangle(rect)
    _attach_normal_appearance(stamp, appearance)
    page.add_annotation(stamp)

    renderer = PDFRenderer(doc)
    image = renderer.render_image(0)
    assert _pixels_in_rect_are_non_white(image, rect, page_height=200.0)


# ---------------------------------------------------------------------------
# link annotation: no appearance is the common case — must not crash
# ---------------------------------------------------------------------------


def test_link_annotation_without_appearance_does_not_crash() -> None:
    doc, page = _make_doc_with_page()
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(10.0, 10.0, 60.0, 30.0))
    page.add_annotation(link)
    renderer = PDFRenderer(doc)
    # Should walk the annotation list without raising; the link has no
    # Normal Appearance so nothing is painted.
    image = renderer.render_image(0)
    assert image is not None


# ---------------------------------------------------------------------------
# hidden annotation must NOT paint
# ---------------------------------------------------------------------------


def test_hidden_annotation_is_skipped() -> None:
    doc, page = _make_doc_with_page()
    content = b"0 0 0 rg\n0 0 50 40 re\nf\n"
    bbox = PDRectangle(0.0, 0.0, 50.0, 40.0)
    appearance = _make_appearance_stream(bbox, content)
    widget = PDAnnotationWidget()
    rect = PDRectangle(20.0, 60.0, 70.0, 100.0)
    widget.set_rectangle(rect)
    _attach_normal_appearance(widget, appearance)
    widget.set_hidden(True)
    page.add_annotation(widget)

    renderer = PDFRenderer(doc)
    image = renderer.render_image(0)
    # The Hidden flag must skip rendering — the rect area should stay white.
    assert not _pixels_in_rect_are_non_white(image, rect, page_height=200.0)


def test_no_view_annotation_skipped_for_view_destination() -> None:
    doc, page = _make_doc_with_page()
    content = b"0 0 0 rg\n0 0 50 40 re\nf\n"
    bbox = PDRectangle(0.0, 0.0, 50.0, 40.0)
    appearance = _make_appearance_stream(bbox, content)
    widget = PDAnnotationWidget()
    rect = PDRectangle(20.0, 60.0, 70.0, 100.0)
    widget.set_rectangle(rect)
    _attach_normal_appearance(widget, appearance)
    widget.set_no_view(True)
    page.add_annotation(widget)

    renderer = PDFRenderer(doc)
    # Default destination is View; NoView annotations must be skipped.
    image = renderer.render_image(0)
    assert not _pixels_in_rect_are_non_white(image, rect, page_height=200.0)


def test_print_destination_skips_non_printed_annotation() -> None:
    doc, page = _make_doc_with_page()
    content = b"0 0 0 rg\n0 0 50 40 re\nf\n"
    bbox = PDRectangle(0.0, 0.0, 50.0, 40.0)
    appearance = _make_appearance_stream(bbox, content)
    widget = PDAnnotationWidget()
    rect = PDRectangle(20.0, 60.0, 70.0, 100.0)
    widget.set_rectangle(rect)
    _attach_normal_appearance(widget, appearance)
    # /F bit 3 (Print) defaults to false — explicitly leave it false.
    widget.set_printed(False)
    page.add_annotation(widget)

    renderer = PDFRenderer(doc)
    image = renderer.render_image(0, destination="Print")
    # Print destination + Print=false => skipped.
    assert not _pixels_in_rect_are_non_white(image, rect, page_height=200.0)


# ---------------------------------------------------------------------------
# bbox + matrix mapping
# ---------------------------------------------------------------------------


def test_appearance_bbox_scales_to_annotation_rect() -> None:
    """The appearance's local-space content (50x40 rect filling its bbox)
    must scale to a much larger 100x80 annotation rect."""
    doc, page = _make_doc_with_page()
    content = b"0 0 0 rg\n0 0 25 20 re\nf\n"  # bottom-left quadrant
    bbox = PDRectangle(0.0, 0.0, 50.0, 40.0)
    appearance = _make_appearance_stream(bbox, content)
    widget = PDAnnotationWidget()
    # Annotation 4x the size of the appearance bbox.
    rect = PDRectangle(10.0, 10.0, 110.0, 90.0)  # 100x80
    widget.set_rectangle(rect)
    _attach_normal_appearance(widget, appearance)
    page.add_annotation(widget)

    renderer = PDFRenderer(doc)
    image = renderer.render_image(0)
    # The bottom-left quadrant of the annotation rect should be filled
    # (the 25x20 local rect scales to 50x40 in user space at the rect's
    # bottom-left corner — page coords (10,10) → (60,50)).
    fill_area = PDRectangle(10.0, 10.0, 60.0, 50.0)
    assert _pixels_in_rect_are_non_white(image, fill_area, page_height=200.0)


# ---------------------------------------------------------------------------
# AcroFormsBasicFields.pdf — 26 widget annotations
# ---------------------------------------------------------------------------


def test_acroforms_basic_fields_renders_non_blank() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "pdmodel"
        / "interactive"
        / "form"
        / "AcroFormsBasicFields.pdf"
    )
    if not fixture.exists():
        # Skip silently when the fixture isn't present in the workspace.
        import pytest

        pytest.skip(f"fixture not present: {fixture}")
    with PDDocument.load(fixture) as doc:
        renderer = PDFRenderer(doc)
        image = renderer.render_image(0)
    # Walk all pixels and check that some are non-white. Before wave 1385
    # the only content was the page-level form (typically blank) and the
    # 26 widget appearances were dropped, so the entire image was white.
    pixels = image.load()
    w, h = image.size
    found_non_white = False
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            p = pixels[x, y]
            r, g, b = (p[0], p[1], p[2]) if isinstance(p, tuple) else (p, p, p)
            if (r, g, b) != (255, 255, 255):
                found_non_white = True
                break
        if found_non_white:
            break
    assert found_non_white, "AcroFormsBasicFields rendered fully white"
