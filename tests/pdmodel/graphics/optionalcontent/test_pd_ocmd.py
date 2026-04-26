from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import PDOptionalContentGroup
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)


def test_fresh_has_type_ocmd_and_default_policy() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    cos = ocmd.get_cos_object()
    assert cos.get_dictionary_object(COSName.TYPE) == COSName.get_pdf_name("OCMD")  # type: ignore[attr-defined]
    assert ocmd.get_visibility_policy() == "AnyOn"


def test_visibility_policy_round_trip() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AnyOff")
    assert ocmd.get_visibility_policy() == "AnyOff"

    cos_p = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("P"))
    assert cos_p == COSName.get_pdf_name("AnyOff")


def test_visibility_policy_rejects_invalid() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(ValueError):
        ocmd.set_visibility_policy("Maybe")


def test_set_o_cgs_round_trips_two_groups() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("Layer 1")
    g2 = PDOptionalContentGroup("Layer 2")
    ocmd.set_o_cgs([g1, g2])

    arr = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(arr, COSArray)
    assert arr.size() == 2

    groups = ocmd.get_o_cgs()
    assert len(groups) == 2
    assert all(isinstance(g, PDOptionalContentGroup) for g in groups)
    assert [g.get_name() for g in groups] == ["Layer 1", "Layer 2"]


def test_get_o_cgs_handles_single_dictionary() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g = PDOptionalContentGroup("Solo")
    ocmd.get_cos_object().set_item(
        COSName.get_pdf_name("OCGs"), g.get_cos_object()
    )
    groups = ocmd.get_o_cgs()
    assert len(groups) == 1
    assert groups[0].get_name() == "Solo"


def test_get_o_cgs_empty_when_missing() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_o_cgs() == []


def test_visibility_expression_round_trip() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_visibility_expression() is None

    ve = COSArray([COSName.get_pdf_name("And")])
    ocmd.set_visibility_expression(ve)
    assert ocmd.get_visibility_expression() is ve

    ocmd.set_visibility_expression(None)
    assert ocmd.get_visibility_expression() is None


def test_init_rejects_wrong_type_dictionary() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OCG"))  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        PDOptionalContentMembershipDictionary(raw)


def test_init_accepts_existing_ocmd_dictionary() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OCMD"))  # type: ignore[attr-defined]
    ocmd = PDOptionalContentMembershipDictionary(raw)
    assert ocmd.get_cos_object() is raw
