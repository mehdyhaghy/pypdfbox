"""Wave 1341 coverage-boost tests for ``pypdfbox.pdmodel.graphics.color.pd_color_space``.

Targets the still-uncovered branches in the wave-1332 snapshot:

* :meth:`PDColorSpace._create_from_cos_object` resource-cache pathway
  (lines 207-216): pre-populated cache hit, cache miss with put-back,
  and the no-cache branch when ``resources.get_resource_cache()``
  returns ``None``.
* The default :meth:`PDColorSpace.to_rgb` delegation through
  :class:`PDColor` (lines 256-259); concrete subclasses all override
  ``to_rgb`` so we drive the base implementation directly through a
  no-override stub.
* :meth:`to_raw_image` ``DeviceCMYK`` raster path (line 352).
* :meth:`__str__` returning the color-space name (line 434).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSArray, COSName, COSObject
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

# ---------- _create_from_cos_object cache pathways ------------------------


class _StubCache:
    def __init__(self, pre_populated: dict[int, PDColorSpace] | None = None) -> None:
        self.store: dict[int, PDColorSpace] = pre_populated or {}
        self.puts: list[tuple[int, PDColorSpace]] = []
        self.lookups: list[int] = []

    def get_color_space(self, indirect: COSObject) -> PDColorSpace | None:
        self.lookups.append(id(indirect))
        return self.store.get(id(indirect))

    def put_color_space(
        self, indirect: COSObject, color_space: PDColorSpace
    ) -> None:
        self.puts.append((id(indirect), color_space))
        self.store[id(indirect)] = color_space


class _StubResources:
    def __init__(self, cache: _StubCache | None) -> None:
        self._cache = cache

    def get_resource_cache(self) -> _StubCache | None:
        return self._cache


def _make_cos_object_name(name: str) -> COSObject:
    """Wrap a /DeviceGray-like COSName in a resolved COSObject reference."""
    return COSObject(1, 0, resolved=COSName.get_pdf_name(name))


def test_create_from_cos_object_returns_cached_instance() -> None:
    """Pre-populated cache short-circuits and returns the cached entry."""
    cos_obj = _make_cos_object_name("DeviceGray")
    sentinel = PDDeviceRGB.INSTANCE  # any singleton works -- it's the stored entry
    cache = _StubCache(pre_populated={id(cos_obj): sentinel})
    resources = _StubResources(cache)
    out = PDColorSpace._create_from_cos_object(cos_obj, resources)
    assert out is sentinel
    assert cache.lookups == [id(cos_obj)]


def test_create_from_cos_object_caches_miss() -> None:
    """An empty cache routes through ``create`` and stores the result."""
    cos_obj = _make_cos_object_name("DeviceRGB")
    cache = _StubCache()
    resources = _StubResources(cache)
    out = PDColorSpace._create_from_cos_object(cos_obj, resources)
    assert out is PDDeviceRGB.INSTANCE
    assert cache.puts == [(id(cos_obj), PDDeviceRGB.INSTANCE)]


def test_create_from_cos_object_no_cache_falls_through() -> None:
    """``resources.get_resource_cache() is None`` -> direct ``create()``."""
    cos_obj = _make_cos_object_name("DeviceCMYK")
    resources = _StubResources(cache=None)
    out = PDColorSpace._create_from_cos_object(cos_obj, resources)
    assert out is PDDeviceCMYK.INSTANCE


# ---------- default to_rgb delegation through PDColor ---------------------


class _NoToRGBOverride(PDColorSpace):
    """Stub subclass that DOES NOT override ``to_rgb``, so the base class's
    delegation through :class:`PDColor` is exercised. We pin the
    color-space identity so :meth:`PDColor.to_rgb` knows what to
    dispatch on.
    """

    def get_name(self) -> str:
        return "DeviceGray"  # piggy-back on Gray's PDColor.to_rgb path

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> Any:  # noqa: ANN401
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

        return PDColor([0.0], self)


def test_default_to_rgb_delegates_through_pd_color() -> None:
    """The base implementation builds a :class:`PDColor` and calls
    ``to_rgb()``. ``_NoToRGBOverride`` reports the same name as
    :class:`PDDeviceGray` so :meth:`PDColor.to_rgb` will route through
    the Gray-component dispatch arm.
    """
    # Sanity check: instantiating the no-override stub doesn't raise.
    assert _NoToRGBOverride().get_name() == "DeviceGray"
    # Call the base method directly through PDDeviceGray.INSTANCE — its
    # ``to_rgb`` override is skipped when we invoke the unbound method
    # explicitly via ``PDColorSpace.to_rgb(...)``.
    rgb = PDColorSpace.to_rgb(PDDeviceGray.INSTANCE, [0.5])
    assert rgb == [0.5, 0.5, 0.5]


# ---------- to_raw_image: DeviceCMYK fast path ----------------------------


class _BaseCMYKShaped(PDColorSpace):
    """Stub whose ``get_name()`` is ``DeviceCMYK`` and which does NOT
    override :meth:`to_raw_image`, so the base class's CMYK fast-path
    fires (line 352). ``PDDeviceCMYK`` itself overrides ``to_raw_image``
    to return ``None`` (the upstream "fallback to RGB" carve-out), so it
    can't be used to drive the base implementation directly.
    """

    def get_name(self) -> str:
        return "DeviceCMYK"

    def get_number_of_components(self) -> int:
        return 4

    def get_initial_color(self) -> Any:  # noqa: ANN401
        from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

        return PDColor([0.0, 0.0, 0.0, 1.0], self)


def test_to_raw_image_cmyk_shaped_base_returns_cmyk_image() -> None:
    """The base ``to_raw_image`` returns a Pillow ``CMYK`` image when the
    color-space name is ``DeviceCMYK`` and the component count is 4.
    """
    cs = _BaseCMYKShaped()
    # 1 pixel of (0, 0, 0, 0) — pure white in CMYK.
    raster = bytes([0, 0, 0, 0])
    img = cs.to_raw_image(raster, 1, 1)
    assert img.mode == "CMYK"
    assert img.size == (1, 1)


# ---------- __str__ -------------------------------------------------------


def test_str_returns_color_space_name() -> None:
    """``PDDeviceColorSpace`` overrides ``__str__`` but inherits via the
    base class's name-routing helper, and any custom subclass (like
    :class:`_BaseCMYKShaped`) hits the base ``__str__`` directly.
    """
    cs = _BaseCMYKShaped()
    assert str(cs) == "DeviceCMYK"


# ---------- additional defensive helper ----------------------------------


def test_create_from_cos_object_no_resources_unwraps_directly() -> None:
    """``create_from_cos_object`` with ``resources=None`` still resolves."""
    cos_obj = _make_cos_object_name("DeviceGray")
    out = PDColorSpace.create_from_cos_object(cos_obj, None)
    assert out is PDDeviceGray.INSTANCE


def test_create_from_cos_object_caches_array_form() -> None:
    """Array-form color spaces (Indexed etc.) also flow through the cache."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    palette = COSStream()
    with palette.create_output_stream() as out:
        out.write(b"\x00" * 12)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    arr.add(palette)  # placeholder — not used by PDIndexed init
    cos_obj = COSObject(2, 0, resolved=arr)
    cache = _StubCache()
    resources = _StubResources(cache)
    out_cs = PDColorSpace._create_from_cos_object(cos_obj, resources)
    assert isinstance(out_cs, PDIndexed)
    assert len(cache.puts) == 1
