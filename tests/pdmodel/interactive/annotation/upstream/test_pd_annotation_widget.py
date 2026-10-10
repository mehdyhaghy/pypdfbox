"""Companion to ``test_pd_annotation.py``.

Upstream PDFBox 3.0.8 does not ship a dedicated ``PDAnnotationWidgetTest``
(the 3.0 branch adds one for PDFBOX-6270, ported at the bottom of this file);
the widget construction tests live in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationTest.java``
(see ``test_pd_annotation.py`` in this directory).

This module supplements that with a minimal upstream-style smoke check
that ``PDAnnotation.create()`` dispatches a ``/Subtype /Widget`` dict to
:class:`PDAnnotationWidget` rather than falling through to
:class:`PDAnnotationUnknown` — the regression that prompted porting the
class in this wave.
"""

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationUnknown,
    PDAnnotationWidget,
)


def test_factory_dispatches_widget_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Type"), "Annot")
    d.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    annotation = PDAnnotation.create(d)
    assert isinstance(annotation, PDAnnotationWidget)
    assert not isinstance(annotation, PDAnnotationUnknown)
    assert annotation.get_subtype() == PDAnnotationWidget.SUB_TYPE


# Upstream: PDAnnotationWidgetTest.testDontDirtyOnConstruction (PDFBOX-6270,
# 3.0 branch, unreleased 3.0.9): a correct annotation must not get dirty.
def test_dont_dirty_on_construction() -> None:
    from pypdfbox.cos import COSDocumentState

    # setup: build a COSDictionary that will accept update flags
    d = COSDictionary()
    state = COSDocumentState()
    state.set_parsing(False)
    d.get_update_state().set_origin_document_state(state)

    # set subtype correctly
    # (this stands in for an annotation widget that was parsed from an existing document)
    d.set_item(COSName.TYPE, COSName.get_pdf_name("Annot"))
    d.set_name(COSName.SUBTYPE, PDAnnotationWidget.SUB_TYPE)
    d.set_needs_to_be_updated(False)
    assert not d.is_needs_to_be_updated()

    # construct a PDAnnotationWidget wrapper around it
    PDAnnotationWidget(d)

    assert not d.is_needs_to_be_updated()
