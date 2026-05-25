"""Wave 1397 branch-coverage tests for ``PDDocumentNameDictionary``.

Closes False-branch arrows on the catalog-fallback paths where the
legacy ``/Dests`` entry exists on the catalog but isn't a
``COSDictionary``:

* ``has_dests`` 145->147 — ``/Catalog/Dests`` is present but non-dict
* ``get_dests`` 195->197 — same shape
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_document_name_dictionary import (
    PDDocumentNameDictionary,
)


class _StubCatalog:
    """Minimal catalog stub: just a getter for a backing COSDictionary."""

    def __init__(self, cos: COSDictionary) -> None:
        self._cos = cos

    def get_cos_object(self) -> COSDictionary:
        return self._cos


def test_has_dests_false_when_catalog_dests_is_non_dict() -> None:
    """Closes 145->147: /Names/Dests absent AND /Catalog/Dests is a
    non-dictionary (an array, for instance) — has_dests reports False."""
    catalog_cos = COSDictionary()
    # Catalog carries a /Dests entry but as an array, not a dict.
    catalog_cos.set_item(COSName.get_pdf_name("Dests"), COSArray())
    names = COSDictionary()
    nd = PDDocumentNameDictionary(_StubCatalog(catalog_cos), names)
    assert nd.has_dests() is False


def test_get_dests_returns_none_when_catalog_dests_is_non_dict() -> None:
    """Closes 195->197: same shape — get_dests returns None when the
    catalog's /Dests is a non-dictionary."""
    catalog_cos = COSDictionary()
    catalog_cos.set_item(COSName.get_pdf_name("Dests"), COSArray())
    names = COSDictionary()
    nd = PDDocumentNameDictionary(_StubCatalog(catalog_cos), names)
    assert nd.get_dests() is None
