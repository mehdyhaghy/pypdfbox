from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import PDOptionalContentGroup
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (
    PDOptionalContentMembershipDictionary,
)

OCGS = COSName.get_pdf_name("OCGs")
P = COSName.get_pdf_name("P")


def _group(name: str) -> PDOptionalContentGroup:
    return PDOptionalContentGroup(name)


def test_wave725_ocgs_exotic_value_reads_as_empty() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.get_cos_object().set_item(OCGS, COSName.get_pdf_name("Broken"))

    assert ocmd.get_o_cgs() == []
    assert ocmd.get_ocgs_property_list() == []
    assert ocmd.contains_ocg(_group("Layer")) is False


def test_wave725_set_o_cgs_accepts_raw_cos_dictionary() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    raw = _group("Raw").get_cos_object()

    ocmd.set_o_cgs([raw])

    stored = ocmd.get_cos_object().get_dictionary_object(OCGS)
    assert isinstance(stored, COSArray)
    assert stored.get_object(0) is raw
    assert ocmd.get_ocgs()[0].get_cos_object() is raw


def test_wave725_raw_visibility_expression_non_node_is_false() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_expression(COSArray([COSName.get_pdf_name("Not"), COSBoolean.TRUE]))

    assert ocmd.evaluate_visibility(set()) is True


def test_wave725_resolver_visibility_expression_non_node_is_false() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_expression(COSArray([COSName.get_pdf_name("Not"), COSBoolean.TRUE]))

    assert ocmd.is_visible_with(lambda group: group.get_name() == "unused") is True
    assert (
        PDOptionalContentMembershipDictionary._eval_node_with(
            COSBoolean.TRUE,
            lambda group: group.get_name() == "unused",
        )
        is False
    )


def test_wave725_resolver_unknown_policy_falls_back_to_any_on() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    first = _group("First")
    second = _group("Second")
    ocmd.set_ocgs([first, second])
    ocmd.get_cos_object().set_item(P, COSName.get_pdf_name("CustomPolicy"))

    assert ocmd.is_visible_with(lambda group: group.get_name() == "Second") is True
    assert ocmd.is_visible_with(lambda group: False) is False


def test_wave725_raw_eval_node_matches_dictionary_identity_and_rejects_other_nodes() -> None:
    raw_leaf = COSDictionary()

    assert PDOptionalContentMembershipDictionary._eval_node(
        raw_leaf, {id(raw_leaf)}
    ) is True
    assert PDOptionalContentMembershipDictionary._eval_node(raw_leaf, set()) is False
    assert PDOptionalContentMembershipDictionary._eval_node(
        COSBoolean.TRUE, set()
    ) is False
