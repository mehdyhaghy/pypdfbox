"""Coverage-boost tests for ``pypdfbox.pdmodel.resource_cache``
(wave 1316).

The thin :class:`ResourceCache` subclass adds a generic ``put(key, value)``
dispatcher on top of :class:`PDResourceCache`. The four type branches and
the unsupported-type fallback (which raises :class:`TypeError`) are the
only lines unique to this module — the rest is inherited from
``pd_resource_cache``. These tests exercise each branch.
"""
from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSObject
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache
from pypdfbox.pdmodel.resource_cache import ResourceCache


class _RecordingCache(ResourceCache):
    """Minimal concrete subclass that records which ``put_*`` slot was hit.

    The four-line ``ResourceCache.put`` dispatcher routes by runtime type;
    the simplest way to assert routing is to override each slot and stash
    the value in a per-category attribute.
    """

    def __init__(self) -> None:
        self.font: Any = None
        self.color_space: Any = None
        self.x_object: Any = None
        self.pattern: Any = None
        self.shading: Any = None
        self.ext_g_state: Any = None
        self.property_list: Any = None

    def get_font(self, indirect: COSObject) -> Any:
        return self.font

    def put_font(self, indirect: COSObject, font: Any) -> None:
        self.font = font

    def get_x_object(self, indirect: COSObject) -> Any:
        return self.x_object

    def put_x_object(self, indirect: COSObject, xobject: Any) -> None:
        self.x_object = xobject

    def get_color_space(self, indirect: COSObject) -> Any:
        return self.color_space

    def put_color_space(self, indirect: COSObject, color_space: Any) -> None:
        self.color_space = color_space

    def get_pattern(self, indirect: COSObject) -> Any:
        return self.pattern

    def put_pattern(self, indirect: COSObject, pattern: Any) -> None:
        self.pattern = pattern

    def get_shading(self, indirect: COSObject) -> Any:
        return self.shading

    def put_shading(self, indirect: COSObject, shading: Any) -> None:
        self.shading = shading

    def get_ext_g_state(self, indirect: COSObject) -> Any:
        return self.ext_g_state

    def put_ext_g_state(self, indirect: COSObject, ext_g_state: Any) -> None:
        self.ext_g_state = ext_g_state

    def get_property_list(self, indirect: COSObject) -> Any:
        return self.property_list

    def put_property_list(self, indirect: COSObject, prop: Any) -> None:
        self.property_list = prop


def _ref(num: int = 1) -> COSObject:
    return COSObject(num)


def test_resource_cache_is_subclass_of_pd_resource_cache() -> None:
    assert issubclass(ResourceCache, PDResourceCache)


def test_put_dispatches_pd_form_x_object_to_x_object_slot() -> None:
    """PDFormXObject (a subclass of PDXObject) routes to ``put_x_object``."""
    cache = _RecordingCache()
    form = PDFormXObject(COSStream())
    cache.put(_ref(1), form)
    assert cache.x_object is form
    # Sibling slots untouched.
    assert cache.font is None
    assert cache.color_space is None


def test_put_dispatches_pd_color_space() -> None:
    """A PDColorSpace instance lands in the color-space slot."""
    cache = _RecordingCache()
    gray = PDDeviceGray.INSTANCE
    cache.put(_ref(2), gray)
    assert cache.color_space is gray
    assert cache.x_object is None


def test_put_dispatches_pd_font() -> None:
    """The dispatcher recognises PDFont — the cheapest concrete PDFont we
    can spin up is a no-arg :class:`PDType1Font` (defaults to Helvetica)."""
    from pypdfbox.pdmodel.font import PDFont
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    helvetica = PDType1Font()
    assert isinstance(helvetica, PDFont)
    cache = _RecordingCache()
    cache.put(_ref(3), helvetica)
    assert cache.font is helvetica
    assert cache.x_object is None


def test_put_rejects_unsupported_value_type_with_typeerror() -> None:
    cache = _RecordingCache()
    with pytest.raises(TypeError, match="unsupported value type"):
        cache.put(_ref(4), "not a resource")
    with pytest.raises(TypeError, match="int"):
        cache.put(_ref(5), 123)


def test_put_rejects_pd_font_descriptor_explicitly() -> None:
    """PDFontDescriptor is in the PD-family but the thin ``ResourceCache``
    dispatcher only knows the four canonical slots; descriptors must fall
    through to the TypeError branch (DefaultResourceCache handles them via
    a different dispatcher)."""
    cache = _RecordingCache()
    descriptor = PDFontDescriptor(COSDictionary())
    with pytest.raises(TypeError):
        cache.put(_ref(6), descriptor)


def test_resource_cache_inherits_all_abstract_methods() -> None:
    """Without overriding the abstract methods the subclass should still be
    abstract — sanity check that ResourceCache adds no concrete defaults
    beyond ``put``."""
    import inspect

    assert inspect.isabstract(ResourceCache)


def test_resource_cache_module_all_lists_resource_cache() -> None:
    import pypdfbox.pdmodel.resource_cache as module

    assert module.__all__ == ["ResourceCache"]
