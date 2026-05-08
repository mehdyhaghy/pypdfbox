from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI, PDAdditionalActions


def _uri(value: str) -> PDActionURI:
    action = PDActionURI()
    action.set_uri(value)
    return action


def test_trigger_constant_matches_pdf_key() -> None:
    assert COSName.get_pdf_name("F") == PDAdditionalActions.TRIGGER_F


def test_f_action_round_trips_as_typed_action() -> None:
    aa = PDAdditionalActions()

    aa.set_f(_uri("https://example.test/f"))

    action = aa.get_f()
    assert isinstance(action, PDActionURI)
    assert action.get_uri() == "https://example.test/f"


def test_set_f_none_removes_entry() -> None:
    aa = PDAdditionalActions()
    aa.set_f(_uri("https://example.test/f"))
    assert aa.get_cos_object().get_dictionary_object(PDAdditionalActions.TRIGGER_F) is not None

    aa.set_f(None)

    assert aa.get_cos_object().get_dictionary_object(PDAdditionalActions.TRIGGER_F) is None
    assert aa.get_f() is None


def test_get_f_returns_none_when_entry_is_not_a_dictionary() -> None:
    aa = PDAdditionalActions()
    aa.get_cos_object().set_name(PDAdditionalActions.TRIGGER_F, "Bogus")

    assert aa.get_f() is None


def test_constructor_wraps_existing_dictionary() -> None:
    seed = COSDictionary()
    action = _uri("https://example.test/seed")
    seed.set_item(PDAdditionalActions.TRIGGER_F, action.get_cos_object())

    aa = PDAdditionalActions(seed)

    assert aa.get_cos_object() is seed
    resolved = aa.get_f()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/seed"
