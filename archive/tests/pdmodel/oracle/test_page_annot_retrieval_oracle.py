"""Live PDFBox parity for ``PDPage.get_annotations()`` factory dispatch.

The ``PageAnnotRetrievalProbe`` Java probe builds a single-page document with a
deterministic mix of annotation subtypes on ``/Annots`` (Link, Text, Square,
Circle, Widget, Line, Popup, Highlight, plus an unknown subtype and a
``/Subtype``-less dictionary), saves it to bytes, reloads it (so the entries
become indirect references), and emits — in ``/Annots`` array order — each
returned annotation's concrete class simple-name, ``/Subtype`` and ``/Rect``
(four nearest-int corners). It also emits the result of the
``getAnnotations(AnnotationFilter)`` overload filtering to widgets only.

This test rebuilds the byte-identical document with pypdfbox, parses it back,
and asserts ``get_annotations()`` matches the Java dump exactly: the subclass
dispatch by ``/Subtype``, the array-order preservation across direct/indirect
entries, the typed-``PDRectangle`` corners, and the ``AnnotationFilter``
overload. The Python class names mirror upstream's exactly, so the ``cls``
field is directly comparable.
"""

from __future__ import annotations

import json
from io import BytesIO

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_pdf() -> bytes:
    """Build the same document the Java probe builds and save it to bytes.

    PDFBox's ``PDRectangle(x, y, w, h)`` constructor treats the args as
    (lower-left-x, lower-left-y, width, height); pypdfbox's ``PDRectangle``
    takes the four corners directly, so we precompute upper-right = ll + size
    to land the identical /Rect arrays.
    """
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 595, 842))
        doc.add_page(page)

        annots = COSArray()

        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(10, 20, 110, 50))
        annots.add(link.get_cos_object())

        text = PDAnnotationText()
        text.set_rectangle(PDRectangle(50, 60, 68, 80))
        annots.add(text.get_cos_object())

        square = PDAnnotationSquare()
        square.set_rectangle(PDRectangle(120, 200, 200, 240))
        annots.add(square.get_cos_object())

        circle = PDAnnotationCircle()
        circle.set_rectangle(PDRectangle(300, 400, 360, 460))
        annots.add(circle.get_cos_object())

        widget = PDAnnotationWidget()
        widget.set_rectangle(PDRectangle(15, 700, 215, 730))
        annots.add(widget.get_cos_object())

        line = PDAnnotationLine()
        line.set_rectangle(PDRectangle(0, 0, 595, 842))
        annots.add(line.get_cos_object())

        popup = PDAnnotationPopup()
        popup.set_rectangle(PDRectangle(400, 500, 550, 600))
        annots.add(popup.get_cos_object())

        hl = PDAnnotationHighlight()
        hl.set_rectangle(PDRectangle(200, 210, 440, 435))
        annots.add(hl.get_cos_object())

        # Unknown subtype — factory falls back to PDAnnotationUnknown.
        unknown = COSDictionary()
        unknown.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
        unknown.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Frobnicate")
        )
        u_rect = COSArray()
        for v in (1, 2, 3, 4):
            u_rect.add(COSInteger.get(v))
        unknown.set_item(COSName.get_pdf_name("Rect"), u_rect)
        annots.add(unknown)

        # Subtype-less dict — still PDAnnotationUnknown.
        no_sub = COSDictionary()
        no_sub.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
        annots.add(no_sub)

        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


def _annot_to_dict(annot) -> dict:
    rect = annot.get_rectangle()
    if rect is None:
        rect_json = None
    else:
        rect_json = [
            round(rect.get_lower_left_x()),
            round(rect.get_lower_left_y()),
            round(rect.get_upper_right_x()),
            round(rect.get_upper_right_y()),
        ]
    return {
        "cls": type(annot).__name__,
        "subtype": annot.get_subtype(),
        "rect": rect_json,
    }


@requires_oracle
def test_page_annotation_retrieval_matches_pdfbox() -> None:
    pdf = _build_pdf()
    java_dump = json.loads(run_probe_text("PageAnnotRetrievalProbe"))

    doc = PDDocument.load(pdf)
    try:
        page = doc.get_page(0)
        py_all = [_annot_to_dict(a) for a in page.get_annotations()]
        py_widgets = [
            _annot_to_dict(a)
            for a in page.get_annotations(
                lambda a: isinstance(a, PDAnnotationWidget)
            )
        ]
    finally:
        doc.close()

    py_dump = {"all": py_all, "widgets": py_widgets}

    assert py_dump == java_dump, (
        "annotation retrieval divergence:\n"
        f"  java: {json.dumps(java_dump, sort_keys=True)}\n"
        f"  py:   {json.dumps(py_dump, sort_keys=True)}"
    )
