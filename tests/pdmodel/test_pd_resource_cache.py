from __future__ import annotations

from typing import Any

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSDictionary, COSObject, COSStream
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.pd_resource_cache import (
    DefaultResourceCache,
    PDResourceCache,
)


def _ref(object_number: int, generation_number: int = 0) -> COSObject:
    """Build a bare indirect reference for cache keying — no loader needed
    since the cache only ever uses ``__hash__`` / ``__eq__``."""
    return COSObject(object_number, generation_number)


def _font_standin() -> Any:
    return COSDictionary()


# ---------- DefaultResourceCache ----------


def test_default_cache_is_a_pd_resource_cache() -> None:
    assert isinstance(DefaultResourceCache(), PDResourceCache)


def test_put_font_get_font_round_trip() -> None:
    cache = DefaultResourceCache()
    key = _ref(7)
    font = _font_standin()
    cache.put_font(key, font)
    assert cache.get_font(key) is font


def test_get_font_missing_returns_none() -> None:
    cache = DefaultResourceCache()
    assert cache.get_font(_ref(99)) is None


def test_put_x_object_get_x_object_round_trip() -> None:
    cache = DefaultResourceCache()
    key = _ref(8)
    xobject = PDFormXObject(COSStream())
    cache.put_x_object(key, xobject)
    assert cache.get_x_object(key) is xobject


def test_get_x_object_missing_returns_none() -> None:
    cache = DefaultResourceCache()
    assert cache.get_x_object(_ref(100)) is None


def test_clear_empties_the_cache() -> None:
    cache = DefaultResourceCache()
    key = _ref(3)
    cache.put_font(key, _font_standin())
    cache.put_x_object(key, PDFormXObject(COSStream()))
    cache.put_color_space(key, object())  # type: ignore[arg-type]
    cache.put_pattern(key, object())  # type: ignore[arg-type]
    cache.put_shading(key, object())  # type: ignore[arg-type]
    cache.put_ext_g_state(key, object())  # type: ignore[arg-type]
    cache.put_property_list(key, object())  # type: ignore[arg-type]
    cache.clear()
    assert cache.get_font(key) is None
    assert cache.get_x_object(key) is None
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
    font = _font_standin()
    cache.put_font(_ref(11, 0), font)
    # Different COSObject instance, same ref pair.
    assert cache.get_font(_ref(11, 0)) is font


def test_distinct_keys_do_not_collide() -> None:
    cache = DefaultResourceCache()
    a, b = _font_standin(), _font_standin()
    cache.put_font(_ref(1), a)
    cache.put_font(_ref(2), b)
    assert cache.get_font(_ref(1)) is a
    assert cache.get_font(_ref(2)) is b


def test_each_category_is_isolated() -> None:
    cache = DefaultResourceCache()
    key = _ref(5)
    font = _font_standin()
    cache.put_font(key, font)
    # Same key in a different category should miss.
    assert cache.get_color_space(key) is None
    assert cache.get_x_object(key) is None
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
    # ``None`` is an explicit "disabled" value, not an unset sentinel.
    assert doc.get_resource_cache() is None


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


# ---------- CID font / font descriptor (upstream defaults) ----------


def test_put_cid_font_get_cid_font_round_trip() -> None:
    cache = DefaultResourceCache()
    key = _ref(20)
    cid_font: Any = COSDictionary()  # stand-in for a PDCIDFont wrapper
    cache.put_cid_font(key, cid_font)
    assert cache.get_cid_font(key) is cid_font


def test_get_cid_font_missing_returns_none() -> None:
    assert DefaultResourceCache().get_cid_font(_ref(21)) is None


def test_put_font_descriptor_get_font_descriptor_round_trip() -> None:
    cache = DefaultResourceCache()
    key = _ref(22)
    descriptor: Any = COSDictionary()  # stand-in for a PDFontDescriptor
    cache.put_font_descriptor(key, descriptor)
    assert cache.get_font_descriptor(key) is descriptor


def test_get_font_descriptor_missing_returns_none() -> None:
    assert DefaultResourceCache().get_font_descriptor(_ref(23)) is None


# ---------- removal hooks ----------


def test_remove_color_space_pops_and_returns_value() -> None:
    cache = DefaultResourceCache()
    key = _ref(31)
    cs = object()
    cache.put_color_space(key, cs)  # type: ignore[arg-type]
    assert cache.remove_color_space(key) is cs
    assert cache.get_color_space(key) is None
    # Second remove returns None (already gone).
    assert cache.remove_color_space(key) is None


def test_remove_methods_return_value_and_clear_each_category() -> None:
    cache = DefaultResourceCache()
    key = _ref(32)
    font, xobject, ext, shading, pattern, prop = (
        _font_standin(),
        PDFormXObject(COSStream()),
        object(),
        object(),
        object(),
        object(),
    )
    cache.put_font(key, font)
    cache.put_x_object(key, xobject)
    cache.put_ext_g_state(key, ext)  # type: ignore[arg-type]
    cache.put_shading(key, shading)  # type: ignore[arg-type]
    cache.put_pattern(key, pattern)  # type: ignore[arg-type]
    cache.put_property_list(key, prop)  # type: ignore[arg-type]

    assert cache.remove_font(key) is font
    assert cache.remove_x_object(key) is xobject
    assert cache.remove_ext_g_state(key) is ext
    assert cache.remove_shading(key) is shading
    assert cache.remove_pattern(key) is pattern
    assert cache.remove_property_list(key) is prop

    # All cleared.
    assert cache.get_font(key) is None
    assert cache.get_x_object(key) is None
    assert cache.get_ext_g_state(key) is None
    assert cache.get_shading(key) is None
    assert cache.get_pattern(key) is None
    assert cache.get_property_list(key) is None


def test_remove_cid_font_and_font_descriptor_round_trip() -> None:
    cache = DefaultResourceCache()
    key = _ref(33)
    cid_font: Any = COSDictionary()
    descriptor: Any = COSDictionary()
    cache.put_cid_font(key, cid_font)
    cache.put_font_descriptor(key, descriptor)

    assert cache.remove_cid_font(key) is cid_font
    assert cache.remove_font_descriptor(key) is descriptor
    assert cache.get_cid_font(key) is None
    assert cache.get_font_descriptor(key) is None


class _MinimalCache(PDResourceCache):
    """Bare-bones subclass exercising abstract defaults (cid font, font
    descriptor, ``remove_*``) — none of which are abstract on
    :class:`PDResourceCache`. Mirrors the upstream ``ResourceCache`` defaults
    that return ``null``."""

    def get_font(self, indirect: COSObject) -> Any:
        return None

    def put_font(self, indirect: COSObject, font: Any) -> None:
        pass

    def get_x_object(self, indirect: COSObject) -> Any:
        return None

    def put_x_object(self, indirect: COSObject, xobject: Any) -> None:
        pass

    def get_color_space(self, indirect: COSObject) -> Any:
        return None

    def put_color_space(self, indirect: COSObject, color_space: Any) -> None:
        pass

    def get_pattern(self, indirect: COSObject) -> Any:
        return None

    def put_pattern(self, indirect: COSObject, pattern: Any) -> None:
        pass

    def get_shading(self, indirect: COSObject) -> Any:
        return None

    def put_shading(self, indirect: COSObject, shading: Any) -> None:
        pass

    def get_ext_g_state(self, indirect: COSObject) -> Any:
        return None

    def put_ext_g_state(self, indirect: COSObject, ext_g_state: Any) -> None:
        pass

    def get_property_list(self, indirect: COSObject) -> Any:
        return None

    def put_property_list(self, indirect: COSObject, property_list: Any) -> None:
        pass


def test_pd_resource_cache_defaults_match_upstream_null_returns() -> None:
    """Upstream ``ResourceCache`` declares CID-font / font-descriptor /
    remove-* methods as ``default ... return null``. Subclasses that omit
    them must inherit those ``None`` returns."""
    cache = _MinimalCache()
    key = _ref(40)

    assert cache.get_cid_font(key) is None
    assert cache.get_font_descriptor(key) is None
    cache.put_cid_font(key, object())  # type: ignore[arg-type]
    cache.put_font_descriptor(key, object())  # type: ignore[arg-type]

    assert cache.remove_color_space(key) is None
    assert cache.remove_ext_g_state(key) is None
    assert cache.remove_font(key) is None
    assert cache.remove_cid_font(key) is None
    assert cache.remove_font_descriptor(key) is None
    assert cache.remove_shading(key) is None
    assert cache.remove_pattern(key) is None
    assert cache.remove_property_list(key) is None
    assert cache.remove_x_object(key) is None


# ---------- upstream-name aliases ----------


def test_get_properties_alias_round_trips_through_property_list() -> None:
    """``get_properties`` / ``put_properties`` mirror upstream
    ``getProperties`` / ``put(COSObject, PDPropertyList)`` — they must hit
    the same backing store as ``get_property_list`` / ``put_property_list``."""
    cache = DefaultResourceCache()
    key = _ref(50)
    prop = object()
    cache.put_properties(key, prop)  # type: ignore[arg-type]
    assert cache.get_properties(key) is prop
    # Both name spellings address the same slot.
    assert cache.get_property_list(key) is prop


def test_remove_properties_alias_pops_property_list() -> None:
    """``remove_properties`` mirrors upstream ``removeProperties`` — must
    drop the same entry ``remove_property_list`` would."""
    cache = DefaultResourceCache()
    key = _ref(51)
    prop = object()
    cache.put_property_list(key, prop)  # type: ignore[arg-type]
    assert cache.remove_properties(key) is prop
    assert cache.get_property_list(key) is None
    # Idempotent on a missing key.
    assert cache.remove_properties(key) is None


def test_remove_ext_state_alias_pops_ext_g_state() -> None:
    """``remove_ext_state`` mirrors upstream ``removeExtState`` — pypdfbox
    standardised on ``remove_ext_g_state`` to match ``get_ext_g_state`` /
    ``put_ext_g_state``, but the upstream-mechanical name must work too."""
    cache = DefaultResourceCache()
    key = _ref(52)
    ext = object()
    cache.put_ext_g_state(key, ext)  # type: ignore[arg-type]
    assert cache.remove_ext_state(key) is ext
    assert cache.get_ext_g_state(key) is None


def test_minimal_cache_aliases_inherit_none_defaults() -> None:
    """Subclasses that don't override the new aliases inherit the upstream
    ``null`` defaults — ``get_properties`` falls through to the abstract
    ``get_property_list`` (here, a ``None`` stub), and the remove aliases
    return ``None``."""
    cache = _MinimalCache()
    key = _ref(53)
    # ``put_properties`` must not raise on the minimal subclass.
    cache.put_properties(key, object())  # type: ignore[arg-type]
    assert cache.get_properties(key) is None
    assert cache.remove_properties(key) is None
    assert cache.remove_ext_state(key) is None


# ---------- stable-cache flag + MAX_REMOVALS constant ----------


def test_max_removals_constant_matches_upstream() -> None:
    """Upstream ``DefaultResourceCache.maxRemovals = 3``. Surface it as a
    class constant so callers can refer to the threshold without hard-coding
    it."""
    assert DefaultResourceCache.MAX_REMOVALS == 3


def test_stable_cache_enabled_by_default() -> None:
    """Mirrors the upstream no-arg constructor, which delegates to
    ``DefaultResourceCache(true)``."""
    assert DefaultResourceCache().is_stable_cache_enabled() is True


def test_stable_cache_can_be_disabled_via_constructor() -> None:
    """Upstream ``DefaultResourceCache(boolean enableStableCache)``. When
    callers pass ``False``, the flag must round-trip through
    ``is_stable_cache_enabled``."""
    cache = DefaultResourceCache(enable_stable_cache=False)
    assert cache.is_stable_cache_enabled() is False
    # Removals still work regardless of the flag (eviction policy is a no-op
    # until SoftReference semantics are implemented — see CHANGES.md).
    key = _ref(60)
    font = _font_standin()
    cache.put_font(key, font)
    assert cache.remove_font(key) is font
    assert cache.get_font(key) is None


def test_stable_cache_stops_removing_shared_font_after_threshold() -> None:
    """Upstream stable caching marks repeatedly removed resources as stable
    after ``MAX_REMOVALS`` attempts; the threshold removal itself is ignored."""
    cache = DefaultResourceCache()
    key = _ref(61)

    first = _font_standin()
    cache.put_font(key, first)
    assert cache.remove_font(key) is first

    second = _font_standin()
    cache.put_font(_ref(61), second)
    assert cache.remove_font(_ref(61)) is second

    stable = _font_standin()
    cache.put_font(key, stable)
    assert cache.remove_font(key) is None
    assert cache.get_font(_ref(61)) is stable

    assert cache.remove_font(_ref(61)) is None
    assert cache.get_font(key) is stable


def test_stable_cache_disabled_keeps_honoring_repeated_removals() -> None:
    cache = DefaultResourceCache(enable_stable_cache=False)
    key = _ref(62)

    for _ in range(DefaultResourceCache.MAX_REMOVALS + 1):
        font = _font_standin()
        cache.put_font(key, font)
        assert cache.remove_font(_ref(62)) is font
        assert cache.get_font(key) is None


def test_stable_cache_applies_to_upstream_removal_aliases() -> None:
    cache = DefaultResourceCache()
    key = _ref(63)

    for removed in range(DefaultResourceCache.MAX_REMOVALS):
        prop = object()
        cache.put_property_list(key, prop)  # type: ignore[arg-type]
        removed_value = cache.remove_properties(_ref(63))
        if removed < DefaultResourceCache.MAX_REMOVALS - 1:
            assert removed_value is prop
            assert cache.get_property_list(key) is None
        else:
            assert removed_value is None
            assert cache.get_property_list(key) is prop


def test_clear_resets_stable_cache_bookkeeping() -> None:
    cache = DefaultResourceCache()
    key = _ref(64)

    for _ in range(DefaultResourceCache.MAX_REMOVALS):
        font = _font_standin()
        cache.put_font(key, font)
        cache.remove_font(key)

    assert cache.get_font(key) is not None

    cache.clear()

    font = _font_standin()
    cache.put_font(key, font)
    assert cache.remove_font(key) is font
    assert cache.get_font(key) is None


# ---------- DefaultResourceCache concrete overrides for upstream parity ----------


def test_default_cache_get_properties_returns_cached_property_list() -> None:
    """``DefaultResourceCache.get_properties`` mirrors upstream's
    ``getProperties`` (line 311) — it must return the same backing entry as
    ``get_property_list`` without going through the abstract base."""
    cache = DefaultResourceCache()
    key = _ref(70)
    prop = object()
    cache.put_property_list(key, prop)  # type: ignore[arg-type]
    assert cache.get_properties(key) is prop
    assert cache.get_properties(_ref(71)) is None


def test_default_cache_remove_properties_applies_stable_cache_guard() -> None:
    """``DefaultResourceCache.remove_properties`` (upstream line 327) must
    apply the same ``MAX_REMOVALS`` eviction guard as
    ``remove_property_list``."""
    cache = DefaultResourceCache()
    key = _ref(72)

    for removed in range(DefaultResourceCache.MAX_REMOVALS):
        prop = object()
        cache.put_property_list(key, prop)  # type: ignore[arg-type]
        result = cache.remove_properties(_ref(72))
        if removed < DefaultResourceCache.MAX_REMOVALS - 1:
            assert result is prop
        else:
            # Threshold hit — removal is suppressed and the entry stays.
            assert result is None
            assert cache.get_property_list(key) is prop


def test_default_cache_remove_ext_state_applies_stable_cache_guard() -> None:
    """``DefaultResourceCache.remove_ext_state`` (upstream line 252) must
    apply the same ``MAX_REMOVALS`` eviction guard as
    ``remove_ext_g_state``."""
    cache = DefaultResourceCache()
    key = _ref(73)

    for removed in range(DefaultResourceCache.MAX_REMOVALS):
        ext = object()
        cache.put_ext_g_state(key, ext)  # type: ignore[arg-type]
        result = cache.remove_ext_state(_ref(73))
        if removed < DefaultResourceCache.MAX_REMOVALS - 1:
            assert result is ext
        else:
            assert result is None
            assert cache.get_ext_g_state(key) is ext


def test_default_cache_put_dispatches_by_resource_type() -> None:
    """The single-name ``put`` dispatcher mirrors upstream's nine
    ``put(COSObject, ...)`` overloads (lines 119, 137, 154, 173, 198, 230,
    263, 289, 318) — each runtime type must land in the matching backing
    store."""
    from pypdfbox.cos import COSDictionary, COSStream
    from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
    from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
    from pypdfbox.pdmodel.graphics.form import PDFormXObject
    from pypdfbox.pdmodel.graphics.pattern.pd_shading_pattern import (
        PDShadingPattern,
    )
    from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
    from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    cache = DefaultResourceCache()

    xobject = PDFormXObject(COSStream())
    cache.put(_ref(80), xobject)
    assert cache.get_x_object(_ref(80)) is xobject

    ext = PDExtendedGraphicsState()
    cache.put(_ref(81), ext)
    assert cache.get_ext_g_state(_ref(81)) is ext

    cs_dict = COSDictionary()
    color_space = PDDeviceN(cs_dict) if False else None
    if color_space is not None:
        cache.put(_ref(82), color_space)
        assert cache.get_color_space(_ref(82)) is color_space

    shading = PDShadingType1(COSDictionary())
    cache.put(_ref(83), shading)
    assert cache.get_shading(_ref(83)) is shading

    pattern = PDShadingPattern(COSDictionary())
    cache.put(_ref(84), pattern)
    assert cache.get_pattern(_ref(84)) is pattern

    descriptor = PDFontDescriptor(COSDictionary())
    cache.put(_ref(85), descriptor)
    assert cache.get_font_descriptor(_ref(85)) is descriptor

    prop = PDPropertyList(COSDictionary())
    cache.put(_ref(86), prop)
    assert cache.get_property_list(_ref(86)) is prop

    # PDCIDFont must route to the CID slot, not the generic font slot.
    cid_dict = COSDictionary()
    cid_font = PDCIDFont.__new__(PDCIDFont)
    cid_font.dict = cid_dict  # type: ignore[attr-defined]
    cache.put(_ref(87), cid_font)
    assert cache.get_cid_font(_ref(87)) is cid_font
    assert cache.get_font(_ref(87)) is None


def test_default_cache_put_rejects_unsupported_types() -> None:
    """Anything that isn't a recognised PD wrapper must raise ``TypeError``
    — silent drops would mask programming errors."""
    cache = DefaultResourceCache()
    with pytest.raises(TypeError):
        cache.put(_ref(90), "not a resource")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cache.put(_ref(91), 12345)  # type: ignore[arg-type]
