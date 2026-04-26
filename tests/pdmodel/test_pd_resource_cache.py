from __future__ import annotations

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSDictionary, COSObject
from pypdfbox.pdmodel.pd_resource_cache import (
    DefaultResourceCache,
    PDResourceCache,
)


def _ref(object_number: int, generation_number: int = 0) -> COSObject:
    """Build a bare indirect reference for cache keying — no loader needed
    since the cache only ever uses ``__hash__`` / ``__eq__``."""
    return COSObject(object_number, generation_number)


# ---------- DefaultResourceCache ----------


def test_default_cache_is_a_pd_resource_cache() -> None:
    assert isinstance(DefaultResourceCache(), PDResourceCache)


def test_put_font_get_font_round_trip() -> None:
    cache = DefaultResourceCache()
    key = _ref(7)
    font = COSDictionary()  # stand-in for a PDFont wrapper
    cache.put_font(key, font)
    assert cache.get_font(key) is font


def test_get_font_missing_returns_none() -> None:
    cache = DefaultResourceCache()
    assert cache.get_font(_ref(99)) is None


def test_clear_empties_the_cache() -> None:
    cache = DefaultResourceCache()
    key = _ref(3)
    cache.put_font(key, COSDictionary())
    cache.put_color_space(key, object())  # type: ignore[arg-type]
    cache.put_pattern(key, object())  # type: ignore[arg-type]
    cache.put_shading(key, object())  # type: ignore[arg-type]
    cache.put_ext_g_state(key, object())  # type: ignore[arg-type]
    cache.put_property_list(key, object())  # type: ignore[arg-type]
    cache.clear()
    assert cache.get_font(key) is None
    assert cache.get_color_space(key) is None
    assert cache.get_pattern(key) is None
    assert cache.get_shading(key) is None
    assert cache.get_ext_g_state(key) is None
    assert cache.get_property_list(key) is None


def test_identity_caching_same_key_returns_same_instance() -> None:
    """Two ``COSObject`` instances pointing at the same indirect ref must
    resolve to the same cached entry — the cache keys on
    ``(object_number, generation_number)`` equality, not identity."""
    cache = DefaultResourceCache()
    font = COSDictionary()
    cache.put_font(_ref(11, 0), font)
    # Different COSObject instance, same ref pair.
    assert cache.get_font(_ref(11, 0)) is font


def test_distinct_keys_do_not_collide() -> None:
    cache = DefaultResourceCache()
    a, b = COSDictionary(), COSDictionary()
    cache.put_font(_ref(1), a)
    cache.put_font(_ref(2), b)
    assert cache.get_font(_ref(1)) is a
    assert cache.get_font(_ref(2)) is b


def test_each_category_is_isolated() -> None:
    cache = DefaultResourceCache()
    key = _ref(5)
    font = COSDictionary()
    cache.put_font(key, font)
    # Same key in a different category should miss.
    assert cache.get_color_space(key) is None
    assert cache.get_pattern(key) is None
    assert cache.get_shading(key) is None
    assert cache.get_ext_g_state(key) is None
    assert cache.get_property_list(key) is None


# ---------- PDDocument wiring ----------


def test_get_resource_cache_default_is_default_resource_cache() -> None:
    doc = PDDocument()
    cache = doc.get_resource_cache()
    assert isinstance(cache, DefaultResourceCache)
    # Lazily allocated — second call returns the same instance.
    assert doc.get_resource_cache() is cache


def test_set_resource_cache_stores_custom_instance() -> None:
    doc = PDDocument()
    custom = DefaultResourceCache()
    doc.set_resource_cache(custom)
    assert doc.get_resource_cache() is custom


def test_set_resource_cache_to_none_disables_caching() -> None:
    doc = PDDocument()
    # Force lazy allocation.
    doc.get_resource_cache()
    doc.set_resource_cache(None)
    # Next access lazily re-allocates a fresh DefaultResourceCache.
    cache = doc.get_resource_cache()
    assert isinstance(cache, DefaultResourceCache)


def test_add_signature_rejects_non_pdsignature() -> None:
    """``add_signature`` now ships a working pipeline (digitalsignature
    cluster). Passing a non-PDSignature must raise ``TypeError`` — the
    NotImplementedError stub message is gone."""
    doc = PDDocument()
    with pytest.raises(TypeError):
        doc.add_signature(object())  # type: ignore[arg-type]


def test_register_true_type_font_for_closing_is_a_noop() -> None:
    doc = PDDocument()
    sentinel = object()
    # Must not raise.
    doc.register_true_type_font_for_closing(sentinel)
    # Internal list captures the registration so future lifecycle work has
    # something to drain (PRD §6 — font subsetting cluster).
    assert sentinel in doc._fonts_to_close  # noqa: SLF001 — test invariant
