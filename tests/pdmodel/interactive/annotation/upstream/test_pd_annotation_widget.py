"""Companion to ``test_pd_annotation.py``.

Upstream PDFBox 3.0.x does not ship a dedicated ``PDAnnotationWidgetTest``;
the widget construction tests live in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/annotation/PDAnnotationTest.java``
(see ``test_pd_annotation.py`` in this directory).

This module supplements that with a minimal upstream-style smoke check
that ``PDAnnotation.create()`` dispatches a ``/Subtype /Widget`` dict to
:class:`PDAnnotationWidget` rather than falling through to
:class:`PDAnnotationUnknown` — the regression that prompted porting the
class in this wave.
"""

from __future__ import annotations

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
