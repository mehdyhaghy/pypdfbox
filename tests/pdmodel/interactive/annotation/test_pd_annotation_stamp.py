from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_stamp import (
    PDAnnotationStamp,
)


def test_stamp_subtype_constant() -> None:
    assert PDAnnotationStamp.SUB_TYPE == "Stamp"


def test_stamp_inherits_markup() -> None:
    assert issubclass(PDAnnotationStamp, PDAnnotationMarkup)


def test_stamp_default_constructor_sets_type_and_subtype() -> None:
    ann = PDAnnotationStamp()
    cos = ann.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]
    assert ann.get_subtype() == "Stamp"


def test_stamp_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Stamp")  # type: ignore[attr-defined]
    ann = PDAnnotationStamp(d)
    assert ann.get_subtype() == "Stamp"
    assert ann.get_cos_object() is d


def test_stamp_name_default_draft() -> None:
    ann = PDAnnotationStamp()
    assert ann.get_name() == "Draft"
    assert ann.get_name() == PDAnnotationStamp.NAME_DRAFT


def test_stamp_name_round_trip() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_APPROVED)
    assert ann.get_name() == "Approved"
    ann.set_name(PDAnnotationStamp.NAME_TOP_SECRET)
    assert ann.get_name() == "TopSecret"


def test_stamp_name_clear_returns_to_default() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_FINAL)
    ann.set_name(None)
    assert ann.get_name() == "Draft"


def test_stamp_name_constants_match_spec() -> None:
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
        assert getattr(PDAnnotationStamp, attr) == value


def test_stamp_inherits_markup_creation_date() -> None:
    ann = PDAnnotationStamp()
    assert ann.get_creation_date() is None
    ann.set_creation_date("D:20260101120000Z00'00'")
    assert ann.get_creation_date() == "D:20260101120000Z00'00'"


def test_stamp_inherits_markup_subject() -> None:
    ann = PDAnnotationStamp()
    ann.set_subject("Approval pending")
    assert ann.get_subject() == "Approval pending"


def test_stamp_inherits_markup_constant_opacity_default() -> None:
    ann = PDAnnotationStamp()
    assert ann.get_constant_opacity() == 1.0
    ann.set_constant_opacity(0.5)
    assert ann.get_constant_opacity() == 0.5


def test_stamp_factory_routes_via_rubber_stamp() -> None:
    # /Subtype /Stamp currently dispatches to legacy PDAnnotationRubberStamp.
    # PDAnnotationStamp can still be constructed directly and round-trips.
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Stamp")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    # Should be a /Stamp annotation, not Unknown
    assert ann.get_subtype() == "Stamp"


# ---------- STANDARD_NAMES + is_standard_name ----------


def test_stamp_standard_names_set_size_and_contents() -> None:
    # PDF 32000-1:2008 Table 183 enumerates exactly 14 standard icons.
    assert len(PDAnnotationStamp.STANDARD_NAMES) == 14
    expected = {
        "Approved",
        "AsIs",
        "Confidential",
        "Departmental",
        "Draft",
        "Experimental",
        "Expired",
        "Final",
        "ForComment",
        "ForPublicRelease",
        "NotApproved",
        "NotForPublicRelease",
        "Sold",
        "TopSecret",
    }
    assert expected == PDAnnotationStamp.STANDARD_NAMES


def test_stamp_standard_names_is_frozenset() -> None:
    assert isinstance(PDAnnotationStamp.STANDARD_NAMES, frozenset)


def test_stamp_is_standard_name_default_draft() -> None:
    # Spec default (no /Name entry) is "Draft" — a standard icon.
    ann = PDAnnotationStamp()
    assert ann.is_standard_name() is True


def test_stamp_is_standard_name_each_constant() -> None:
    ann = PDAnnotationStamp()
    for name in PDAnnotationStamp.STANDARD_NAMES:
        ann.set_name(name)
        assert ann.is_standard_name() is True, f"{name} should be standard"


def test_stamp_is_standard_name_rejects_custom() -> None:
    ann = PDAnnotationStamp()
    ann.set_name("CompanyLogo")
    assert ann.is_standard_name() is False
    ann.set_name("approved")  # case-sensitive
    assert ann.is_standard_name() is False


def test_stamp_is_standard_name_after_clear_returns_true() -> None:
    ann = PDAnnotationStamp()
    ann.set_name("Custom")
    assert ann.is_standard_name() is False
    ann.set_name(None)  # falls back to NAME_DRAFT
    assert ann.is_standard_name() is True
