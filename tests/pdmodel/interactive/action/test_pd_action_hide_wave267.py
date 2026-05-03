"""Wave 267 round-out tests for :class:`PDActionHide`.

Cover the predicate / clear / validation surface added in wave 267:
``has_target``, ``has_hide_flag``, ``clear_target``, ``clear_hide_flag``,
``is_empty``, ``is_valid``, plus the ``SUB_TYPE`` constant and the
default ``/Type /Action`` and ``/S /Hide`` boilerplate written on
construction."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)


_H: COSName = COSName.get_pdf_name("H")
_S: COSName = COSName.get_pdf_name("S")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_T: COSName = COSName.T  # type: ignore[attr-defined]
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


# ---------- SUB_TYPE constant + construction defaults ----------


def test_sub_type_constant_value() -> None:
    assert PDActionHide.SUB_TYPE == "Hide"


def test_default_construction_writes_type_and_subtype() -> None:
    action = PDActionHide()
    cos = action.get_cos_object()
    assert cos.get_name(_TYPE) == "Action"
    assert cos.get_name(_S) == "Hide"


def test_wrapping_existing_dict_does_not_overwrite_subtype() -> None:
    """Constructing around a pre-existing dictionary must leave its /S
    entry alone — the wrapper does not stamp the default sub-type when
    a dictionary is passed in."""
    raw = COSDictionary()
    raw.set_name(_S, "Hide")
    raw.set_string(_T, "ExistingField")
    action = PDActionHide(raw)
    assert action.get_cos_object() is raw
    assert action.get_sub_type() == "Hide"
    assert action.get_target_names() == ["ExistingField"]


# ---------- has_target ----------


def test_has_target_false_on_fresh_action() -> None:
    assert PDActionHide().has_target() is False


def test_has_target_true_for_string_form() -> None:
    action = PDActionHide()
    action.set_target_names(["F1"])
    assert action.has_target() is True


def test_has_target_true_for_array_form() -> None:
    action = PDActionHide()
    array = COSArray()
    array.add(COSString("F1"))
    array.add(COSString("F2"))
    action.set_target(array)
    assert action.has_target() is True


def test_has_target_true_for_annotation_dict_form() -> None:
    action = PDActionHide()
    action.set_annotation(PDAnnotationWidget())
    assert action.has_target() is True


def test_has_target_false_after_clear() -> None:
    action = PDActionHide()
    action.set_target_names(["F1"])
    assert action.has_target() is True
    action.clear_target()
    assert action.has_target() is False
    assert action.get_target() is None


# ---------- has_hide_flag ----------


def test_has_hide_flag_false_on_fresh_action() -> None:
    """A freshly constructed action has no /H entry — the effective
    value defaults to True via the spec, but the entry itself is absent."""
    action = PDActionHide()
    assert action.has_hide_flag() is False
    # The effective value is still True via the default.
    assert action.is_hide() is True


def test_has_hide_flag_true_after_set_h_true() -> None:
    action = PDActionHide()
    action.set_h(True)
    assert action.has_hide_flag() is True


def test_has_hide_flag_true_after_set_h_false() -> None:
    """Even an explicit /H false counts as the entry being present —
    has_hide_flag is independent of the boolean value."""
    action = PDActionHide()
    action.set_h(False)
    assert action.has_hide_flag() is True
    assert action.is_hide() is False


def test_has_hide_flag_distinct_from_is_hide_for_default_case() -> None:
    """The point of has_hide_flag: it lets callers tell apart
    "/H absent (default True)" from "/H true written explicitly"."""
    action = PDActionHide()
    assert action.is_hide() is True
    assert action.has_hide_flag() is False  # absent

    action.set_h(True)
    assert action.is_hide() is True
    assert action.has_hide_flag() is True  # now written explicitly


# ---------- clear_target / clear_hide_flag ----------


def test_clear_target_on_fresh_action_is_noop() -> None:
    action = PDActionHide()
    action.clear_target()
    assert action.get_target() is None
    assert action.has_target() is False


def test_clear_hide_flag_resets_to_default() -> None:
    action = PDActionHide()
    action.set_h(False)
    assert action.is_hide() is False
    action.clear_hide_flag()
    assert action.has_hide_flag() is False
    # /H now absent ⇒ defaults back to True.
    assert action.is_hide() is True


def test_clear_hide_flag_idempotent() -> None:
    action = PDActionHide()
    action.clear_hide_flag()
    action.clear_hide_flag()
    assert action.has_hide_flag() is False


# ---------- is_empty ----------


def test_is_empty_true_on_fresh_action() -> None:
    """A freshly constructed PDActionHide carries only /Type and /S
    boilerplate — no /T, no /H — so it reports empty."""
    action = PDActionHide()
    assert action.is_empty() is True


def test_is_empty_false_after_set_target() -> None:
    action = PDActionHide()
    action.set_target_names(["F1"])
    assert action.is_empty() is False


def test_is_empty_false_after_set_h() -> None:
    action = PDActionHide()
    action.set_h(False)
    assert action.is_empty() is False


def test_is_empty_true_after_clearing_both() -> None:
    action = PDActionHide()
    action.set_target_names(["F1"])
    action.set_h(False)
    assert action.is_empty() is False

    action.clear_target()
    action.clear_hide_flag()
    assert action.is_empty() is True


# ---------- is_valid ----------


def test_is_valid_true_for_fresh_action() -> None:
    assert PDActionHide().is_valid() is True


def test_is_valid_true_after_factory_dispatch() -> None:
    """A round-trip through :meth:`PDAction.create` preserves /S and
    therefore the validity flag."""
    action = PDActionHide()
    action.set_target_names(["F1"])
    parsed = PDAction.create(action.get_cos_object())
    assert isinstance(parsed, PDActionHide)
    assert parsed.is_valid() is True


def test_is_valid_false_when_subtype_mismatched() -> None:
    """If a caller constructs the wrapper around a dictionary whose /S
    is something other than /Hide, the validity check flags it."""
    raw = COSDictionary()
    raw.set_name(_S, "URI")
    action = PDActionHide(raw)
    assert action.is_valid() is False


def test_is_valid_false_when_subtype_missing() -> None:
    raw = COSDictionary()
    # No /S entry at all.
    action = PDActionHide(raw)
    assert action.is_valid() is False


# ---------- explicit COSBoolean round-trip ----------


def test_has_hide_flag_true_for_explicit_cos_boolean_false() -> None:
    """Storing the COSBoolean directly via the underlying dictionary
    still registers as /H present."""
    action = PDActionHide()
    action.get_cos_object().set_item(_H, COSBoolean.FALSE)
    assert action.has_hide_flag() is True
    assert action.is_hide() is False
