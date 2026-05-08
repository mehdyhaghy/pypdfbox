from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationText, FDFDictionary


def test_get_annotations_dispatches_known_subtypes() -> None:
    raw_annotation = COSDictionary()
    raw_annotation.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    annots = COSArray()
    annots.add(raw_annotation)

    raw_fdf = COSDictionary()
    raw_fdf.set_item(COSName.get_pdf_name("Annots"), annots)

    annotations = FDFDictionary(raw_fdf).get_annotations()

    assert annotations is not None
    assert len(annotations) == 1
    assert isinstance(annotations[0], FDFAnnotationText)
    assert annotations[0].get_cos_object() is raw_annotation
