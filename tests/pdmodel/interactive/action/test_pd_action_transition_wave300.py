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


def test_transition_alias_round_trips_pd_transition() -> None:
    action = PDActionTransition()
    transition = PDTransition(style=PDTransitionStyle.FADE)

    action.set_transition(transition)

    resolved = action.get_transition()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == PDTransitionStyle.FADE
    assert action.get_trans() is not None


def test_transition_alias_accepts_raw_dictionary() -> None:
    action = PDActionTransition()
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), PDTransitionStyle.PUSH)

    action.set_transition(raw)

    assert action.get_cos_object().get_dictionary_object(_TRANS) is raw
    resolved = action.get_transition()
    assert isinstance(resolved, PDTransition)
    assert resolved.get_style() == PDTransitionStyle.PUSH


def test_transition_alias_none_removes_entry() -> None:
    action = PDActionTransition()
    action.set_transition(PDTransition(style=PDTransitionStyle.WIPE))
    assert action.has_trans() is True

    action.set_transition(None)

    assert action.has_trans() is False
    assert action.get_transition() is None
