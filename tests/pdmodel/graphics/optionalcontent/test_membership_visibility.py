"""Hand-written tests for the PDOptionalContentMembershipDictionary
visibility evaluator.

Covers:
- The four /P policies (AllOn / AnyOn / AnyOff / AllOff) under the
  resolver-callable API ``is_visible_with``.
- Recursive /VE expression trees (And / Or / Not + nesting) under
  ``evaluate_ve``.
- The combined ``is_visible_with`` path (prefers /VE over /P).
- Edge cases: empty /OCGs, missing /P (default AnyOn), invalid /VE
  shapes, and unknown operators.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    MembershipDictionaryVisibilityPolicy,
    PDOptionalContentMembershipDictionary,
    StateResolver,
)


# ---------- Fixtures / helpers ----------


def _make_ocg(name: str) -> PDOptionalContentGroup:
    return PDOptionalContentGroup(name)


def _resolver_from_set(on: set[str]) -> StateResolver:
    """Return a resolver callable that reports an OCG ON iff its /Name
    appears in ``on``."""

    def _resolve(group: PDOptionalContentGroup) -> bool:
        return group.get_name() in on

    return _resolve


def _ocmd_with_groups(
    *groups: PDOptionalContentGroup,
    policy: str | MembershipDictionaryVisibilityPolicy | None = None,
) -> PDOptionalContentMembershipDictionary:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs(list(groups))
    if policy is not None:
        ocmd.set_visibility_policy(policy)
    return ocmd


# ---------- /P policy: AllOn ----------


def test_all_on_all_visible_returns_true():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AllOn")
    assert ocmd.is_visible_with(_resolver_from_set({"A", "B"})) is True


def test_all_on_one_off_returns_false():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AllOn")
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is False


def test_all_on_empty_ocgs_is_vacuously_true():
    ocmd = _ocmd_with_groups(policy="AllOn")
    assert ocmd.is_visible_with(_resolver_from_set(set())) is True


# ---------- /P policy: AnyOn ----------


def test_any_on_one_visible_returns_true():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AnyOn")
    assert ocmd.is_visible_with(_resolver_from_set({"B"})) is True


def test_any_on_all_off_returns_false():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AnyOn")
    assert ocmd.is_visible_with(_resolver_from_set(set())) is False


def test_any_on_is_default_policy():
    a = _make_ocg("A")
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs([a])
    # No /P set — default per PDF 1.7 §8.11.2.2.
    assert ocmd.get_visibility_policy() == "AnyOn"
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is True
    assert ocmd.is_visible_with(_resolver_from_set(set())) is False


# ---------- /P policy: AnyOff ----------


def test_any_off_one_off_returns_true():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AnyOff")
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is True


def test_any_off_all_on_returns_false():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AnyOff")
    assert ocmd.is_visible_with(_resolver_from_set({"A", "B"})) is False


def test_any_off_empty_ocgs_is_vacuously_false():
    ocmd = _ocmd_with_groups(policy="AnyOff")
    assert ocmd.is_visible_with(_resolver_from_set(set())) is False


# ---------- /P policy: AllOff ----------


def test_all_off_all_off_returns_true():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AllOff")
    assert ocmd.is_visible_with(_resolver_from_set(set())) is True


def test_all_off_one_on_returns_false():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b, policy="AllOff")
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is False


def test_all_off_empty_ocgs_is_vacuously_true():
    ocmd = _ocmd_with_groups(policy="AllOff")
    assert ocmd.is_visible_with(_resolver_from_set(set())) is True


# ---------- /P with the typed enum ----------


def test_policy_set_via_enum_round_trips():
    a = _make_ocg("A")
    ocmd = _ocmd_with_groups(
        a, policy=MembershipDictionaryVisibilityPolicy.ALL_OFF
    )
    assert ocmd.get_visibility_policy() == "AllOff"
    assert (
        ocmd.get_visibility_policy_enum()
        is MembershipDictionaryVisibilityPolicy.ALL_OFF
    )
    assert ocmd.is_visible_with(_resolver_from_set(set())) is True


# ---------- /VE expression tree ----------


def _ve_op(op: str, *children: object) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name(op))
    for child in children:
        if isinstance(child, PDOptionalContentGroup):
            arr.add(child.get_cos_object())
        else:
            arr.add(child)
    return arr


def test_ve_or_with_one_visible_returns_true():
    a, b = _make_ocg("A"), _make_ocg("B")
    ve = _ve_op("Or", a, b)
    ocmd = _ocmd_with_groups(a, b)
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set({"B"})) is True


def test_ve_or_all_off_returns_false():
    a, b = _make_ocg("A"), _make_ocg("B")
    ve = _ve_op("Or", a, b)
    ocmd = _ocmd_with_groups(a, b)
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set(set())) is False


def test_ve_and_one_off_returns_false():
    a, b = _make_ocg("A"), _make_ocg("B")
    ve = _ve_op("And", a, b)
    ocmd = _ocmd_with_groups(a, b)
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is False


def test_ve_and_all_on_returns_true():
    a, b = _make_ocg("A"), _make_ocg("B")
    ve = _ve_op("And", a, b)
    ocmd = _ocmd_with_groups(a, b)
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set({"A", "B"})) is True


def test_ve_not_inverts_child():
    a = _make_ocg("A")
    ve = _ve_op("Not", a)
    ocmd = _ocmd_with_groups(a)
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set(set())) is True
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is False


def test_ve_nested_and_or_not():
    # VE := And( Or(A, B), Not(C) )
    a, b, c = _make_ocg("A"), _make_ocg("B"), _make_ocg("C")
    ve = _ve_op(
        "And",
        _ve_op("Or", a, b),
        _ve_op("Not", c),
    )
    ocmd = _ocmd_with_groups(a, b, c)
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is True
    assert ocmd.is_visible_with(_resolver_from_set({"B"})) is True
    assert ocmd.is_visible_with(_resolver_from_set({"A", "C"})) is False
    assert ocmd.is_visible_with(_resolver_from_set({"C"})) is False
    assert ocmd.is_visible_with(_resolver_from_set(set())) is False


def test_ve_overrides_policy_when_present():
    # /P would say AllOff (visible iff none on), but /VE says
    # "visible iff A is on".
    a = _make_ocg("A")
    ve = _ve_op("Or", a)
    ocmd = _ocmd_with_groups(a, policy="AllOff")
    ocmd.set_visibility_expression(ve)
    assert ocmd.is_visible_with(_resolver_from_set({"A"})) is True
    assert ocmd.is_visible_with(_resolver_from_set(set())) is False


def test_ve_none_falls_back_to_policy():
    a = _make_ocg("A")
    ocmd = _ocmd_with_groups(a, policy="AnyOn")
    # evaluate_ve(None, ...) routes through the /P policy fallback.
    assert ocmd.evaluate_ve(None, _resolver_from_set({"A"})) is True
    assert ocmd.evaluate_ve(None, _resolver_from_set(set())) is False


# ---------- /VE error paths ----------


def test_ve_empty_subarray_raises():
    a = _make_ocg("A")
    ocmd = _ocmd_with_groups(a)
    ocmd.set_visibility_expression(COSArray())
    with pytest.raises(ValueError):
        ocmd.is_visible_with(_resolver_from_set({"A"}))


def test_ve_missing_operator_raises():
    a = _make_ocg("A")
    ve = COSArray()
    # First entry should be a COSName operator; an OCG dict here is wrong.
    ve.add(a.get_cos_object())
    ocmd = _ocmd_with_groups(a)
    ocmd.set_visibility_expression(ve)
    with pytest.raises(ValueError):
        ocmd.is_visible_with(_resolver_from_set({"A"}))


def test_ve_unknown_operator_raises():
    a = _make_ocg("A")
    ve = _ve_op("Xor", a)
    ocmd = _ocmd_with_groups(a)
    ocmd.set_visibility_expression(ve)
    with pytest.raises(ValueError):
        ocmd.is_visible_with(_resolver_from_set({"A"}))


def test_ve_not_with_two_operands_raises():
    a, b = _make_ocg("A"), _make_ocg("B")
    ve = _ve_op("Not", a, b)
    ocmd = _ocmd_with_groups(a, b)
    ocmd.set_visibility_expression(ve)
    with pytest.raises(ValueError):
        ocmd.is_visible_with(_resolver_from_set({"A"}))


def test_ve_and_with_no_operands_raises():
    ocmd = _ocmd_with_groups()
    ocmd.set_visibility_expression(_ve_op("And"))
    with pytest.raises(ValueError):
        ocmd.is_visible_with(_resolver_from_set(set()))


def test_ve_or_with_no_operands_raises():
    ocmd = _ocmd_with_groups()
    ocmd.set_visibility_expression(_ve_op("Or"))
    with pytest.raises(ValueError):
        ocmd.is_visible_with(_resolver_from_set(set()))


# ---------- getOCGs helper ----------


def test_get_ocgs_returns_wrapper_list():
    a, b = _make_ocg("A"), _make_ocg("B")
    ocmd = _ocmd_with_groups(a, b)
    groups = ocmd.get_ocgs()
    assert [g.get_name() for g in groups] == ["A", "B"]
    # Both spellings (PDFBox-friendly + auto-camel-split) agree on contents.
    assert [g.get_cos_object() for g in ocmd.get_ocgs()] == [
        g.get_cos_object() for g in ocmd.get_o_cgs()
    ]


def test_get_ocgs_handles_single_dictionary_form():
    a = _make_ocg("A")
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs(a)  # single OCG, not a list
    groups = ocmd.get_ocgs()
    assert len(groups) == 1
    assert groups[0].get_name() == "A"


def test_get_ocgs_missing_returns_empty():
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_ocgs() == []
