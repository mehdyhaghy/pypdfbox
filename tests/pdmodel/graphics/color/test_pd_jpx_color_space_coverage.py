"""Coverage boost for ``PDJPXColorSpace`` (wave 1318).

Drives the fallback branches of ``get_number_of_components`` /
``get_default_decode`` / ``to_rgb`` plus the ``to_rgb_image`` / ``to_raw_image``
helpers that the wave-1281 smoke tests skipped.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.color import PDJPXColorSpace


class _AwtNumCompsAttr:
    """AWT stub exposing only the attribute-style ``num_components``."""

    num_components = 4

    def to_rgb(self, value: list[float]) -> list[float]:
        return list(value[:3])


class _AwtBare:
    """AWT stub with no component / decode / rgb hooks at all."""


def test_get_number_of_components_attribute_fallback() -> None:
    cs = PDJPXColorSpace(_AwtNumCompsAttr())
    assert cs.get_number_of_components() == 4


def test_get_number_of_components_default_when_missing() -> None:
    cs = PDJPXColorSpace(_AwtBare())
    assert cs.get_number_of_components() == 3


def test_get_default_decode_uses_unit_when_min_max_missing() -> None:
    cs = PDJPXColorSpace(_AwtBare())
    assert cs.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_to_rgb_default_truncates_when_awt_missing_to_rgb() -> None:
    cs = PDJPXColorSpace(_AwtBare())
    assert cs.to_rgb([0.1, 0.2, 0.3, 0.4]) == [0.1, 0.2, 0.3]


def test_to_rgb_delegates_to_awt_when_available() -> None:
    class _AwtDelegating:
        def to_rgb(self, value: list[float]) -> list[float]:
            # Return a tuple to ensure the cast to ``list`` is exercised.
            return tuple(v + 0.5 for v in value[:3])

    cs = PDJPXColorSpace(_AwtDelegating())
    rgb = cs.to_rgb([0.1, 0.2, 0.3])
    assert rgb == [0.6, 0.7, 0.8]
    assert isinstance(rgb, list)


def test_to_raw_image_returns_raster_unchanged() -> None:
    cs = PDJPXColorSpace(_AwtBare())
    sentinel = object()
    assert cs.to_raw_image(sentinel) is sentinel


def test_to_rgb_image_builds_pillow_image_from_raster() -> None:
    pillow = pytest.importorskip("PIL.Image")

    class _Raster:
        def get_width(self) -> int:
            return 2

        def get_height(self) -> int:
            return 2

        def get_pixel(self, x: int, y: int, buf: list[float]) -> list[float]:
            # Distinguish each pixel for assertions below.
            return [128.0 + x, 64.0 + y, 32.0]

    class _AwtIdentity:
        def get_num_components(self) -> int:
            return 3

        def get_min_value(self, i: int) -> float:
            return 0.0

        def get_max_value(self, i: int) -> float:
            return 1.0

        def to_rgb(self, value: list[float]) -> list[float]:
            return list(value)

    cs = PDJPXColorSpace(_AwtIdentity())
    image = cs.to_rgb_image(_Raster())
    assert image is not None
    assert image.size == (2, 2)
    assert image.mode == "RGB"
    # Each pixel is (R, G, B) after the *255 conversion from float [0,1].
    pixels = [image.getpixel((x, y)) for y in range(2) for x in range(2)]
    assert pixels[0] == (128, 64, 32)


def test_to_rgb_image_clamps_negative_and_oversaturated_values() -> None:
    pytest.importorskip("PIL.Image")

    class _Raster:
        def get_width(self) -> int:
            return 1

        def get_height(self) -> int:
            return 1

        def get_pixel(self, x: int, y: int, buf: list[float]) -> list[float]:
            return [255.0, 0.0, 255.0]

    class _AwtClamp:
        def get_num_components(self) -> int:
            return 3

        def get_min_value(self, i: int) -> float:
            return 0.0

        def get_max_value(self, i: int) -> float:
            return 1.0

        def to_rgb(self, value: list[float]) -> list[float]:
            # Force a negative and an over-1.0 value so both clamps fire.
            return [-1.0, 0.5, 2.5]

    cs = PDJPXColorSpace(_AwtClamp())
    image = cs.to_rgb_image(_Raster())
    pixel = image.getpixel((0, 0))
    assert pixel == (0, 127, 255)


def test_to_rgb_image_returns_none_when_pillow_missing(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("Pillow not installed (simulated)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    cs = PDJPXColorSpace(_AwtBare())
    assert cs.to_rgb_image(object()) is None
