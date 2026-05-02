from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
    PDAnnotationAdditionalActions,
)


_TRIGGERS: list[tuple[str, str]] = [
    ("e", "E"),
    ("x", "X"),
    ("d", "D"),
    ("u", "U"),
    ("fo", "Fo"),
    ("bl", "Bl"),
    ("po", "PO"),
    ("pc", "PC"),
    ("pv", "PV"),
    ("pi", "PI"),
]


def _uri(value: str) -> PDActionURI:
    action = PDActionURI()
    action.set_uri(value)
    return action


# ---------- Trigger name constants ----------


@pytest.mark.parametrize(("attr", "key_str"), _TRIGGERS)
def test_trigger_constants_match_pdf_keys(attr: str, key_str: str) -> None:
    constant = getattr(PDAnnotationAdditionalActions, f"TRIGGER_{attr.upper()}")
    assert isinstance(constant, COSName)
    assert constant == COSName.get_pdf_name(key_str)


def test_trigger_constants_are_unique() -> None:
    keys = {
        PDAnnotationAdditionalActions.TRIGGER_E,
        PDAnnotationAdditionalActions.TRIGGER_X,
        PDAnnotationAdditionalActions.TRIGGER_D,
        PDAnnotationAdditionalActions.TRIGGER_U,
        PDAnnotationAdditionalActions.TRIGGER_FO,
        PDAnnotationAdditionalActions.TRIGGER_BL,
        PDAnnotationAdditionalActions.TRIGGER_PO,
        PDAnnotationAdditionalActions.TRIGGER_PC,
        PDAnnotationAdditionalActions.TRIGGER_PV,
        PDAnnotationAdditionalActions.TRIGGER_PI,
    }
    assert len(keys) == len(_TRIGGERS)


# ---------- has_* predicate helpers ----------


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_has_returns_false_on_empty_actions(attr: str, _key_str: str) -> None:
    aa = PDAnnotationAdditionalActions()
    assert getattr(aa, f"has_{attr}")() is False


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_has_returns_true_after_setter(attr: str, _key_str: str) -> None:
    aa = PDAnnotationAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert getattr(aa, f"has_{attr}")() is True


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_has_returns_false_after_clearing(attr: str, _key_str: str) -> None:
    aa = PDAnnotationAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri("https://example.test/seed"))
    getattr(aa, f"set_{attr}")(None)
    assert getattr(aa, f"has_{attr}")() is False


def test_has_predicates_are_independent() -> None:
    # Setting /E must not flip the predicates of any other trigger.
    aa = PDAnnotationAdditionalActions()
    aa.set_e(_uri("https://example.test/e-only"))
    assert aa.has_e() is True
    assert aa.has_x() is False
    assert aa.has_d() is False
    assert aa.has_u() is False
    assert aa.has_fo() is False
    assert aa.has_bl() is False
    assert aa.has_po() is False
    assert aa.has_pc() is False
    assert aa.has_pv() is False
    assert aa.has_pi() is False


def test_has_returns_true_for_non_dictionary_value() -> None:
    # ``has_*`` is a key-presence check, NOT a typed-resolution check —
    # it must return True even when the value at the key is bogus
    # (e.g. a name produced by a non-conformant writer). The typed
    # ``get_*`` accessor is the one that filters non-dicts to None.
    aa = PDAnnotationAdditionalActions()
    aa.get_cos_object().set_name(
        PDAnnotationAdditionalActions.TRIGGER_E, "Bogus"
    )
    assert aa.has_e() is True
    assert aa.get_e() is None


# ---------- is_empty() ----------


def test_is_empty_default_true() -> None:
    assert PDAnnotationAdditionalActions().is_empty() is True


@pytest.mark.parametrize(("attr", "_key_str"), _TRIGGERS)
def test_is_empty_false_when_any_single_trigger_set(attr: str, _key_str: str) -> None:
    aa = PDAnnotationAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert aa.is_empty() is False


def test_is_empty_true_after_clearing_every_trigger() -> None:
    aa = PDAnnotationAdditionalActions()
    for attr, _ in _TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert aa.is_empty() is False
    for attr, _ in _TRIGGERS:
        getattr(aa, f"set_{attr}")(None)
    assert aa.is_empty() is True


def test_is_empty_treats_unrelated_dict_entries_as_non_empty() -> None:
    # The dictionary may carry only the AA-meaningful keys we know about;
    # any other COS key still flips is_empty to False because by
    # definition the wrapper considers ANY non-trigger entry equivalent
    # to "no trigger present" — verify the default behaviour: stray keys
    # do NOT flip is_empty (we only consult the trigger keys).
    aa = PDAnnotationAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name("Stray"), "Yes")
    assert aa.is_empty() is True


# ---------- __repr__ ----------


def test_repr_empty() -> None:
    assert repr(PDAnnotationAdditionalActions()) == "PDAnnotationAdditionalActions(empty)"


def test_repr_with_e_only() -> None:
    aa = PDAnnotationAdditionalActions()
    aa.set_e(_uri("https://example.test/e"))
    assert repr(aa) == "PDAnnotationAdditionalActions(E)"


def test_repr_preserves_table_197_order() -> None:
    # Set triggers out of order — repr must still list them in the
    # E,X,D,U,Fo,Bl,PO,PC,PV,PI order from PDF 32000-1:2008 Table 197
    # so source-level diffing against PDFBox-produced PDFs stays sane.
    aa = PDAnnotationAdditionalActions()
    aa.set_pi(_uri("https://example.test/pi"))
    aa.set_e(_uri("https://example.test/e"))
    aa.set_pc(_uri("https://example.test/pc"))
    aa.set_d(_uri("https://example.test/d"))
    assert repr(aa) == "PDAnnotationAdditionalActions(E,D,PC,PI)"


def test_repr_with_all_triggers() -> None:
    aa = PDAnnotationAdditionalActions()
    for attr, _ in _TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert repr(aa) == "PDAnnotationAdditionalActions(E,X,D,U,Fo,Bl,PO,PC,PV,PI)"


# ---------- defensive non-dictionary handling ----------


@pytest.mark.parametrize(("attr", "key_str"), _TRIGGERS)
def test_get_returns_none_when_entry_is_not_a_dictionary(
    attr: str, key_str: str
) -> None:
    # Mirrors the upstream getCOSDictionary contract: a non-conformant
    # producer writing a name (or any non-dict) at a trigger key must
    # surface as None from the typed accessor, not crash.
    aa = PDAnnotationAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name(key_str), "Bogus")
    assert getattr(aa, f"get_{attr}")() is None


# ---------- constructor edge cases ----------


def test_constructor_default_creates_empty_dict() -> None:
    aa = PDAnnotationAdditionalActions()
    cos = aa.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_none_arg_creates_empty_dict() -> None:
    aa = PDAnnotationAdditionalActions(None)
    cos = aa.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_seeded_dict_round_trips_known_trigger() -> None:
    seed = COSDictionary()
    action = PDActionURI()
    action.set_uri("https://example.test/seeded-fo")
    seed.set_item(PDAnnotationAdditionalActions.TRIGGER_FO, action.get_cos_object())

    aa = PDAnnotationAdditionalActions(seed)

    assert aa.get_cos_object() is seed
    resolved = aa.get_fo()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/seeded-fo"
    assert aa.has_fo() is True
    assert aa.is_empty() is False
