from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification import PDSimpleFileSpecification
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)


def test_subtype_constant() -> None:
    assert PDAnnotationFileAttachment.SUB_TYPE == "FileAttachment"


def test_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationFileAttachment()
    assert ann.get_subtype() == "FileAttachment"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_markup() -> None:
    ann = PDAnnotationFileAttachment()
    assert isinstance(ann, PDAnnotationMarkup)


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FileAttachment")  # type: ignore[attr-defined]
    ann = PDAnnotationFileAttachment(d)
    assert ann.get_subtype() == "FileAttachment"
    assert ann.get_cos_object() is d


def test_attachment_name_default_push_pin() -> None:
    assert PDAnnotationFileAttachment().get_attachment_name() == "PushPin"


def test_attachment_name_round_trip() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP)
    assert ann.get_attachment_name() == "Paperclip"


def test_attachment_name_constants() -> None:
    assert PDAnnotationFileAttachment.ATTACHMENT_NAME_GRAPH == "Graph"
    assert PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP == "Paperclip"
    assert PDAnnotationFileAttachment.ATTACHMENT_NAME_PUSH_PIN == "PushPin"
    assert PDAnnotationFileAttachment.ATTACHMENT_NAME_TAG == "Tag"


def test_attachment_name_clear() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name("Tag")
    ann.set_attachment_name(None)
    # Cleared name falls back to the spec default.
    assert ann.get_attachment_name() == "PushPin"


def test_set_file_round_trip() -> None:
    ann = PDAnnotationFileAttachment()
    fs = PDSimpleFileSpecification()
    fs.set_file("attached.pdf")
    ann.set_file(fs)
    got = ann.get_file()
    assert got is not None
    assert got.get_file() == "attached.pdf"


def test_set_file_clear() -> None:
    ann = PDAnnotationFileAttachment()
    fs = PDSimpleFileSpecification()
    fs.set_file("foo.bin")
    ann.set_file(fs)
    ann.set_file(None)
    assert ann.get_file() is None


def test_factory_routes_to_file_attachment() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FileAttachment")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationFileAttachment)


def test_markup_subject_inherited() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_subject("design notes")
    assert ann.get_subject() == "design notes"
