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


# ---------- has_name (presence check) ----------


def test_stamp_has_name_absent_on_default_construction() -> None:
    # Default construction must not write /Name; spec default is implicit.
    ann = PDAnnotationStamp()
    assert ann.has_name() is False
    # ...but get_name() still resolves to Draft.
    assert ann.get_name() == "Draft"


def test_stamp_has_name_after_set() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_APPROVED)
    assert ann.has_name() is True


def test_stamp_has_name_after_set_then_clear() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_FINAL)
    assert ann.has_name() is True
    ann.set_name(None)
    assert ann.has_name() is False


def test_stamp_has_name_explicit_draft_distinguished_from_absent() -> None:
    # Setting /Name = "Draft" explicitly is distinguishable from absent /Name,
    # even though get_name() returns "Draft" in both cases.
    ann_default = PDAnnotationStamp()
    ann_explicit = PDAnnotationStamp()
    ann_explicit.set_name(PDAnnotationStamp.NAME_DRAFT)
    assert ann_default.has_name() is False
    assert ann_explicit.has_name() is True
    # But the resolved name is identical.
    assert ann_default.get_name() == ann_explicit.get_name() == "Draft"


# ---------- is_default_name ----------


def test_stamp_is_default_name_implicit() -> None:
    ann = PDAnnotationStamp()
    assert ann.is_default_name() is True


def test_stamp_is_default_name_explicit_draft() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_DRAFT)
    assert ann.is_default_name() is True


def test_stamp_is_default_name_other_icon() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_APPROVED)
    assert ann.is_default_name() is False


def test_stamp_is_default_name_case_sensitive() -> None:
    ann = PDAnnotationStamp()
    ann.set_name("draft")  # lower-case is not the spec default
    assert ann.is_default_name() is False


# ---------- per-icon predicates ----------


def test_stamp_is_draft_aliases_default_name() -> None:
    ann = PDAnnotationStamp()
    assert ann.is_draft() is True
    ann.set_name(PDAnnotationStamp.NAME_APPROVED)
    assert ann.is_draft() is False


def test_stamp_is_approved_predicate() -> None:
    ann = PDAnnotationStamp()
    assert ann.is_approved() is False
    ann.set_name(PDAnnotationStamp.NAME_APPROVED)
    assert ann.is_approved() is True


def test_stamp_is_confidential_predicate() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_CONFIDENTIAL)
    assert ann.is_confidential() is True
    ann.set_name(PDAnnotationStamp.NAME_DRAFT)
    assert ann.is_confidential() is False


def test_stamp_is_final_predicate() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_FINAL)
    assert ann.is_final() is True
    ann.set_name(PDAnnotationStamp.NAME_APPROVED)
    assert ann.is_final() is False


def test_stamp_is_top_secret_predicate() -> None:
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_TOP_SECRET)
    assert ann.is_top_secret() is True
    ann.set_name(PDAnnotationStamp.NAME_DRAFT)
    assert ann.is_top_secret() is False


def test_stamp_per_icon_predicates_mutually_exclusive() -> None:
    # At most one of the per-icon predicates may be True at once.
    ann = PDAnnotationStamp()
    ann.set_name(PDAnnotationStamp.NAME_CONFIDENTIAL)
    flags = [
        ann.is_approved(),
        ann.is_confidential(),
        ann.is_draft(),
        ann.is_final(),
        ann.is_top_secret(),
    ]
    assert sum(flags) == 1
    assert ann.is_confidential() is True


def test_stamp_per_icon_predicates_all_false_for_custom() -> None:
    ann = PDAnnotationStamp()
    ann.set_name("CompanyLogo")
    assert ann.is_approved() is False
    assert ann.is_confidential() is False
    assert ann.is_draft() is False
    assert ann.is_final() is False
    assert ann.is_top_secret() is False
    assert ann.is_default_name() is False
    assert ann.is_standard_name() is False
