from __future__ import annotations

from pypdfbox.cos import COSDictionary
from tests.multipdf.test_pdf_merger_utility_wave645 import _CatalogWithForm


def test_wave1174_catalog_with_form_exposes_cos_dictionary() -> None:
    catalog = _CatalogWithForm()

    assert isinstance(catalog.get_cos_object(), COSDictionary)
