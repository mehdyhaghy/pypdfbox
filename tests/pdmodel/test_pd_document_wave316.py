"""Wave 316 coverage for PDDocument resource cache sentinel handling."""

from __future__ import annotations

from pypdfbox import PDDocument
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


def test_set_resource_cache_none_disables_lazy_default_wave316() -> None:
    doc = PDDocument()

    doc.set_resource_cache(None)

    assert doc.get_resource_cache() is None
    doc.close()


def test_set_resource_cache_none_after_default_cache_stays_disabled_wave316() -> None:
    doc = PDDocument()
    default_cache = doc.get_resource_cache()
    assert isinstance(default_cache, DefaultResourceCache)

    doc.set_resource_cache(None)

    assert doc.get_resource_cache() is None
    doc.close()

