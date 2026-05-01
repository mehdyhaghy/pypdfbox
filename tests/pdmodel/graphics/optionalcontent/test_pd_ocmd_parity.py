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


# ---------- /Type accessor (PDFBox getType parity) ----------


def test_get_type_returns_ocmd_for_fresh_dict() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_type() == COSName.get_pdf_name("OCMD")


def test_get_type_returns_ocmd_when_existing_dict_round_tripped() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g = PDOptionalContentGroup("Layer")
    ocmd.set_ocgs([g])
    # round-trip via wrapping the same dict again
    again = PDOptionalContentMembershipDictionary(ocmd.get_cos_object())
    assert again.get_type() == COSName.get_pdf_name("OCMD")


# ---------- get_visibility_policy_name (upstream COSName return) ----------


def test_get_visibility_policy_name_default_any_on() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_visibility_policy_name() == COSName.get_pdf_name("AnyOn")


def test_get_visibility_policy_name_after_set() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AllOff")
    assert ocmd.get_visibility_policy_name() == COSName.get_pdf_name("AllOff")


def test_set_visibility_policy_name_round_trips_cos_name() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy_name(COSName.get_pdf_name("AnyOff"))
    assert ocmd.get_visibility_policy() == "AnyOff"
    assert ocmd.get_visibility_policy_name() == COSName.get_pdf_name("AnyOff")


def test_set_visibility_policy_name_accepts_arbitrary_cos_name() -> None:
    # Upstream setVisibilityPolicy(COSName) does not validate; mirror that.
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy_name(COSName.get_pdf_name("Bogus"))
    raw = ocmd.get_cos_object().get_dictionary_object(COSName.get_pdf_name("P"))
    assert raw == COSName.get_pdf_name("Bogus")


def test_set_visibility_policy_name_rejects_non_cos_name() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(TypeError):
        ocmd.set_visibility_policy_name("AllOn")  # type: ignore[arg-type]


# ---------- get_ocgs_property_list (upstream List<PDPropertyList> return) ----


def test_get_ocgs_property_list_default_empty() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_ocgs_property_list() == []


def test_get_ocgs_property_list_returns_ocgs() -> None:
    from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList

    ocmd = PDOptionalContentMembershipDictionary()
    g1 = PDOptionalContentGroup("L1")
    g2 = PDOptionalContentGroup("L2")
    ocmd.set_ocgs([g1, g2])

    plist = ocmd.get_ocgs_property_list()
    assert len(plist) == 2
    assert all(isinstance(p, PDPropertyList) for p in plist)


def test_get_ocgs_property_list_includes_nested_ocmd() -> None:
    """Upstream returns ``List<PDPropertyList>`` so nested OCMDs surface;
    :meth:`get_ocgs` filters them out, but the property-list flavour does not.
    """
    outer = PDOptionalContentMembershipDictionary()
    g = PDOptionalContentGroup("Real")
    nested = PDOptionalContentMembershipDictionary()
    arr = COSArray()
    arr.add(g.get_cos_object())
    arr.add(nested.get_cos_object())
    outer.get_cos_object().set_item(COSName.get_pdf_name("OCGs"), arr)

    plist = outer.get_ocgs_property_list()
    # Both entries surface; nested OCMD makes it through.
    assert len(plist) == 2
    assert any(
        isinstance(p, PDOptionalContentMembershipDictionary) for p in plist
    )
    # ``get_ocgs`` continues to filter to OCG only.
    assert len(outer.get_ocgs()) == 1


def test_get_ocgs_property_list_handles_single_dictionary_entry() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    g = PDOptionalContentGroup("Solo")
    ocmd.get_cos_object().set_item(
        COSName.get_pdf_name("OCGs"), g.get_cos_object()
    )
    plist = ocmd.get_ocgs_property_list()
    assert len(plist) == 1
    assert plist[0].get_cos_object() is g.get_cos_object()
