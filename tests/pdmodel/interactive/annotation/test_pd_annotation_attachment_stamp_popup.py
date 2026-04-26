from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification import PDSimpleFileSpecification
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (
    PDAnnotationFileAttachment,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)


# ---------- PDAnnotationFileAttachment ----------


def test_file_attachment_subtype_constant() -> None:
    assert PDAnnotationFileAttachment.SUB_TYPE == "FileAttachment"


def test_file_attachment_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationFileAttachment()
    assert ann.get_subtype() == "FileAttachment"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_file_attachment_set_file_round_trip() -> None:
    ann = PDAnnotationFileAttachment()
    fs = PDSimpleFileSpecification()
    fs.set_file("attached.pdf")
    ann.set_file(fs)
    got = ann.get_file()
    assert got is not None
    assert got.get_file() == "attached.pdf"


def test_file_attachment_attachment_name_default_push_pin() -> None:
    ann = PDAnnotationFileAttachment()
    assert ann.get_attachment_name() == "PushPin"


def test_file_attachment_attachment_name_round_trip() -> None:
    ann = PDAnnotationFileAttachment()
    ann.set_attachment_name(PDAnnotationFileAttachment.ATTACHMENT_NAME_PAPERCLIP)
    assert ann.get_attachment_name() == "Paperclip"


def test_file_attachment_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FileAttachment")  # type: ignore[attr-defined]
    ann = PDAnnotationFileAttachment(d)
    assert ann.get_subtype() == "FileAttachment"


# ---------- PDAnnotationRubberStamp ----------


def test_rubber_stamp_subtype_constant() -> None:
    assert PDAnnotationRubberStamp.SUB_TYPE == "Stamp"


def test_rubber_stamp_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationRubberStamp()
    assert ann.get_subtype() == "Stamp"


def test_rubber_stamp_name_default_draft() -> None:
    ann = PDAnnotationRubberStamp()
    assert ann.get_name() == "Draft"


def test_rubber_stamp_name_round_trip() -> None:
    ann = PDAnnotationRubberStamp()
    ann.set_name(PDAnnotationRubberStamp.NAME_APPROVED)
    assert ann.get_name() == "Approved"


def test_rubber_stamp_name_constants_exist() -> None:
    expected = {
        "NAME_APPROVED": "Approved",
        "NAME_AS_IS": "AsIs",
        "NAME_CONFIDENTIAL": "Confidential",
        "NAME_DEPARTMENTAL": "Departmental",
        "NAME_DRAFT": "Draft",
        "NAME_EXPERIMENTAL": "Experimental",
        "NAME_EXPIRED": "Expired",
        "NAME_FINAL": "Final",
        "NAME_FOR_COMMENT": "ForComment",
        "NAME_FOR_PUBLIC_RELEASE": "ForPublicRelease",
        "NAME_NOT_APPROVED": "NotApproved",
        "NAME_NOT_FOR_PUBLIC_RELEASE": "NotForPublicRelease",
        "NAME_SOLD": "Sold",
        "NAME_TOP_SECRET": "TopSecret",
    }
    for attr, value in expected.items():
        assert getattr(PDAnnotationRubberStamp, attr) == value


# ---------- PDAnnotationPopup ----------


def test_popup_subtype_constant() -> None:
    assert PDAnnotationPopup.SUB_TYPE == "Popup"


def test_popup_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationPopup()
    assert ann.get_subtype() == "Popup"


def test_popup_open_default_false() -> None:
    ann = PDAnnotationPopup()
    assert ann.get_open() is False


def test_popup_open_round_trip() -> None:
    ann = PDAnnotationPopup()
    ann.set_open(True)
    assert ann.get_open() is True
    ann.set_open(False)
    assert ann.get_open() is False


def test_popup_parent_default_none() -> None:
    ann = PDAnnotationPopup()
    assert ann.get_parent() is None


def test_popup_parent_round_trip() -> None:
    ann = PDAnnotationPopup()
    parent_dict = COSDictionary()
    parent_dict.set_name(COSName.SUBTYPE, "Text")  # type: ignore[attr-defined]
    ann.set_parent(parent_dict)
    got = ann.get_parent()
    assert got is parent_dict


def test_popup_parent_clear() -> None:
    ann = PDAnnotationPopup()
    ann.set_parent(COSDictionary())
    ann.set_parent(None)
    assert ann.get_parent() is None
