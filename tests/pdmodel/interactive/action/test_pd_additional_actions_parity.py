from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.action import (
    PDActionURI,
    PDDocumentCatalogAdditionalActions,
    PDPageAdditionalActions,
)

_PAGE_TRIGGERS = [
    ("o", "https://example.test/page/o"),
    ("c", "https://example.test/page/c"),
]

_CATALOG_TRIGGERS = [
    ("wc", "https://example.test/catalog/wc"),
    ("ws", "https://example.test/catalog/ws"),
    ("ds", "https://example.test/catalog/ds"),
    ("wp", "https://example.test/catalog/wp"),
    ("dp", "https://example.test/catalog/dp"),
]


@pytest.mark.parametrize(("attr", "uri"), _PAGE_TRIGGERS)
def test_page_additional_actions_typed_round_trip(attr: str, uri: str) -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri(uri)

    getattr(aa, f"set_{attr}")(action)

    resolved = getattr(aa, f"get_{attr}")()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == uri


@pytest.mark.parametrize(("attr", "uri"), _CATALOG_TRIGGERS)
def test_document_catalog_additional_actions_typed_round_trip(
    attr: str, uri: str
) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    action = PDActionURI()
    action.set_uri(uri)

    getattr(aa, f"set_{attr}")(action)

    resolved = getattr(aa, f"get_{attr}")()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == uri


def test_page_get_open_action_alias_matches_get_o() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/page/open-alias")

    aa.set_o(action)

    via_short = aa.get_o()
    via_alias = aa.get_open_action()
    assert isinstance(via_alias, PDActionURI)
    assert isinstance(via_short, PDActionURI)
    assert via_alias.get_uri() == via_short.get_uri() == (
        "https://example.test/page/open-alias"
    )
    # Both accessors observe the same underlying COS dictionary entry.
    assert via_alias.get_cos_object() is via_short.get_cos_object()


def test_page_set_open_action_alias_writes_o_entry() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/page/set-via-alias")

    aa.set_open_action(action)

    resolved = aa.get_o()
    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test/page/set-via-alias"


def test_page_close_action_alias_round_trip() -> None:
    aa = PDPageAdditionalActions()
    action = PDActionURI()
    action.set_uri("https://example.test/page/close-alias")

    aa.set_close_action(action)

    via_alias = aa.get_close_action()
    via_short = aa.get_c()
    assert isinstance(via_alias, PDActionURI)
    assert isinstance(via_short, PDActionURI)
    assert via_alias.get_uri() == via_short.get_uri() == (
        "https://example.test/page/close-alias"
    )


_CATALOG_ALIASES = [
    ("wc", "will_close", "https://example.test/catalog/will_close"),
    ("ws", "will_save", "https://example.test/catalog/will_save"),
    ("ds", "did_save", "https://example.test/catalog/did_save"),
    ("wp", "will_print", "https://example.test/catalog/will_print"),
    ("dp", "did_print", "https://example.test/catalog/did_print"),
]


@pytest.mark.parametrize(("short", "alias", "uri"), _CATALOG_ALIASES)
def test_document_catalog_alias_matches_short_accessor(
    short: str, alias: str, uri: str
) -> None:
    aa = PDDocumentCatalogAdditionalActions()
    action = PDActionURI()
    action.set_uri(uri)

    # Set via the alias, observe via the short accessor.
    getattr(aa, f"set_{alias}")(action)
    via_short = getattr(aa, f"get_{short}")()
    via_alias = getattr(aa, f"get_{alias}")()
    assert isinstance(via_short, PDActionURI)
    assert isinstance(via_alias, PDActionURI)
    assert via_short.get_uri() == via_alias.get_uri() == uri
