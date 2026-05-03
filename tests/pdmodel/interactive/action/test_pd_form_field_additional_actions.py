"""Wave 227: parity-style helpers on PDFormFieldAdditionalActions.

These cover the new ``TRIGGER_*`` constants, the ``has_*`` predicate
helpers, ``is_empty`` and ``__repr__`` introspection — mirroring the
shape of the existing PDAnnotationAdditionalActions / PDPageAdditionalActions
test suites so producers iterating across many form fields share a
consistent surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_form_field_additional_actions import (
    PDFormFieldAdditionalActions,
)

_TRIGGERS: list[tuple[str, str]] = [
    ("k", "K"),
    ("f", "F"),
    ("v", "V"),
    ("c", "C"),
]


def _uri(value: str) -> PDActionURI:
    action = PDActionURI()
    action.set_uri(value)
    return action


# ---------- Trigger name constants ----------


@pytest.mark.parametrize(("attr", "key_str"), _TRIGGERS)
def test_trigger_constants_match_pdf_keys(attr: str, key_str: str) -> None:
    constant = getattr(PDFormFieldAdditionalActions, f"TRIGGER_{attr.upper()}")
    assert isinstance(constant, COSName)
    assert constant == COSName.get_pdf_name(key_str)


def test_trigger_constants_are_unique() -> None:
    keys = {
        PDFormFieldAdditionalActions.TRIGGER_K,
        PDFormFieldAdditionalActions.TRIGGER_F,
        PDFormFieldAdditionalActions.TRIGGER_V,
        PDFormFieldAdditionalActions.TRIGGER_C,
    }
    assert len(keys) == len(_TRIGGERS)


# ---------- has_* predicate helpers ----------


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_has_returns_false_on_empty_actions(attr: str, _key_str: str) -> None:
    aa = PDFormFieldAdditionalActions()
    assert getattr(aa, f"has_{attr}")() is False


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_has_returns_true_after_setter(attr: str, _key_str: str) -> None:
    aa = PDFormFieldAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert getattr(aa, f"has_{attr}")() is True


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_has_returns_false_after_clearing(attr: str, _key_str: str) -> None:
    aa = PDFormFieldAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri("https://example.test/seed"))
    getattr(aa, f"set_{attr}")(None)
    assert getattr(aa, f"has_{attr}")() is False


def test_has_predicates_are_independent() -> None:
    # Setting /K must not flip the predicates of any other trigger.
    aa = PDFormFieldAdditionalActions()
    aa.set_k(_uri("https://example.test/k-only"))
    assert aa.has_k() is True
    assert aa.has_f() is False
    assert aa.has_v() is False
    assert aa.has_c() is False


def test_has_returns_true_for_non_dictionary_value() -> None:
    # ``has_*`` is a key-presence check, NOT a typed-resolution check —
    # it must return True even when the value at the key is bogus
    # (e.g. a name produced by a non-conformant writer). The typed
    # ``get_*`` accessor is the one that filters non-dicts to None.
    aa = PDFormFieldAdditionalActions()
    aa.get_cos_object().set_name(
        PDFormFieldAdditionalActions.TRIGGER_K, "Bogus"
    )
    assert aa.has_k() is True
    assert aa.get_k() is None


# ---------- is_empty() ----------


def test_is_empty_default_true() -> None:
    assert PDFormFieldAdditionalActions().is_empty() is True


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_is_empty_false_when_any_single_trigger_set(attr: str, _key_str: str) -> None:
    aa = PDFormFieldAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert aa.is_empty() is False


def test_is_empty_true_after_clearing_every_trigger() -> None:
    aa = PDFormFieldAdditionalActions()
    for attr, _ in _TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert aa.is_empty() is False
    for attr, _ in _TRIGGERS:
        getattr(aa, f"set_{attr}")(None)
    assert aa.is_empty() is True


def test_is_empty_treats_unrelated_dict_entries_as_non_empty() -> None:
    # The wrapper considers only the four trigger keys; stray COS keys
    # (a non-conformant writer dropping unrelated metadata into the AA
    # dictionary) do NOT flip is_empty to False.
    aa = PDFormFieldAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name("Stray"), "Yes")
    assert aa.is_empty() is True


# ---------- __repr__ ----------


def test_repr_empty() -> None:
    assert repr(PDFormFieldAdditionalActions()) == "PDFormFieldAdditionalActions(empty)"


def test_repr_with_k_only() -> None:
    aa = PDFormFieldAdditionalActions()
    aa.set_k(_uri("https://example.test/k"))
    assert repr(aa) == "PDFormFieldAdditionalActions(K)"


def test_repr_preserves_table_196_order() -> None:
    # Set triggers out of order — repr must still list them in the
    # K,F,V,C order from PDF 32000-1:2008 Table 196 so source-level
    # diffing against PDFBox-produced PDFs stays sane.
    aa = PDFormFieldAdditionalActions()
    aa.set_c(_uri("https://example.test/c"))
    aa.set_k(_uri("https://example.test/k"))
    aa.set_v(_uri("https://example.test/v"))
    aa.set_f(_uri("https://example.test/f"))
    assert repr(aa) == "PDFormFieldAdditionalActions(K,F,V,C)"


def test_repr_with_all_triggers() -> None:
    aa = PDFormFieldAdditionalActions()
    for attr, _ in _TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert repr(aa) == "PDFormFieldAdditionalActions(K,F,V,C)"


# ---------- defensive non-dictionary handling ----------


@pytest.mark.parametrize(("attr", "key_str"), _TRIGGERS)
def test_get_returns_none_when_entry_is_not_a_dictionary(
    attr: str, key_str: str
) -> None:
    # Mirrors the upstream getCOSDictionary contract: a non-conformant
    # producer writing a name (or any non-dict) at a trigger key must
    # surface as None from the typed accessor, not crash.
    aa = PDFormFieldAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name(key_str), "Bogus")
    assert getattr(aa, f"get_{attr}")() is None


# ---------- constructor edge cases ----------


def test_constructor_default_creates_empty_dict() -> None:
    aa = PDFormFieldAdditionalActions()
    cos = aa.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_none_arg_creates_empty_dict() -> None:
    aa = PDFormFieldAdditionalActions(None)
    cos = aa.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_seeded_dict_round_trips_known_trigger() -> None:
    seed = COSDictionary()
    action = PDActionURI()
    action.set_uri("https://example.test/seeded-v")
    seed.set_item(PDFormFieldAdditionalActions.TRIGGER_V, action.get_cos_object())

    aa = PDFormFieldAdditionalActions(seed)

    assert aa.get_cos_object() is seed
    resolved = aa.get_v()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/seeded-v"
    assert aa.has_v() is True
    assert aa.is_empty() is False
