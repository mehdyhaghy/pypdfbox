"""Wave 267 round-out tests for :class:`PDActionSetOCGState`.

Cover the predicate / clear / typed-view surface added in wave 267:
``has_state``, ``has_preserve_rb``, ``clear_state``, ``clear_preserve_rb``,
``is_empty``, ``is_valid``, and ``get_groups``."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.interactive.action import (
    PDAction,
    PDActionSetOCGState,
)

_S: COSName = COSName.get_pdf_name("S")
_STATE: COSName = COSName.get_pdf_name("State")
_PRESERVE_RB: COSName = COSName.get_pdf_name("PreserveRB")
_ON: COSName = COSName.get_pdf_name("ON")
_OFF: COSName = COSName.get_pdf_name("OFF")


def _ocg(name: str) -> PDOptionalContentGroup:
    return PDOptionalContentGroup(name)


# ---------- has_state ----------


def test_has_state_false_on_fresh_action() -> None:
    assert PDActionSetOCGState().has_state() is False


def test_has_state_true_after_set_state_iterable() -> None:
    action = PDActionSetOCGState()
    action.set_state(["ON", _ocg("L1")])
    assert action.has_state() is True


def test_has_state_true_after_set_state_cos_array() -> None:
    action = PDActionSetOCGState()
    action.set_state(COSArray([_ON, _ocg("L1").get_cos_object()]))
    assert action.has_state() is True


def test_has_state_false_when_state_is_non_array() -> None:
    """Spec-invalid non-array /State values report as state-absent —
    matches what get_cos_state filters."""
    raw = COSDictionary()
    raw.set_name(_S, "SetOCGState")
    raw.set_item(_STATE, COSString("not-an-array"))
    action = PDActionSetOCGState(raw)
    assert action.has_state() is False


# ---------- has_preserve_rb ----------


def test_has_preserve_rb_false_on_fresh_action() -> None:
    """Freshly constructed ⇒ /PreserveRB not yet written; effective
    value still defaults to True via the spec."""
    action = PDActionSetOCGState()
    assert action.has_preserve_rb() is False
    assert action.is_preserve_rb() is True


def test_has_preserve_rb_true_after_set_true() -> None:
    action = PDActionSetOCGState()
    action.set_preserve_rb(True)
    assert action.has_preserve_rb() is True
    assert action.is_preserve_rb() is True


def test_has_preserve_rb_true_after_set_false() -> None:
    """Independent of the boolean value — present-but-false still
    counts as 'present'."""
    action = PDActionSetOCGState()
    action.set_preserve_rb(False)
    assert action.has_preserve_rb() is True
    assert action.is_preserve_rb() is False


# ---------- clear_state / clear_preserve_rb ----------


def test_clear_state_removes_entry() -> None:
    action = PDActionSetOCGState()
    action.set_state(["ON", _ocg("L1")])
    assert action.has_state() is True
    action.clear_state()
    assert action.has_state() is False
    assert action.get_state() == []
    assert action.get_cos_state() is None


def test_clear_state_idempotent_when_absent() -> None:
    action = PDActionSetOCGState()
    action.clear_state()
    action.clear_state()
    assert action.has_state() is False


def test_clear_preserve_rb_resets_to_default() -> None:
    action = PDActionSetOCGState()
    action.set_preserve_rb(False)
    assert action.is_preserve_rb() is False
    action.clear_preserve_rb()
    assert action.has_preserve_rb() is False
    # /PreserveRB now absent ⇒ defaults back to True per Table 207.
    assert action.is_preserve_rb() is True


def test_clear_preserve_rb_idempotent_when_absent() -> None:
    action = PDActionSetOCGState()
    action.clear_preserve_rb()
    action.clear_preserve_rb()
    assert action.has_preserve_rb() is False


# ---------- is_empty ----------


def test_is_empty_true_on_fresh_action() -> None:
    """Freshly constructed: no /State array ⇒ empty."""
    assert PDActionSetOCGState().is_empty() is True


def test_is_empty_true_when_state_array_is_empty() -> None:
    """A /State present but with zero entries is still functionally
    a no-op — ``is_empty`` reports True."""
    action = PDActionSetOCGState()
    action.set_state(COSArray())
    assert action.has_state() is True
    assert action.is_empty() is True


def test_is_empty_false_when_state_has_entries() -> None:
    action = PDActionSetOCGState()
    action.set_state(["ON", _ocg("L1")])
    assert action.is_empty() is False


def test_is_empty_ignores_preserve_rb() -> None:
    """``/PreserveRB`` alone (no /State) does not make the action
    "non-empty" — without an OCG list to act on, the action is still
    a no-op at viewer level."""
    action = PDActionSetOCGState()
    action.set_preserve_rb(False)
    assert action.has_preserve_rb() is True
    assert action.is_empty() is True


# ---------- is_valid ----------


def test_is_valid_true_on_fresh_action() -> None:
    assert PDActionSetOCGState().is_valid() is True


def test_is_valid_true_after_factory_dispatch() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "SetOCGState")
    parsed = PDAction.create(raw)
    assert isinstance(parsed, PDActionSetOCGState)
    assert parsed.is_valid() is True


def test_is_valid_false_when_subtype_mismatched() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "URI")
    action = PDActionSetOCGState(raw)
    assert action.is_valid() is False


def test_is_valid_false_when_subtype_missing() -> None:
    raw = COSDictionary()
    # No /S at all.
    action = PDActionSetOCGState(raw)
    assert action.is_valid() is False


# ---------- get_groups ----------


def test_get_groups_empty_when_state_absent() -> None:
    assert PDActionSetOCGState().get_groups() == []


def test_get_groups_returns_typed_wrappers() -> None:
    layer_a = _ocg("Layer A")
    layer_b = _ocg("Layer B")
    action = PDActionSetOCGState()
    action.set_state(["ON", layer_a, "OFF", layer_b])

    groups = action.get_groups()
    assert len(groups) == 2
    assert all(isinstance(g, PDOptionalContentGroup) for g in groups)
    assert groups[0].get_cos_object() is layer_a.get_cos_object()
    assert groups[1].get_cos_object() is layer_b.get_cos_object()


def test_get_groups_preserves_duplicates() -> None:
    """The same OCG referenced twice in /State (e.g. ON-then-OFF)
    appears twice in the result — get_groups does not de-dup."""
    layer = _ocg("L1")
    action = PDActionSetOCGState()
    action.set_state(["ON", layer, "OFF", layer])

    groups = action.get_groups()
    assert len(groups) == 2
    assert groups[0].get_cos_object() is groups[1].get_cos_object()


def test_get_groups_skips_preamble_names() -> None:
    """The preamble ``COSName`` entries (ON/OFF/Toggle) are not OCGs and
    must not appear in the typed list."""
    layer = _ocg("Layer")
    action = PDActionSetOCGState()
    action.set_state(["ON", layer, "Toggle", layer, "OFF", layer])

    groups = action.get_groups()
    assert len(groups) == 3
    for g in groups:
        assert isinstance(g, PDOptionalContentGroup)


def test_get_groups_empty_when_state_is_only_preambles() -> None:
    """A /State carrying only preamble names — malformed but possible —
    yields an empty groups list."""
    action = PDActionSetOCGState()
    action.set_state(COSArray([_ON, _OFF]))
    assert action.get_groups() == []
