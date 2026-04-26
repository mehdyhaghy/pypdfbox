from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.action.pd_document_catalog_additional_actions import (
    PDDocumentCatalogAdditionalActions,
)

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
