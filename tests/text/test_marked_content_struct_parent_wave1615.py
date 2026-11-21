"""Wave 1615 — PDFBOX-6303 / 6311 / 6338 hand-written tests.

* PDFBOX-6303: ``PDFMarkedContentExtractor`` records the ``/StructParents``
  key of the page / form XObject on every ``PDMarkedContent`` and descends
  into form XObjects on ``Do`` (reporting the XObject via ``xobject``).
* PDFBOX-6311: only the span that set ``/ActualText`` ends it; nested
  ``/ActualText`` is ignored.
* PDFBOX-6338: unclosed marked content does not leak across pages.
"""
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text import (
    PDFMarkedContentExtractor,
    PDFTextStripper,
    PDFTextStripperByArea,
    TextPosition,
)


def _page(doc: PDDocument, content: bytes, resources: PDResources | None = None) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    if resources is not None:
        page.set_resources(resources)
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _form(body: bytes, *, group: bool = False) -> PDFormXObject:
    stream = COSStream()
    stream.set_data(body)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    stream.set_item(
        COSName.get_pdf_name("BBox"),
        COSArray([COSInteger.get(v) for v in (0, 0, 200, 50)]),
    )
    if group:
        g = COSDictionary()
        g.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
        stream.set_item(COSName.get_pdf_name("Group"), g)
    return PDFormXObject(stream)


def _text_of(mc: PDMarkedContent) -> str:
    return "".join(c.get_unicode() for c in mc.get_contents() if isinstance(c, TextPosition))


# ---------- PDFBOX-6303 ----------


def test_page_struct_parents_recorded() -> None:
    doc = PDDocument()
    try:
        page = _page(doc, b"/P <</MCID 0>> BDC BT /F0 12 Tf 10 700 Td (a) Tj ET EMC")
        page.set_struct_parents(4)
        e = PDFMarkedContentExtractor()
        e.process_page(page)
        [mc] = e.get_marked_contents()
        assert mc.get_struct_parent() == 4
    finally:
        doc.close()


def test_page_without_struct_parents_reports_minus_one() -> None:
    doc = PDDocument()
    try:
        page = _page(doc, b"/P BMC BT /F0 12 Tf 10 700 Td (a) Tj ET EMC")
        e = PDFMarkedContentExtractor()
        e.process_page(page)
        assert [mc.get_struct_parent() for mc in e.get_marked_contents()] == [-1]
    finally:
        doc.close()


def _form_page(doc: PDDocument, *, group: bool) -> tuple[PDPage, PDFormXObject]:
    form = _form(b"/Span <</MCID 1>> BDC BT /F0 12 Tf 10 20 Td (In) Tj ET EMC", group=group)
    form.set_struct_parents(9)
    resources = PDResources()
    key = resources.add_x_object(form).get_name().encode("ascii")
    page = _page(
        doc,
        b"/P <</MCID 0>> BDC /" + key + b" Do EMC /P <</MCID 2>> BDC EMC",
        resources,
    )
    page.set_struct_parents(4)
    return page, form


def test_form_struct_parents_recorded_and_restored() -> None:
    for group in (False, True):
        doc = PDDocument()
        try:
            page, form = _form_page(doc, group=group)
            e = PDFMarkedContentExtractor()
            e.process_page(page)
            outer, after = e.get_marked_contents()
            assert outer.get_struct_parent() == 4
            assert after.get_struct_parent() == 4
            # Upstream DrawObject reports the XObject before descending.
            xobj, inner = outer.get_contents()
            assert xobj.get_cos_object() is form.get_cos_object()
            assert isinstance(inner, PDMarkedContent)
            assert inner.get_struct_parent() == 9
            assert _text_of(inner) == "In"
        finally:
            doc.close()


# ---------- PDFBOX-6311 ----------


def _strip(doc: PDDocument) -> str:
    s = PDFTextStripper()
    s.set_line_separator("\n")
    s.set_page_end("\n")
    return s.get_text(doc)


def test_nested_span_without_actual_text_keeps_replacement() -> None:
    doc = PDDocument()
    try:
        _page(
            doc,
            b"BT /F0 12 Tf 50 700 Td /Span <</ActualText (XYZ)>> BDC "
            b"/Foo BMC (abc) Tj EMC (def) Tj EMC (ghi) Tj ET",
        )
        assert _strip(doc) == "XYZghi\n"
    finally:
        doc.close()


def test_nested_actual_text_ignored_and_outer_end_resets() -> None:
    doc = PDDocument()
    try:
        _page(
            doc,
            b"BT /F0 12 Tf 50 700 Td /Span <</ActualText (X)>> BDC (a) Tj "
            b"/Span <</ActualText (Y)>> BDC (b) Tj EMC (c) Tj EMC (d) Tj ET",
        )
        assert _strip(doc) == "Xd\n"
    finally:
        doc.close()


# ---------- PDFBOX-6338 ----------


def test_process_page_resets_unclosed_actual_text() -> None:
    doc = PDDocument()
    try:
        p1 = _page(doc, b"BT /F0 12 Tf 50 700 Td /Span <</ActualText (X)>> BDC (one) Tj ET")
        p2 = _page(doc, b"BT /F0 12 Tf 50 700 Td (two) Tj ET")
        s = PDFTextStripper()
        assert "X" in s.process_page(p1)
        assert "two" in s.process_page(p2)
        assert s._marked_content_stack == []
    finally:
        doc.close()


def test_by_area_resets_unclosed_actual_text() -> None:
    doc = PDDocument()
    try:
        p1 = _page(doc, b"BT /F0 12 Tf 50 700 Td /Span <</ActualText (X)>> BDC (one) Tj ET")
        p2 = _page(doc, b"BT /F0 12 Tf 50 700 Td (two) Tj ET")
        s = PDFTextStripperByArea()
        s.add_region("r", PDRectangle.from_xywh(0, 0, 612, 792))
        s.extract_regions(p1)
        assert "X" in s.get_text_for_region("r")
        s.extract_regions(p2)
        assert "two" in s.get_text_for_region("r")
    finally:
        doc.close()
