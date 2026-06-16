"""Behavioral-parity fuzz for optional content (PDF layers), wave 1575.

Hammers the read/write surface of :class:`PDOptionalContentProperties` (the
catalog ``/OCProperties`` wrapper) and
:class:`PDOptionalContentMembershipDictionary` (OCMD) against the documented
Apache PDFBox 3.0.7 semantics:

- ``is_group_enabled`` / ``set_group_enabled`` driven through the ``/D /ON``
  and ``/D /OFF`` arrays, including the upstream "move first match from the
  opposite array, else append (possibly duplicate)" contract and its ``found``
  return value (PDOptionalContentProperties.java setGroupEnabled).
- ``/D /BaseState`` ``ON`` vs ``OFF`` vs ``Unchanged`` default visibility.
- ``add_group`` / ``get_optional_content_groups`` / ``get_group`` name lookup.
- OCMD ``/P`` policy logic (``AnyOn`` / ``AllOn`` / ``AnyOff`` / ``AllOff``)
  over multiple OCGs and a single OCG, plus the default-when-absent
  (``AnyOn``) and vacuous-empty-/OCGs behavior.
- the ``/Order`` tree (nested arrays).

These are hand-written parity cases — the upstream Java behavior was read out
of pdfbox 3.0.7 PDOptionalContentProperties.java /
PDOptionalContentMembershipDictionary.java rather than translated from a
single JUnit file, so they live alongside (not under) the upstream/ tree.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentMembershipDictionary,
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    MembershipDictionaryVisibilityPolicy,
)

_ON = COSName.get_pdf_name("ON")
_OFF = COSName.get_pdf_name("OFF")
_BASE_STATE = COSName.get_pdf_name("BaseState")
_ORDER = COSName.get_pdf_name("Order")


def _build(*names: str):
    props = PDOptionalContentProperties()
    groups = [PDOptionalContentGroup(n) for n in names]
    for g in groups:
        props.add_group(g)
    return props, groups


def _default(props: PDOptionalContentProperties) -> COSDictionary:
    d = props.get_cos_object().get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(d, COSDictionary)
    return d


def _arr(props: PDOptionalContentProperties, key: COSName) -> COSArray:
    a = _default(props).get_dictionary_object(key)
    assert isinstance(a, COSArray)
    return a


# --------------------------------------------------------------------------
# get_optional_content_groups / add_group / name lookup
# --------------------------------------------------------------------------


def test_get_optional_content_groups_lists_added_in_order() -> None:
    props, (a, b, c) = _build("A", "B", "C")
    groups = props.get_optional_content_groups()
    assert [g.get_name() for g in groups] == ["A", "B", "C"]


def test_get_groups_alias_matches_upstream_spelling() -> None:
    props, _ = _build("X", "Y")
    assert [g.get_name() for g in props.get_groups()] == ["X", "Y"]
    assert [g.get_name() for g in props.get_optional_content_groups()] == ["X", "Y"]


def test_add_group_also_appends_to_order_tree() -> None:
    props, (a,) = _build("A")
    order = _default(props).get_dictionary_object(_ORDER)
    assert isinstance(order, COSArray)
    assert order.size() == 1
    assert order.get_object(0) is a.get_cos_object()


def test_get_group_name_lookup_returns_first_match() -> None:
    props, (a, b) = _build("Layer", "Other")
    found = props.get_group("Layer")
    assert found is not None
    assert found.get_cos_object() is a.get_cos_object()
    assert props.get_group("Other").get_cos_object() is b.get_cos_object()


def test_get_group_missing_returns_none() -> None:
    props, _ = _build("A")
    assert props.get_group("Nope") is None
    assert props.has_group("Nope") is False
    assert props.has_group("A") is True


def test_get_group_names_preserves_array_order() -> None:
    props, _ = _build("First", "Second")
    assert props.get_group_names() == ["First", "Second"]


def test_get_group_names_nameless_dict_yields_none_slot() -> None:
    props = PDOptionalContentProperties()
    ocg = PDOptionalContentGroup(COSDictionary())  # no /Name set
    props.add_group(ocg)
    # Upstream getString(/Name) returns null uncoalesced for a nameless OCG.
    assert props.get_group_names() == [None]


def test_get_group_names_non_dict_entry_yields_empty_string() -> None:
    props = PDOptionalContentProperties()
    props.get_oc_gs().add(COSName.get_pdf_name("junk"))
    assert props.get_group_names() == [""]


# --------------------------------------------------------------------------
# BaseState default visibility
# --------------------------------------------------------------------------


def test_base_state_default_is_on_when_absent() -> None:
    props, (a,) = _build("A")
    assert props.get_base_state() == "ON"
    # No /ON or /OFF entry, BaseState ON => enabled.
    assert props.is_group_enabled(a) is True


def test_base_state_off_disables_groups_not_in_on() -> None:
    props, (a,) = _build("A")
    props.set_base_state("OFF")
    assert props.get_base_state() == "OFF"
    # Not listed in /D /ON => defaults off.
    assert props.is_group_enabled(a) is False


def test_base_state_off_but_group_in_on_is_enabled() -> None:
    props, (a, b) = _build("A", "B")
    props.set_base_state("OFF")
    _default(props).set_item(_ON, COSArray([a.get_cos_object()]))
    assert props.is_group_enabled(a) is True
    assert props.is_group_enabled(b) is False


def test_base_state_on_but_group_in_off_is_disabled() -> None:
    props, (a,) = _build("A")
    _default(props).set_item(_OFF, COSArray([a.get_cos_object()]))
    assert props.is_group_enabled(a) is False


def test_base_state_unchanged_treated_as_enabled_baseline() -> None:
    props, (a,) = _build("A")
    props.set_base_state("Unchanged")
    assert props.get_base_state() == "Unchanged"
    # enabled = baseState != OFF, so Unchanged seeds enabled True.
    assert props.is_group_enabled(a) is True


def test_is_group_enabled_none_returns_base_state_flag() -> None:
    props = PDOptionalContentProperties()
    assert props.is_group_enabled(None) is True
    props.set_base_state("OFF")
    assert props.is_group_enabled(None) is False


def test_base_state_raw_name_round_trip() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state(PDOptionalContentProperties.BaseState.OFF)
    assert _default(props).get_dictionary_object(_BASE_STATE) == _OFF


# --------------------------------------------------------------------------
# is_group_enabled: ON wins over OFF, name-based "at least one enabled"
# --------------------------------------------------------------------------


def test_group_in_both_on_and_off_resolves_on_first() -> None:
    # Upstream checks /ON before /OFF, so /ON wins when a group is in both.
    props, (a,) = _build("A")
    d = _default(props)
    d.set_item(_ON, COSArray([a.get_cos_object()]))
    d.set_item(_OFF, COSArray([a.get_cos_object()]))
    assert props.is_group_enabled(a) is True


def test_is_group_enabled_by_name_any_enabled() -> None:
    # Two OCGs share a /Name; one off, one on => "at least one enabled" True.
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("Dup")
    b = PDOptionalContentGroup("Dup")
    props.add_group(a)
    props.add_group(b)
    _default(props).set_item(_OFF, COSArray([a.get_cos_object()]))
    _default(props).set_item(_ON, COSArray([b.get_cos_object()]))
    assert props.is_group_enabled("Dup") is True


def test_is_group_enabled_by_name_all_off_is_false() -> None:
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("Dup")
    b = PDOptionalContentGroup("Dup")
    props.add_group(a)
    props.add_group(b)
    off = COSArray([a.get_cos_object(), b.get_cos_object()])
    _default(props).set_item(_OFF, off)
    assert props.is_group_enabled("Dup") is False


def test_is_group_enabled_unknown_name_false() -> None:
    props, _ = _build("A")
    assert props.is_group_enabled("Ghost") is False


# --------------------------------------------------------------------------
# set_group_enabled: upstream move-or-append + found semantics
# --------------------------------------------------------------------------


def test_set_group_enabled_first_enable_appends_and_returns_false() -> None:
    props, (a,) = _build("A")
    # Group not previously tracked: scans /OFF (empty), found=False, append /ON.
    assert props.set_group_enabled(a, True) is False
    assert _arr(props, _ON).size() == 1
    assert _arr(props, _ON).get_object(0) is a.get_cos_object()
    assert _arr(props, _OFF).size() == 0


def test_set_group_enabled_disable_then_enable_round_trip() -> None:
    props, (a,) = _build("A")
    # Disable: scans /ON (empty), found=False, append /OFF.
    assert props.set_group_enabled(a, False) is False
    assert props.is_group_enabled(a) is False
    # Enable: scans /OFF, finds it, moves to /ON, found=True.
    assert props.set_group_enabled(a, True) is True
    assert props.is_group_enabled(a) is True
    assert _arr(props, _ON).size() == 1
    assert _arr(props, _OFF).size() == 0


def test_set_group_enabled_enable_when_already_on_appends_duplicate() -> None:
    props, (a,) = _build("A")
    _default(props).set_item(_ON, COSArray([a.get_cos_object()]))
    _default(props).set_item(_OFF, COSArray())
    # Upstream scans only /OFF on enable -> not found -> append again.
    assert props.set_group_enabled(a, True) is False
    assert _arr(props, _ON).size() == 2


def test_set_group_enabled_disable_when_already_off_appends_duplicate() -> None:
    props, (a,) = _build("A")
    _default(props).set_item(_ON, COSArray())
    _default(props).set_item(_OFF, COSArray([a.get_cos_object()]))
    assert props.set_group_enabled(a, False) is False
    assert _arr(props, _OFF).size() == 2


def test_set_group_enabled_enable_moves_single_off_entry() -> None:
    props, (a,) = _build("A")
    _default(props).set_item(_OFF, COSArray([a.get_cos_object()]))
    _default(props).set_item(_ON, COSArray())
    assert props.set_group_enabled(a, True) is True
    assert _arr(props, _OFF).size() == 0
    assert _arr(props, _ON).size() == 1


def test_set_group_enabled_by_name_returns_true_when_any_had_setting() -> None:
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("Dup")
    b = PDOptionalContentGroup("Dup")
    props.add_group(a)
    props.add_group(b)
    # a already in /OFF; b untracked. Enabling by name: a moves off->on (found),
    # b appended (not found). At least one found => True.
    _default(props).set_item(_OFF, COSArray([a.get_cos_object()]))
    assert props.set_group_enabled("Dup", True) is True


def test_set_group_enabled_unknown_name_returns_false() -> None:
    props, _ = _build("A")
    assert props.set_group_enabled("Ghost", True) is False


def test_set_group_enabled_enable_a_group_absent_from_any_config() -> None:
    # OCG that is in /OCGs but not referenced by /D config at all.
    props, (a, b) = _build("A", "B")
    assert props.is_group_enabled(b) is True  # BaseState ON baseline
    assert props.set_group_enabled(b, False) is False
    assert props.is_group_enabled(b) is False


# --------------------------------------------------------------------------
# OCMD /P policy logic over multiple and single OCGs
# --------------------------------------------------------------------------


def _ocmd(policy: str | None, *groups: PDOptionalContentGroup):
    ocmd = PDOptionalContentMembershipDictionary()
    if len(groups) == 1:
        ocmd.set_ocgs(groups[0])
    else:
        ocmd.set_ocgs(list(groups))
    if policy is not None:
        ocmd.set_visibility_policy(policy)
    return ocmd


def _resolver(on_groups):
    on_ids = {id(g.get_cos_object()) for g in on_groups}
    return lambda g: id(g.get_cos_object()) in on_ids


@pytest.mark.parametrize(
    ("policy", "on_first", "on_second", "expected"),
    [
        # AnyOn: visible iff at least one member on.
        ("AnyOn", True, False, True),
        ("AnyOn", False, False, False),
        ("AnyOn", True, True, True),
        # AllOn: visible iff every member on.
        ("AllOn", True, True, True),
        ("AllOn", True, False, False),
        ("AllOn", False, False, False),
        # AnyOff: visible iff at least one member off.
        ("AnyOff", True, False, True),
        ("AnyOff", True, True, False),
        ("AnyOff", False, False, True),
        # AllOff: visible iff every member off.
        ("AllOff", False, False, True),
        ("AllOff", True, False, False),
        ("AllOff", True, True, False),
    ],
)
def test_ocmd_policy_two_groups(
    policy: str, on_first: bool, on_second: bool, expected: bool
) -> None:
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd = _ocmd(policy, a, b)
    on = [g for g, flag in ((a, on_first), (b, on_second)) if flag]
    visible = {id(g.get_cos_object()) for g in on}
    assert ocmd.is_visible(visible) is expected
    # Resolver-callable path must agree.
    assert ocmd.is_visible_with(_resolver(on)) is expected


@pytest.mark.parametrize(
    ("policy", "member_on", "expected"),
    [
        ("AnyOn", True, True),
        ("AnyOn", False, False),
        ("AllOn", True, True),
        ("AllOn", False, False),
        ("AnyOff", True, False),
        ("AnyOff", False, True),
        ("AllOff", True, False),
        ("AllOff", False, True),
    ],
)
def test_ocmd_policy_single_ocg(
    policy: str, member_on: bool, expected: bool
) -> None:
    a = PDOptionalContentGroup("Solo")
    ocmd = _ocmd(policy, a)
    assert ocmd.get_ocg_count() == 1
    visible = {id(a.get_cos_object())} if member_on else set()
    assert ocmd.is_visible(visible) is expected


def test_ocmd_default_policy_is_anyon() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_visibility_policy() == "AnyOn"
    assert ocmd.is_visibility_policy("AnyOn") is True
    assert ocmd.is_visibility_policy(
        MembershipDictionaryVisibilityPolicy.ANY_ON
    ) is True


def test_ocmd_empty_ocgs_vacuous_semantics() -> None:
    # No /OCGs: AllOn/AllOff vacuously True, AnyOn/AnyOff vacuously False.
    visible: set[int] = set()
    for policy, expected in (
        ("AllOn", True),
        ("AllOff", True),
        ("AnyOn", False),
        ("AnyOff", False),
    ):
        ocmd = PDOptionalContentMembershipDictionary()
        ocmd.set_visibility_policy(policy)
        assert ocmd.is_visible(visible) is expected


def test_ocmd_single_ocg_read_back_count_and_membership() -> None:
    a = PDOptionalContentGroup("Solo")
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs(a)
    assert ocmd.get_ocg_count() == 1
    assert ocmd.contains_ocg(a) is True
    assert [g.get_name() for g in ocmd.get_ocgs()] == ["Solo"]


def test_ocmd_invalid_policy_rejected() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(ValueError):
        ocmd.set_visibility_policy("Maybe")


# --------------------------------------------------------------------------
# /Order tree (nested arrays)
# --------------------------------------------------------------------------


def test_order_tree_nested_arrays_preserved_on_read() -> None:
    props, (a, b, c) = _build("A", "B", "C")
    cfg = props.get_default_configuration()
    # Build a nested /Order: [A, [B, C]]
    nested = COSArray([b.get_cos_object(), c.get_cos_object()])
    order = COSArray([a.get_cos_object(), nested])
    cfg.set_order(order)
    read = cfg.get_order()
    assert read is not None
    assert read.size() == 2
    assert read.get_object(0) is a.get_cos_object()
    inner = read.get_object(1)
    assert isinstance(inner, COSArray)
    assert inner.size() == 2
    assert inner.get_object(0) is b.get_cos_object()


def test_remove_group_scrubs_nested_order_entry() -> None:
    props, (a, b, c) = _build("A", "B", "C")
    cfg = props.get_default_configuration()
    nested = COSArray([b.get_cos_object(), c.get_cos_object()])
    cfg.set_order(COSArray([a.get_cos_object(), nested]))
    assert props.remove_group(b) is True
    order = cfg.get_order()
    assert order is not None
    inner = order.get_object(1)
    assert isinstance(inner, COSArray)
    assert inner.size() == 1
    assert inner.get_object(0) is c.get_cos_object()
