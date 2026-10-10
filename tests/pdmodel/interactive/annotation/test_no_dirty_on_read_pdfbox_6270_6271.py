"""PDFBOX-6270 / PDFBOX-6271 (3.0 branch, unreleased 3.0.9).

Reading the annotations of a page from a loaded document, and the normal
appearance stream of a widget, must not mark the parsed objects as needing
an update, so an incremental save does not rewrite them.
"""

import io

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _widget_pdf() -> bytes:
    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    widget = PDAnnotationWidget()
    widget.set_rectangle(PDRectangle(10, 10, 50, 20))
    appearance = PDAppearanceStream(doc)
    appearance.set_b_box(PDRectangle(0, 0, 50, 20))
    ap_dict = PDAppearanceDictionary()
    ap_dict.set_normal_appearance(appearance)
    widget.set_appearance(ap_dict)
    page.set_annotations([widget])
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_reading_annotations_and_appearance_does_not_dirty() -> None:
    data = _widget_pdf()
    with PDDocument.load(data) as doc:
        annotation = doc.get_page(0).get_annotations()[0]
        assert isinstance(annotation, PDAnnotationWidget)
        assert not annotation.get_cos_object().is_needs_to_be_updated()

        stream = annotation.get_normal_appearance_stream()
        assert stream is not None
        assert not stream.get_cos_object().is_needs_to_be_updated()


def test_incremental_save_does_not_rewrite_annotation_or_appearance() -> None:
    data = _widget_pdf()
    with PDDocument.load(data) as doc:
        annotation = doc.get_page(0).get_annotations()[0]
        annotation.get_normal_appearance_stream()
        out = io.BytesIO()
        doc.save_incremental(out)
    increment = out.getvalue()[len(data):]
    assert b"/Widget" not in increment
    assert b"/Form" not in increment


def test_widget_with_wrong_subtype_is_still_stamped() -> None:
    from pypdfbox.cos import COSDictionary

    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Link")
    PDAnnotationWidget(d)
    assert d.get_name_as_string(COSName.SUBTYPE) == "Widget"


def test_form_xobject_missing_names_are_still_stamped() -> None:
    s = COSStream()
    PDFormXObject(s)
    assert s.get_item(COSName.TYPE) == COSName.XOBJECT
    assert s.get_item(COSName.SUBTYPE) == COSName.FORM
