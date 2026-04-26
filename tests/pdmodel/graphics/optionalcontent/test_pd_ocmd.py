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


# ---------- /VE tree evaluation (PDF 32000-1 §8.11.2.4) ----------


def _ve_and(*operands: object) -> COSArray:
    arr = COSArray([COSName.get_pdf_name("And")])
    for op in operands:
        arr.add(op)  # type: ignore[arg-type]
    return arr


def _ve_or(*operands: object) -> COSArray:
    arr = COSArray([COSName.get_pdf_name("Or")])
    for op in operands:
        arr.add(op)  # type: ignore[arg-type]
    return arr


def _ve_not(operand: object) -> COSArray:
    arr = COSArray([COSName.get_pdf_name("Not")])
    arr.add(operand)  # type: ignore[arg-type]
    return arr


def test_evaluate_visibility_and_two_ocgs() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    cos1 = g1.get_cos_object()
    cos2 = g2.get_cos_object()
    ocmd.set_visibility_expression(_ve_and(cos1, cos2))

    assert ocmd.evaluate_visibility({id(cos1), id(cos2)}) is True
    assert ocmd.evaluate_visibility({id(cos1)}) is False
    assert ocmd.evaluate_visibility({id(cos2)}) is False
    assert ocmd.evaluate_visibility(set()) is False


def test_evaluate_visibility_or_two_ocgs() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    cos1 = g1.get_cos_object()
    cos2 = g2.get_cos_object()
    ocmd.set_visibility_expression(_ve_or(cos1, cos2))

    assert ocmd.evaluate_visibility({id(cos1), id(cos2)}) is True
    assert ocmd.evaluate_visibility({id(cos1)}) is True
    assert ocmd.evaluate_visibility({id(cos2)}) is True
    assert ocmd.evaluate_visibility(set()) is False


def test_evaluate_visibility_not_one_ocg() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    cos1 = g1.get_cos_object()
    ocmd.set_visibility_expression(_ve_not(cos1))

    assert ocmd.evaluate_visibility(set()) is True
    assert ocmd.evaluate_visibility({id(cos1)}) is False


def test_evaluate_visibility_nested_and_or() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    g3 = PDOptionalContentGroup("L3")
    cos1 = g1.get_cos_object()
    cos2 = g2.get_cos_object()
    cos3 = g3.get_cos_object()
    # And(cos1, Or(cos2, cos3))
    ocmd.set_visibility_expression(_ve_and(cos1, _ve_or(cos2, cos3)))

    assert ocmd.evaluate_visibility({id(cos1), id(cos2)}) is True
    assert ocmd.evaluate_visibility({id(cos1), id(cos3)}) is True
    assert ocmd.evaluate_visibility({id(cos1)}) is False
    assert ocmd.evaluate_visibility({id(cos2), id(cos3)}) is False
    assert ocmd.evaluate_visibility(set()) is False


def test_evaluate_visibility_not_requires_one_operand() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    bad = COSArray([COSName.get_pdf_name("Not")])  # zero operands
    ocmd.set_visibility_expression(bad)
    with pytest.raises(ValueError):
        ocmd.evaluate_visibility(set())


def test_evaluate_visibility_unknown_operator_raises() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    bad = COSArray([COSName.get_pdf_name("Xor")])
    ocmd.set_visibility_expression(bad)
    with pytest.raises(ValueError):
        ocmd.evaluate_visibility(set())


def test_is_visible_falls_back_to_p_anyon_when_ve_absent() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    cos1 = g1.get_cos_object()
    cos2 = g2.get_cos_object()
    ocmd.set_o_cgs([g1, g2])
    # default policy is AnyOn
    assert ocmd.get_visibility_policy() == "AnyOn"

    assert ocmd.is_visible({id(cos1)}) is True
    assert ocmd.is_visible({id(cos2)}) is True
    assert ocmd.is_visible(set()) is False


def test_is_visible_p_allon_policy() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    cos1 = g1.get_cos_object()
    cos2 = g2.get_cos_object()
    ocmd.set_o_cgs([g1, g2])
    ocmd.set_visibility_policy("AllOn")

    assert ocmd.is_visible({id(cos1), id(cos2)}) is True
    assert ocmd.is_visible({id(cos1)}) is False


def test_is_visible_prefers_ve_over_p() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    cos1 = g1.get_cos_object()
    cos2 = g2.get_cos_object()
    # /P + /OCGs would say "AnyOn → True if either on"
    ocmd.set_o_cgs([g1, g2])
    ocmd.set_visibility_policy("AnyOn")
    # but /VE demands BOTH on
    ocmd.set_visibility_expression(_ve_and(cos1, cos2))

    assert ocmd.is_visible({id(cos1)}) is False
    assert ocmd.is_visible({id(cos1), id(cos2)}) is True
