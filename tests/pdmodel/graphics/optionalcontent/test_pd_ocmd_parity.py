from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import PDOptionalContentGroup
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)


# ---------- /OCGs (upstream-named accessors) ----------


def test_get_ocgs_default_empty() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_ocgs() == []


def test_set_ocgs_round_trips_list() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("Layer 1")
    g2 = PDOptionalContentGroup("Layer 2")
    ocmd.set_ocgs([g1, g2])

    arr = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(arr, COSArray)
    assert arr.size() == 2

    groups = ocmd.get_ocgs()
    assert [g.get_name() for g in groups] == ["Layer 1", "Layer 2"]


def test_set_ocgs_single_group_round_trips_as_dict() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    solo = PDOptionalContentGroup("Solo")
    ocmd.set_ocgs(solo)

    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    # /OCGs may legally be a single OCG dictionary (PDF 32000-1 §8.11.2.2).
    assert raw is solo.get_cos_object()

    groups = ocmd.get_ocgs()
    assert len(groups) == 1
    assert groups[0].get_name() == "Solo"


def test_set_ocgs_single_cos_dictionary_round_trips() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g = PDOptionalContentGroup("Direct")
    ocmd.set_ocgs(g.get_cos_object())

    groups = ocmd.get_ocgs()
    assert len(groups) == 1
    assert groups[0].get_name() == "Direct"


def test_set_ocgs_rejects_invalid_type() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(TypeError):
        ocmd.set_ocgs("not-an-ocg")  # type: ignore[arg-type]


# ---------- /P (visibility policy constants) ----------


def test_get_visibility_policy_default_any_on() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_visibility_policy() == "AnyOn"
    assert (
        PDOptionalContentMembershipDictionary.VISIBILITY_POLICY_ANY_ON == "AnyOn"
    )


@pytest.mark.parametrize(
    "constant,expected",
    [
        (PDOptionalContentMembershipDictionary.VISIBILITY_POLICY_ALL_ON, "AllOn"),
        (PDOptionalContentMembershipDictionary.VISIBILITY_POLICY_ANY_ON, "AnyOn"),
        (PDOptionalContentMembershipDictionary.VISIBILITY_POLICY_ANY_OFF, "AnyOff"),
        (PDOptionalContentMembershipDictionary.VISIBILITY_POLICY_ALL_OFF, "AllOff"),
    ],
)
def test_visibility_policy_round_trip_for_each_constant(
    constant: str, expected: str
) -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy(constant)
    assert ocmd.get_visibility_policy() == expected

    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("P"))
    assert raw == COSName.get_pdf_name(expected)


# ---------- /VE (visibility expression: parser path only) ----------


def test_get_visibility_expression_default_none() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_visibility_expression() is None


def test_set_visibility_expression_round_trips_raw_cos_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    ve = COSArray(
        [
            COSName.get_pdf_name("And"),
            g1.get_cos_object(),
            g2.get_cos_object(),
        ]
    )
    ocmd.set_visibility_expression(ve)

    fetched = ocmd.get_visibility_expression()
    assert fetched is ve
    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("VE"))
    assert raw is ve


def test_set_visibility_expression_none_removes_entry() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_expression(COSArray([COSName.get_pdf_name("Or")]))
    assert ocmd.get_visibility_expression() is not None

    ocmd.set_visibility_expression(None)
    assert ocmd.get_visibility_expression() is None
    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("VE"))
    assert raw is None
