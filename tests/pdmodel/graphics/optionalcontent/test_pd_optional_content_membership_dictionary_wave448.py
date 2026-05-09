from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import PDOptionalContentGroup
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    MembershipDictionaryVisibilityPolicy,
    PDOptionalContentMembershipDictionary,
)

OCGS = COSName.get_pdf_name("OCGs")
P = COSName.get_pdf_name("P")
TYPE = COSName.TYPE
VE = COSName.get_pdf_name("VE")


def _group(name: str) -> PDOptionalContentGroup:
    return PDOptionalContentGroup(name)


def test_constructor_sets_missing_type_and_rejects_wrong_type() -> None:
    raw = COSDictionary()

    ocmd = PDOptionalContentMembershipDictionary(raw)
    assert ocmd.get_cos_object() is raw
    assert raw.get_dictionary_object(TYPE) == COSName.get_pdf_name("OCMD")

    wrong = COSDictionary()
    wrong.set_item(TYPE, COSName.get_pdf_name("OCG"))
    with pytest.raises(ValueError, match="not of type"):
        PDOptionalContentMembershipDictionary(wrong)


def test_get_type_is_defensive_when_type_key_is_stripped() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.get_cos_object().remove_item(TYPE)

    assert ocmd.get_type() == COSName.get_pdf_name("OCMD")


def test_ocgs_readers_ignore_non_ocg_and_non_dictionary_entries() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    group = _group("visible")
    bare_property_list = COSDictionary()
    arr = COSArray(
        [
            group.get_cos_object(),
            bare_property_list,
            COSBoolean.TRUE,
        ]
    )
    ocmd.get_cos_object().set_item(OCGS, arr)

    assert [g.get_cos_object() for g in ocmd.get_ocgs()] == [
        group.get_cos_object()
    ]

    property_lists = ocmd.get_ocgs_property_list()
    assert [p.get_cos_object() for p in property_lists] == [
        group.get_cos_object(),
        bare_property_list,
    ]


def test_single_non_ocg_dictionary_is_not_returned_as_group() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    raw = COSDictionary()
    ocmd.get_cos_object().set_item(OCGS, raw)

    assert ocmd.get_ocgs() == []
    assert len(ocmd.get_ocgs_property_list()) == 1


def test_set_o_cgs_rejects_non_group_entries() -> None:
    ocmd = PDOptionalContentMembershipDictionary()

    with pytest.raises(TypeError, match="ocgs entries"):
        ocmd.set_o_cgs([object()])  # type: ignore[list-item]


def test_add_ocg_replaces_exotic_ocgs_value_with_single_item_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    group = _group("replacement")
    ocmd.get_cos_object().set_item(OCGS, COSName.get_pdf_name("Unexpected"))

    ocmd.add_ocg(group)

    raw = ocmd.get_cos_object().get_dictionary_object(OCGS)
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    assert raw.get_object(0) is group.get_cos_object()


def test_add_ocg_promotes_single_dictionary_and_deduplicates_identity() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    first = _group("first")
    second = _group("second")
    ocmd.set_ocgs(first)

    ocmd.add_ocg(first)
    assert ocmd.get_ocg_count() == 1

    ocmd.add_ocg(second.get_cos_object())
    assert ocmd.get_ocg_count() == 2
    assert ocmd.contains_ocg(second)


def test_remove_ocg_deletes_all_identity_matches_and_prunes_empty_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    group = _group("duplicate")
    arr = COSArray([group.get_cos_object(), group.get_cos_object()])
    ocmd.get_cos_object().set_item(OCGS, arr)

    assert ocmd.remove_ocg(group) is True
    assert ocmd.get_cos_object().get_dictionary_object(OCGS) is None
    assert ocmd.has_ocgs() is False
    assert len(ocmd) == 0


def test_remove_ocg_rejects_invalid_type_and_ignores_exotic_ocgs_value() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    group = _group("layer")

    with pytest.raises(TypeError, match="group must be"):
        ocmd.remove_ocg("layer")  # type: ignore[arg-type]

    ocmd.get_cos_object().set_item(OCGS, COSName.get_pdf_name("Unexpected"))
    assert ocmd.remove_ocg(group) is False


def test_clear_ocgs_removes_single_dictionary_form() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs(_group("solo"))

    assert ocmd.has_ocgs() is True
    ocmd.clear_ocgs()
    assert ocmd.get_ocg_count() == 0
    assert ocmd.get_ocgs() == []


def test_visibility_policy_enum_and_predicate_type_guards() -> None:
    ocmd = PDOptionalContentMembershipDictionary()

    ocmd.set_visibility_policy(MembershipDictionaryVisibilityPolicy.ANY_OFF)
    assert ocmd.get_visibility_policy_enum() is (
        MembershipDictionaryVisibilityPolicy.ANY_OFF
    )
    assert ocmd.is_visibility_policy(
        MembershipDictionaryVisibilityPolicy.ANY_OFF
    )
    assert ocmd.is_visibility_policy("AllOn") is False

    with pytest.raises(ValueError, match="visibility_policy"):
        ocmd.set_visibility_policy("Sometimes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="policy must be"):
        ocmd.is_visibility_policy(COSName.get_pdf_name("AnyOff"))  # type: ignore[arg-type]


def test_raw_policy_name_can_be_unknown_and_evaluates_like_any_on() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    group = _group("layer")
    ocmd.set_ocgs([group])
    ocmd.set_visibility_policy_name(COSName.get_pdf_name("CustomPolicy"))

    assert ocmd.get_visibility_policy() == "CustomPolicy"
    assert ocmd.evaluate_visibility({id(group.get_cos_object())}) is True
    assert ocmd.evaluate_visibility(set()) is False
    with pytest.raises(ValueError, match="no member"):
        ocmd.get_visibility_policy_enum()


def test_visibility_expression_getter_and_setter_validate_raw_shape() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.get_cos_object().set_item(VE, COSName.get_pdf_name("NotAnArray"))
    assert ocmd.get_visibility_expression() is None

    with pytest.raises(TypeError, match="COSArray"):
        ocmd.set_visibility_expression(COSName.get_pdf_name("And"))  # type: ignore[arg-type]


def test_visibility_expression_errors_for_bad_operator_shapes() -> None:
    ocmd = PDOptionalContentMembershipDictionary()

    for ve, message in [
        (COSArray(), "missing operator"),
        (COSArray([COSBoolean.TRUE]), "COSName operator"),
        (COSArray([COSName.get_pdf_name("Not")]), "exactly 1 operand"),
        (COSArray([COSName.get_pdf_name("And")]), ">= 1 operand"),
        (COSArray([COSName.get_pdf_name("Or")]), ">= 1 operand"),
        (COSArray([COSName.get_pdf_name("Xor"), COSBoolean.TRUE]), "Unknown"),
    ]:
        ocmd.set_visibility_expression(ve)
        with pytest.raises(ValueError, match=message):
            ocmd.evaluate_visibility(set())


def test_resolver_based_visibility_expression_handles_false_leaves_and_none() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    group = _group("layer")
    non_ocg = COSDictionary()
    ve = COSArray([COSName.get_pdf_name("Or"), non_ocg, group.get_cos_object()])
    ocmd.set_visibility_expression(ve)

    seen: list[str | None] = []

    def resolver(resolved: PDOptionalContentGroup) -> bool:
        seen.append(resolved.get_name())
        return resolved.get_name() == "layer"

    assert ocmd.is_visible_with(resolver) is True
    assert seen == ["layer"]

    ocmd.set_visibility_expression(None)
    ocmd.set_ocgs([group])
    ocmd.get_cos_object().set_item(P, COSName.get_pdf_name("AllOn"))
    assert ocmd.evaluate_ve(None, resolver) is True
