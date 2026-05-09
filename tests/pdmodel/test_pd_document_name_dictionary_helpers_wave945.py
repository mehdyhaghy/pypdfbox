from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from tests.pdmodel import test_pd_document_name_dictionary_parity as names_mod


def test_wave945_fake_catalog_returns_stable_cos_dictionary() -> None:
    catalog = names_mod._FakeCatalog()  # noqa: SLF001
    marker = COSName.get_pdf_name("Marker")

    catalog.get_cos_object().set_item(marker, COSDictionary())

    assert catalog.get_cos_object().contains_key(marker)
    assert catalog.get_cos_object() is catalog._dict  # noqa: SLF001
