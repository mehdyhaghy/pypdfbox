from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_document_catalog_additional_actions import (
    PDDocumentCatalogAdditionalActions,
)


def _uri(value: str) -> PDActionURI:
    action = PDActionURI()
    action.set_uri(value)
    return action

_TRIGGERS = [
    ("wc", "WC", "https://example.test/wc"),
    ("ws", "WS", "https://example.test/ws"),
    ("ds", "DS", "https://example.test/ds"),
    ("wp", "WP", "https://example.test/wp"),
    ("dp", "DP", "https://example.test/dp"),
]


@pytest.mark.parametrize(("attr", "key", "uri"), _TRIGGERS)
def test_document_catalog_additional_actions_round_trip(
    attr: str, key: str, uri: str
) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    action = PDActionURI()
    action.set_uri(uri)

    getattr(aa, f"set_{attr}")(action)

    resolved = getattr(aa, f"get_{attr}")()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == uri
    # Underlying dict actually carries the entry under the upstream name.
    assert aa.get_cos_object().contains_key(COSName.get_pdf_name(key))


@pytest.mark.parametrize(("attr", "key", "uri"), _TRIGGERS)
def test_document_catalog_additional_actions_set_none_removes(
    attr: str, key: str, uri: str
) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    action = PDActionURI()
    action.set_uri(uri)
    getattr(aa, f"set_{attr}")(action)
    assert getattr(aa, f"get_{attr}")() is not None

    getattr(aa, f"set_{attr}")(None)

    assert getattr(aa, f"get_{attr}")() is None
    assert not aa.get_cos_object().contains_key(COSName.get_pdf_name(key))


def test_document_catalog_additional_actions_default_dict_is_empty() -> None:
    aa = PDDocumentCatalogAdditionalActions()
    cos = aa.get_cos_object()
    assert cos.size() == 0
    assert aa.get_wc() is None
    assert aa.get_ws() is None
    assert aa.get_ds() is None
    assert aa.get_wp() is None
    assert aa.get_dp() is None


def test_document_catalog_additional_actions_wraps_existing_dict() -> None:
    aa1 = PDDocumentCatalogAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/wc")
    aa1.set_wc(action)

    # Re-wrap the same COSDictionary; should observe the same /WC entry.
    aa2 = PDDocumentCatalogAdditionalActions(aa1.get_cos_object())
    resolved = aa2.get_wc()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/wc"


_CATALOG_ALIASES = [
    ("wc", "will_close", "WC"),
    ("ws", "will_save", "WS"),
    ("ds", "did_save", "DS"),
    ("wp", "will_print", "WP"),
    ("dp", "did_print", "DP"),
]


@pytest.mark.parametrize(("short", "alias", "key"), _CATALOG_ALIASES)
def test_document_catalog_alias_set_none_removes_entry(
    short: str, alias: str, key: str
) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    action = PDActionURI()
    action.set_uri(f"https://example.test/{alias}-remove")
    getattr(aa, f"set_{alias}")(action)
    assert getattr(aa, f"get_{alias}")() is not None

    getattr(aa, f"set_{alias}")(None)

    assert getattr(aa, f"get_{alias}")() is None
    assert getattr(aa, f"get_{short}")() is None
    assert not aa.get_cos_object().contains_key(COSName.get_pdf_name(key))


@pytest.mark.parametrize(("attr", "key"), [(t[0], t[1]) for t in _TRIGGERS])
def test_document_catalog_get_returns_none_when_entry_is_not_a_dictionary(
    attr: str, key: str
) -> None:
    # Defensively, when a malformed producer leaves a non-dictionary value at
    # /WC etc., the typed accessor must return None rather than raise.
    aa = PDDocumentCatalogAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name(key), "Bogus")

    assert getattr(aa, f"get_{attr}")() is None


# ----------------------------------------------------------------------
# Wave 227: parity-style helpers (TRIGGER_* constants, has_* predicates,
# is_empty, __repr__) mirroring PDAnnotationAdditionalActions.
# ----------------------------------------------------------------------


_HAS_TRIGGERS: list[tuple[str, str]] = [(t[0], t[1]) for t in _TRIGGERS]


# ---------- Trigger name constants ----------


@pytest.mark.parametrize(("attr", "key_str"), _HAS_TRIGGERS)
def test_trigger_constants_match_pdf_keys(attr: str, key_str: str) -> None:
    constant = getattr(PDDocumentCatalogAdditionalActions, f"TRIGGER_{attr.upper()}")
    assert isinstance(constant, COSName)
    assert constant == COSName.get_pdf_name(key_str)


def test_trigger_constants_are_unique() -> None:
    keys = {
        PDDocumentCatalogAdditionalActions.TRIGGER_WC,
        PDDocumentCatalogAdditionalActions.TRIGGER_WS,
        PDDocumentCatalogAdditionalActions.TRIGGER_DS,
        PDDocumentCatalogAdditionalActions.TRIGGER_WP,
        PDDocumentCatalogAdditionalActions.TRIGGER_DP,
    }
    assert len(keys) == len(_HAS_TRIGGERS)


# ---------- has_* predicate helpers ----------


@pytest.mark.parametrize(("attr", "_key_str"), _HAS_TRIGGERS)
def test_has_returns_false_on_empty_actions(attr: str, _key_str: str) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    assert getattr(aa, f"has_{attr}")() is False


@pytest.mark.parametrize(("attr", "_key_str"), _HAS_TRIGGERS)
def test_has_returns_true_after_setter(attr: str, _key_str: str) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert getattr(aa, f"has_{attr}")() is True


@pytest.mark.parametrize(("attr", "_key_str"), _HAS_TRIGGERS)
def test_has_returns_false_after_clearing(attr: str, _key_str: str) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri("https://example.test/seed"))
    getattr(aa, f"set_{attr}")(None)
    assert getattr(aa, f"has_{attr}")() is False


def test_has_predicates_are_independent() -> None:
    # Setting /WC must not flip the predicates of any other trigger.
    aa = PDDocumentCatalogAdditionalActions()
    aa.set_wc(_uri("https://example.test/wc-only"))
    assert aa.has_wc() is True
    assert aa.has_ws() is False
    assert aa.has_ds() is False
    assert aa.has_wp() is False
    assert aa.has_dp() is False


def test_has_returns_true_for_non_dictionary_value() -> None:
    # Key-presence check, NOT a typed-resolution check.
    aa = PDDocumentCatalogAdditionalActions()
    aa.get_cos_object().set_name(
        PDDocumentCatalogAdditionalActions.TRIGGER_WC, "Bogus"
    )
    assert aa.has_wc() is True
    assert aa.get_wc() is None


# ---------- is_empty() ----------


def test_is_empty_default_true() -> None:
    assert PDDocumentCatalogAdditionalActions().is_empty() is True


@pytest.mark.parametrize(("attr", "_key_str"), _HAS_TRIGGERS)
def test_is_empty_false_when_any_single_trigger_set(attr: str, _key_str: str) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert aa.is_empty() is False


def test_is_empty_true_after_clearing_every_trigger() -> None:
    aa = PDDocumentCatalogAdditionalActions()
    for attr, _ in _HAS_TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert aa.is_empty() is False
    for attr, _ in _HAS_TRIGGERS:
        getattr(aa, f"set_{attr}")(None)
    assert aa.is_empty() is True


def test_is_empty_treats_unrelated_dict_entries_as_non_empty() -> None:
    aa = PDDocumentCatalogAdditionalActions()
    aa.get_cos_object().set_name(COSName.get_pdf_name("Stray"), "Yes")
    assert aa.is_empty() is True


# ---------- __repr__ ----------


def test_repr_empty() -> None:
    assert (
        repr(PDDocumentCatalogAdditionalActions())
        == "PDDocumentCatalogAdditionalActions(empty)"
    )


def test_repr_with_wc_only() -> None:
    aa = PDDocumentCatalogAdditionalActions()
    aa.set_wc(_uri("https://example.test/wc"))
    assert repr(aa) == "PDDocumentCatalogAdditionalActions(WC)"


def test_repr_preserves_table_195_order() -> None:
    # Set triggers out of order — repr must still list them in the
    # WC,WS,DS,WP,DP order from PDF 32000-1:2008 Table 195 so source-level
    # diffing against PDFBox-produced PDFs stays sane.
    aa = PDDocumentCatalogAdditionalActions()
    aa.set_dp(_uri("https://example.test/dp"))
    aa.set_wc(_uri("https://example.test/wc"))
    aa.set_ds(_uri("https://example.test/ds"))
    assert repr(aa) == "PDDocumentCatalogAdditionalActions(WC,DS,DP)"


def test_repr_with_all_triggers() -> None:
    aa = PDDocumentCatalogAdditionalActions()
    for attr, _ in _HAS_TRIGGERS:
        getattr(aa, f"set_{attr}")(_uri(f"https://example.test/{attr}"))
    assert repr(aa) == "PDDocumentCatalogAdditionalActions(WC,WS,DS,WP,DP)"


# ---------- constructor edge cases ----------


def test_constructor_none_arg_creates_empty_dict() -> None:
    aa = PDDocumentCatalogAdditionalActions(None)
    cos = aa.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.size() == 0


def test_constructor_seeded_dict_round_trips_known_trigger() -> None:
    seed = COSDictionary()
    action = PDActionURI()
    action.set_uri("https://example.test/seeded-ds")
    seed.set_item(PDDocumentCatalogAdditionalActions.TRIGGER_DS, action.get_cos_object())

    aa = PDDocumentCatalogAdditionalActions(seed)

    assert aa.get_cos_object() is seed
    resolved = aa.get_ds()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/seeded-ds"
    assert aa.has_ds() is True
    assert aa.is_empty() is False
