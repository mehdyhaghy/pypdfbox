"""Wave 1368 round-out tests for ``pypdfbox.pdmodel.graphics.color.pd_pattern``.

Targets:

- untinted (colored, ``/Pattern`` name form) vs tinted (uncolored,
  ``[/Pattern <CS>]`` array form) construction
- ``is_uncolored`` / ``is_colored`` / ``has_underlying_color_space``
- COS round-trip (name form returns COSName, array form returns COSArray)
- resources attachment surface (get/set/clear/has)
- ``get_pattern`` and ``get_pattern_or_none`` dispatch + error paths
- ``to_rgb`` for uncolored (recurse into underlying) and colored
  (return None — renderer territory)
- ``to_rgb_image`` / ``to_raw_image`` NotImplementedError shape
- ``get_default_decode`` NotImplementedError shape
- ``PDColorSpace.create`` dispatch for ``/Pattern`` name form, ``[/Pattern]``
  with no underlying, and ``[/Pattern <CS>]`` with underlying
- ``PDPattern`` initial color is empty
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

# ---------- defaults ----------


def test_pattern_default_is_colored_name_form() -> None:
    cs = PDPattern()
    assert cs.get_name() == "Pattern"
    assert cs.is_colored() is True
    assert cs.is_uncolored() is False
    assert cs.has_underlying_color_space() is False
    assert cs.get_underlying_color_space() is None


def test_pattern_colored_form_returns_cos_name() -> None:
    cs = PDPattern()
    cos = cs.get_cos_object()
    assert isinstance(cos, COSName)
    assert cos.get_name() == "Pattern"


def test_pattern_uncolored_form_returns_cos_array() -> None:
    cs = PDPattern(PDDeviceRGB.INSTANCE)
    cos = cs.get_cos_object()
    assert isinstance(cos, COSArray)
    assert cos.size() == 2
    assert cos.get_object(0).get_name() == "Pattern"


def test_pattern_uncolored_carries_underlying_color_space() -> None:
    cs = PDPattern(PDDeviceCMYK.INSTANCE)
    assert cs.is_uncolored() is True
    assert cs.is_colored() is False
    assert cs.has_underlying_color_space() is True
    assert cs.get_underlying_color_space() is PDDeviceCMYK.INSTANCE


def test_pattern_initial_color_is_empty() -> None:
    cs = PDPattern()
    initial = cs.get_initial_color()
    assert initial._components == []


def test_pattern_number_of_components_is_zero() -> None:
    cs = PDPattern()
    # Upstream throws UnsupportedOperationException — pypdfbox returns 0
    # as a safe sentinel (documented in pd_pattern.py).
    assert cs.get_number_of_components() == 0


# ---------- resources surface ----------


class _StubResources:
    def __init__(self, patterns: dict[str, object] | None = None) -> None:
        self._patterns = patterns or {}

    def get_pattern(self, name):
        if hasattr(name, "get_name"):
            name = name.get_name()
        return self._patterns.get(name)

    def get_resource_cache(self):  # pragma: no cover - not exercised here
        return None


def test_resources_round_trip() -> None:
    cs = PDPattern()
    assert cs.get_resources() is None
    assert cs.has_resources() is False
    resources = _StubResources()
    cs.set_resources(resources)
    assert cs.get_resources() is resources
    assert cs.has_resources() is True
    cs.clear_resources()
    assert cs.has_resources() is False


def test_pattern_constructor_accepts_resources() -> None:
    resources = _StubResources()
    cs = PDPattern(resources=resources)
    assert cs.get_resources() is resources


# ---------- get_pattern / get_pattern_or_none ----------


def test_get_pattern_raises_when_no_resources() -> None:
    cs = PDPattern()
    color = PDColor([], cs)
    with pytest.raises(OSError, match="requires PDResources"):
        cs.get_pattern(color)


def test_get_pattern_raises_when_color_has_no_pattern_name() -> None:
    resources = _StubResources()
    cs = PDPattern(resources=resources)
    color = PDColor([], cs)  # no pattern name
    with pytest.raises(OSError, match="no pattern name"):
        cs.get_pattern(color)


def test_get_pattern_raises_when_pattern_not_resolved() -> None:
    resources = _StubResources()  # empty pattern map
    cs = PDPattern(resources=resources)
    color = PDColor([], cs, pattern=COSName.get_pdf_name("P0"))
    with pytest.raises(OSError, match="not found"):
        cs.get_pattern(color)


def test_get_pattern_returns_resolved_pattern() -> None:
    sentinel_pattern = object()
    resources = _StubResources({"P0": sentinel_pattern})
    cs = PDPattern(resources=resources)
    color = PDColor([], cs, pattern=COSName.get_pdf_name("P0"))
    assert cs.get_pattern(color) is sentinel_pattern


def test_get_pattern_or_none_returns_none_for_missing_resources() -> None:
    cs = PDPattern()
    color = PDColor([], cs, pattern=COSName.get_pdf_name("P0"))
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_returns_none_when_no_pattern_name() -> None:
    resources = _StubResources()
    cs = PDPattern(resources=resources)
    color = PDColor([], cs)  # no pattern name
    assert cs.get_pattern_or_none(color) is None


def test_get_pattern_or_none_returns_pattern_when_resolved() -> None:
    sentinel = object()
    resources = _StubResources({"P0": sentinel})
    cs = PDPattern(resources=resources)
    color = PDColor([], cs, pattern=COSName.get_pdf_name("P0"))
    assert cs.get_pattern_or_none(color) is sentinel


# ---------- to_rgb ----------


def test_to_rgb_uncolored_recurses_into_underlying() -> None:
    """Uncolored pattern: tint components route through the underlying CS."""
    cs = PDPattern(PDDeviceGray.INSTANCE)
    rgb = cs.to_rgb([0.5])
    assert rgb is not None
    r, g, b = rgb
    # DeviceGray(0.5) → sRGB (0.5, 0.5, 0.5).
    assert r == 0.5
    assert g == 0.5
    assert b == 0.5


def test_to_rgb_colored_returns_none_for_pattern_with_no_underlying() -> None:
    cs = PDPattern()
    assert cs.to_rgb([]) is None


# ---------- to_rgb_image / to_raw_image / get_default_decode ----------


def test_to_rgb_image_is_not_supported() -> None:
    cs = PDPattern()
    with pytest.raises(NotImplementedError, match="is unsupported"):
        cs.to_rgb_image(b"\x00", 1, 1)


def test_to_raw_image_is_not_supported() -> None:
    cs = PDPattern()
    with pytest.raises(NotImplementedError, match="no native raster"):
        cs.to_raw_image(b"\x00", 1, 1)


def test_get_default_decode_is_not_supported() -> None:
    cs = PDPattern()
    with pytest.raises(NotImplementedError, match="has no default decode"):
        cs.get_default_decode(8)


# ---------- PDColorSpace.create dispatch ----------


def test_pdcolorspace_create_dispatches_pattern_name_to_colored() -> None:
    cs = PDColorSpace.create(COSName.get_pdf_name("Pattern"))
    assert isinstance(cs, PDPattern)
    assert cs.is_colored() is True


def test_pdcolorspace_create_dispatches_pattern_array_to_uncolored() -> None:
    """``[/Pattern <CS>]`` → uncolored pattern with underlying CS."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Pattern"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.is_uncolored() is True
    assert cs.get_underlying_color_space() is PDDeviceRGB.INSTANCE


def test_pdcolorspace_create_dispatches_empty_pattern_array_to_colored() -> None:
    """``[/Pattern]`` (no underlying) — pypdfbox treats as colored."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Pattern"))
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDPattern)
    assert cs.is_colored() is True


def test_pdcolorspace_create_propagates_resources_to_pattern() -> None:
    resources = _StubResources()
    cs = PDColorSpace.create(COSName.get_pdf_name("Pattern"), resources=resources)
    assert isinstance(cs, PDPattern)
    assert cs.get_resources() is resources


# ---------- string form ----------


def test_to_string_returns_literal_pattern_name() -> None:
    """Upstream returns the constant string ``"Pattern"`` even when an
    underlying CS is present."""
    assert PDPattern().to_string() == "Pattern"
    assert PDPattern(PDDeviceRGB.INSTANCE).to_string() == "Pattern"


# ---------- is_pattern predicate ----------


def test_is_pattern_predicate_is_true() -> None:
    cs = PDPattern()
    assert cs.is_pattern() is True
    assert cs.is_indexed() is False
    assert cs.is_separation() is False
    assert cs.is_device_n() is False
