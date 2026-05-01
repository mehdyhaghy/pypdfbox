from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import (
    PDActionNamed,
    PDActionURI,
    PDPageAdditionalActions,
)

_TRIGGERS = [
    ("o", "O", "https://example.test/o"),
    ("c", "C", "https://example.test/c"),
]


def test_page_additional_actions_open_close_round_trip() -> None:
    actions = PDPageAdditionalActions()
    open_action = PDActionURI()
    open_action.set_uri("https://example.test/open")
    close_action = PDActionNamed()
    close_action.set_n("NextPage")

    actions.set_o(open_action)
    actions.set_c(close_action)

    resolved_open = actions.get_o()
    assert isinstance(resolved_open, PDActionURI)
    assert resolved_open.get_uri() == "https://example.test/open"

    resolved_close = actions.get_c()
    assert isinstance(resolved_close, PDActionNamed)
    assert resolved_close.get_n() == "NextPage"


@pytest.mark.parametrize(("attr", "key", "uri"), _TRIGGERS)
def test_page_additional_actions_set_none_removes(
    attr: str, key: str, uri: str
) -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri(uri)
    getattr(aa, f"set_{attr}")(action)
    assert getattr(aa, f"get_{attr}")() is not None

    getattr(aa, f"set_{attr}")(None)

    assert getattr(aa, f"get_{attr}")() is None
    assert not aa.get_cos_object().contains_key(COSName.get_pdf_name(key))


def test_page_additional_actions_default_dict_is_empty() -> None:
    aa = PDPageAdditionalActions()
    cos = aa.get_cos_object()
    assert cos.size() == 0
    assert aa.get_o() is None
    assert aa.get_c() is None


def test_page_additional_actions_wraps_existing_dict() -> None:
    aa1 = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/wrap")
    aa1.set_o(action)

    # Re-wrap the same COSDictionary; should observe the same /O entry and
    # share identity at the COS layer.
    aa2 = PDPageAdditionalActions(aa1.get_cos_object())
    assert aa2.get_cos_object() is aa1.get_cos_object()
    resolved = aa2.get_o()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/wrap"


def test_page_set_open_action_alias_set_none_removes() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/open-alias-remove")
    aa.set_open_action(action)
    assert aa.get_open_action() is not None

    aa.set_open_action(None)

    assert aa.get_open_action() is None
    assert aa.get_o() is None
    assert not aa.get_cos_object().contains_key(COSName.get_pdf_name("O"))


def test_page_set_close_action_alias_set_none_removes() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/close-alias-remove")
    aa.set_close_action(action)
    assert aa.get_close_action() is not None

    aa.set_close_action(None)

    assert aa.get_close_action() is None
    assert aa.get_c() is None
    assert not aa.get_cos_object().contains_key(COSName.get_pdf_name("C"))


@pytest.mark.parametrize("key_str", ["O", "C"])
def test_page_get_returns_none_when_entry_is_not_a_dictionary(key_str: str) -> None:
    # Defensively, when the additional-actions dict carries a non-dictionary
    # value at /O or /C (malformed producer), the typed accessor must return
    # None rather than raise. Mirrors the upstream getCOSDictionary contract,
    # which silently yields null for non-dict resolved values.
    aa = PDPageAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name(key_str), "Bogus")

    assert aa.get_o() is None if key_str == "O" else aa.get_c() is None


def test_page_additional_actions_constructor_default_creates_empty_dict() -> None:
    aa = PDPageAdditionalActions()
    cos = aa.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_page_additional_actions_constructor_accepts_seeded_dict() -> None:
    seed = COSDictionary()
    action = PDActionURI()
    action.set_uri("https://example.test/seeded")
    seed.set_item(COSName.get_pdf_name("O"), action.get_cos_object())

    aa = PDPageAdditionalActions(seed)

    assert aa.get_cos_object() is seed
    resolved = aa.get_o()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/seeded"


# ---------- introspection helpers ----------


def test_page_additional_actions_is_empty_default_true() -> None:
    aa = PDPageAdditionalActions()
    assert aa.is_empty() is True


def test_page_additional_actions_is_empty_false_when_o_set() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/o")
    aa.set_o(action)
    assert aa.is_empty() is False


def test_page_additional_actions_is_empty_false_when_c_set() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/c")
    aa.set_c(action)
    assert aa.is_empty() is False


def test_page_additional_actions_is_empty_true_after_clearing_both() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/o")
    aa.set_o(action)
    aa.set_c(action)
    assert aa.is_empty() is False
    aa.set_o(None)
    aa.set_c(None)
    assert aa.is_empty() is True


def test_page_additional_actions_repr_empty() -> None:
    assert repr(PDPageAdditionalActions()) == "PDPageAdditionalActions(empty)"


def test_page_additional_actions_repr_with_o_only() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/o")
    aa.set_o(action)
    assert repr(aa) == "PDPageAdditionalActions(O)"


def test_page_additional_actions_repr_with_c_only() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/c")
    aa.set_c(action)
    assert repr(aa) == "PDPageAdditionalActions(C)"


def test_page_additional_actions_repr_with_both() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/x")
    aa.set_o(action)
    aa.set_c(action)
    assert repr(aa) == "PDPageAdditionalActions(O,C)"
