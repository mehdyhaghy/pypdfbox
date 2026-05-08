from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.fdf import (
    FDFAnnotation,
    FDFAnnotationFileAttachment,
    FDFDictionary,
)


def test_default_constructor_stamps_subtype_file_attachment() -> None:
    annotation = FDFAnnotationFileAttachment()

    assert annotation.get_subtype() == "FileAttachment"
    assert annotation.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Type")
    ) is COSName.get_pdf_name("Annot")


def test_existing_subtype_preserved() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Custom"))

    annotation = FDFAnnotationFileAttachment(raw)

    assert annotation.get_subtype() == "Custom"


def test_factory_dispatch_file_attachment() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("FileAttachment"))

    annotation = FDFAnnotation.create(raw)

    assert isinstance(annotation, FDFAnnotationFileAttachment)
    assert annotation.get_cos_object() is raw


def test_dictionary_annotations_dispatch_file_attachment() -> None:
    raw_annotation = COSDictionary()
    raw_annotation.set_item(
        COSName.get_pdf_name("Subtype"),
        COSName.get_pdf_name("FileAttachment"),
    )
    raw_fdf = COSDictionary()
    raw_fdf.set_item(COSName.get_pdf_name("Annots"), COSArray([raw_annotation]))

    annotations = FDFDictionary(raw_fdf).get_annotations()

    assert annotations is not None
    assert len(annotations) == 1
    assert isinstance(annotations[0], FDFAnnotationFileAttachment)
    assert annotations[0].get_cos_object() is raw_annotation
