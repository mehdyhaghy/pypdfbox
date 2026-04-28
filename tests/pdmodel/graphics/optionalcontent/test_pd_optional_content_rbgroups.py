"""Tests for the new /D round-out: /RBGroups (radio-button enforcement),
/Locked, /Intent, and the :meth:`is_group_visible` alias on
:class:`PDOptionalContentProperties`. None of these are part of upstream
PDFBox 3.0; they are pypdfbox enrichments and validated here against the
PDF 32000-1 §8.11.4.3 Table 101 semantics."""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _build(
    *names: str,
) -> tuple[PDOptionalContentProperties, list[PDOptionalContentGroup]]:
    props = PDOptionalContentProperties()
    groups = [PDOptionalContentGroup(n) for n in names]
    for g in groups:
        props.add_group(g)
    return props, groups


# ---------- /RBGroups ----------


def test_rbgroup_enabling_one_disables_siblings() -> None:
    props, (a, b, c) = _build("A", "B", "C")
    props.add_rbgroup([a, b])
    # Initially all enabled (BaseState ON, no /OFF entries).
    assert props.is_group_enabled(a) is True
    assert props.is_group_enabled(b) is True
    assert props.is_group_enabled(c) is True

    # Toggle A on explicitly: B should be forced off; C untouched.
    props.set_group_enabled(a, True)
    assert props.is_group_enabled(a) is True
    assert props.is_group_enabled(b) is False
    assert props.is_group_enabled(c) is True


def test_rbgroup_enabling_only_affects_target_group() -> None:
    props, (a, b, c, d) = _build("A", "B", "C", "D")
    props.add_rbgroup([a, b])
    props.add_rbgroup([c, d])

    props.set_group_enabled(c, True)
    # C ON → D forced OFF; A/B untouched.
    assert props.is_group_enabled(c) is True
    assert props.is_group_enabled(d) is False
    assert props.is_group_enabled(a) is True
    assert props.is_group_enabled(b) is True


def test_rbgroup_disabling_does_not_force_siblings_on() -> None:
    """Spec says /RBGroups governs *enabling* — disabling has no
    auto-effect on siblings."""
    props, (a, b) = _build("A", "B")
    props.add_rbgroup([a, b])
    props.set_group_enabled(a, False)
    # A explicitly off, B remains untouched (still enabled by base state).
    assert props.is_group_enabled(a) is False
    assert props.is_group_enabled(b) is True


def test_rbgroup_lookup_helpers() -> None:
    props, (a, b) = _build("A", "B")
    assert props.get_rbgroups() == []
    props.add_rbgroup([a, b])
    rbgroups = props.get_rbgroups()
    assert len(rbgroups) == 1
    assert [g.get_name() for g in rbgroups[0]] == ["A", "B"]


# ---------- /Locked ----------


def test_locked_round_trip_via_properties() -> None:
    props, (a, b) = _build("A", "B")
    assert props.is_locked(a) is False
    props.set_locked([a])
    assert props.is_locked(a) is True
    assert props.is_locked(b) is False
    assert [g.get_name() for g in props.get_locked()] == ["A"]
    props.add_locked(b)
    assert [g.get_name() for g in props.get_locked()] == ["A", "B"]
    props.set_locked(None)
    assert props.get_locked() == []


# ---------- /D /Intent ----------


def test_intent_default_is_view() -> None:
    props = PDOptionalContentProperties()
    assert props.get_intent() == "View"


def test_intent_set_string() -> None:
    props = PDOptionalContentProperties()
    props.set_intent("Design")
    assert props.get_intent() == "Design"


def test_intent_set_list() -> None:
    props = PDOptionalContentProperties()
    props.set_intent(["View", "Design"])
    assert props.get_intent() == ["View", "Design"]


def test_intent_clear_returns_to_default() -> None:
    props = PDOptionalContentProperties()
    props.set_intent("Design")
    props.set_intent(None)
    assert props.get_intent() == "View"


# ---------- is_group_visible ----------


def test_is_group_visible_alias_matches_is_group_enabled() -> None:
    props, (a, b) = _build("A", "B")
    assert props.is_group_visible(a) is True
    assert props.is_group_visible("B") is True
    props.set_hidden(a)
    assert props.is_group_visible(a) is False
    assert props.is_group_visible("A") is False


# ---------- compute_visible_ocgs interplay with /RBGroups ----------


def test_rbgroup_toggle_propagates_to_compute_visible_ocgs() -> None:
    props, (a, b, c) = _build("A", "B", "C")
    props.add_rbgroup([a, b])
    props.set_group_enabled(a, True)
    visible = props.compute_visible_ocgs()
    # B was forced off by /RBGroups when A was enabled.
    assert visible == {id(a.get_cos_object()), id(c.get_cos_object())}


def test_rbgroup_no_op_when_target_outside_any_group() -> None:
    """Setting an OCG ON that does not belong to any /RBGroups must not
    perturb other groups."""
    props, (a, b, c) = _build("A", "B", "C")
    props.add_rbgroup([a, b])
    props.set_group_enabled(c, True)
    # A and B remain in their original states (both enabled by base state).
    assert props.is_group_enabled(a) is True
    assert props.is_group_enabled(b) is True


def test_rbgroup_with_indirect_object_entries() -> None:
    """/RBGroups built from raw arrays at the dict level should also
    enforce the toggle (covers PDFs whose /RBGroups was authored manually)."""
    props, (a, b, c) = _build("A", "B", "C")
    d = props.get_cos_object().get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(d, COSDictionary)
    rbgroups = COSArray()
    sub = COSArray()
    sub.add(a.get_cos_object())
    sub.add(b.get_cos_object())
    rbgroups.add(sub)
    d.set_item(COSName.get_pdf_name("RBGroups"), rbgroups)

    props.set_group_enabled(b, True)
    assert props.is_group_enabled(a) is False
    assert props.is_group_enabled(b) is True
    assert props.is_group_enabled(c) is True
