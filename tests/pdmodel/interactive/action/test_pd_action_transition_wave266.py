"""Wave 266 round-out tests for :class:`PDActionTransition`.

Covers the round-out surface added in wave 266:

- ``set_trans`` accepting raw :class:`COSDictionary`
- ``has_trans`` / ``clear_trans`` / ``is_empty`` / ``is_valid`` predicates
- defaulting of ``/Type`` and ``/S`` on construction
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_transition import (
    PDActionTransition,
)
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition_style import (
    PDTransitionStyle,
)

_TRANS: COSName = COSName.get_pdf_name("Trans")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_S: COSName = COSName.get_pdf_name("S")


# ---- SUB_TYPE / construction ----------------------------------------------


def test_sub_type_constant_is_trans() -> None:
    assert PDActionTransition.SUB_TYPE == "Trans"


def test_default_constructor_sets_type_action_and_s_trans() -> None:
    action = PDActionTransition()
    assert action.get_cos_object().get_name(_TYPE) == "Action"
    assert action.get_cos_object().get_name(_S) == "Trans"
    assert action.get_sub_type() == PDActionTransition.SUB_TYPE


def test_dict_constructor_preserves_existing_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "OtherSub")
    action = PDActionTransition(raw)
    assert action.get_sub_type() == "OtherSub"


# ---- set_trans accepts raw COSDictionary ----------------------------------


def test_set_trans_accepts_pd_transition() -> None:
    action = PDActionTransition()
    trans = PDTransition(style=PDTransitionStyle.SPLIT)
    action.set_trans(trans)

    resolved = action.get_trans()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == PDTransitionStyle.SPLIT


def test_set_trans_accepts_raw_cos_dictionary() -> None:
    """Round-tripping a raw ``COSDictionary`` works for callers carrying
    a hand-built transition dict."""
    action = PDActionTransition()
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), PDTransitionStyle.WIPE)
    action.set_trans(raw)

    assert action.get_cos_object().get_dictionary_object(_TRANS) is raw

    resolved = action.get_trans()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == PDTransitionStyle.WIPE


def test_set_trans_none_removes_entry() -> None:
    action = PDActionTransition()
    action.set_trans(PDTransition(style=PDTransitionStyle.SPLIT))
    assert action.has_trans() is True

    action.set_trans(None)
    assert action.has_trans() is False
    assert action.get_trans() is None


# ---- has_trans / clear_trans / is_empty / is_valid ------------------------


def test_has_trans_false_when_absent() -> None:
    action = PDActionTransition()
    assert action.has_trans() is False


def test_has_trans_true_after_set() -> None:
    action = PDActionTransition()
    action.set_trans(PDTransition(style=PDTransitionStyle.BLINDS))
    assert action.has_trans() is True


def test_clear_trans_removes_entry() -> None:
    action = PDActionTransition()
    action.set_trans(PDTransition(style=PDTransitionStyle.BOX))
    assert action.has_trans() is True

    action.clear_trans()
    assert action.has_trans() is False
    assert action.get_trans() is None


def test_clear_trans_idempotent_when_absent() -> None:
    action = PDActionTransition()
    action.clear_trans()  # no-op
    assert action.has_trans() is False


def test_is_empty_true_for_fresh_action() -> None:
    action = PDActionTransition()
    assert action.is_empty() is True


def test_is_empty_false_when_trans_set() -> None:
    action = PDActionTransition()
    action.set_trans(PDTransition(style=PDTransitionStyle.COVER))
    assert action.is_empty() is False


def test_is_empty_true_after_clearing_trans() -> None:
    action = PDActionTransition()
    action.set_trans(PDTransition(style=PDTransitionStyle.GLITTER))
    action.clear_trans()
    assert action.is_empty() is True


def test_is_valid_true_for_fresh_action() -> None:
    action = PDActionTransition()
    assert action.is_valid() is True


def test_is_valid_false_when_subtype_overridden() -> None:
    action = PDActionTransition()
    action.set_sub_type("GoTo")
    assert action.is_valid() is False
