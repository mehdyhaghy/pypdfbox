"""Coverage-boost tests for ``PDCIEBasedColorSpace``.

Covers the abstract base's concrete surface: ``to_rgb_image``,
``to_raw_image``, ``to_string`` / ``__str__``. The class is abstract,
so we build a minimal concrete subclass implementing the two abstract
hooks (``to_rgb`` and ``get_name``).
"""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.color.pd_cie_based_color_space import (
    PDCIEBasedColorSpace,
)


class _FakeRaster:
    """Bare-bones raster mirroring the AWT-style contract that
    ``PDCIEBasedColorSpace.to_rgb_image`` expects: width/height accessors
    and ``get_pixel(x, y, abc)`` returning a 3-tuple of 0..255 samples.
    """

    def __init__(self, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
        self._width = width
        self._height = height
        # pixels indexed row-major: pixels[y * width + x]
        self._pixels = pixels

    def get_width(self) -> int:
        return self._width

    def get_height(self) -> int:
        return self._height

    def get_pixel(self, x: int, y: int, _abc: list[float]) -> list[float]:
        r, g, b = self._pixels[y * self._width + x]
        return [float(r), float(g), float(b)]


class _Concrete(PDCIEBasedColorSpace):
    """Minimal concrete CIE color space for testing the base surface."""

    def __init__(self, name: str = "FakeCIE") -> None:
        super().__init__()
        self._name = name

    def to_rgb(self, value: list[float]) -> list[float]:
        # Identity in the unit cube — easy to verify pixel output.
        return [value[0], value[1], value[2]]

    def get_name(self) -> str:
        return self._name

    def get_number_of_components(self) -> int:  # pragma: no cover - unused here
        return 3

    def get_initial_color(self):  # pragma: no cover - unused here
        return None


class _OverflowConcrete(_Concrete):
    """A subclass whose ``to_rgb`` returns out-of-range values so the
    clamp branches in the base ``to_rgb_image`` get exercised.
    """

    def to_rgb(self, value: list[float]) -> list[float]:
        # Force one channel below 0, one above 1, one in-range.
        return [-0.5, 2.0, 0.5]


def test_to_rgb_image_returns_none_for_none_raster() -> None:
    cs = _Concrete()
    assert cs.to_rgb_image(None) is None


def test_to_rgb_image_single_pixel_identity_round_trips() -> None:
    cs = _Concrete()
    raster = _FakeRaster(1, 1, [(255, 128, 0)])
    img = cs.to_rgb_image(raster)
    assert img is not None
    assert img.size == (1, 1)
    pixel = img.getpixel((0, 0))
    # 255/255=1.0 -> 255; 128/255 ~= 0.502 -> 128; 0/255=0 -> 0
    assert pixel[0] == 255
    assert pixel[2] == 0
    assert 127 <= pixel[1] <= 128


def test_to_rgb_image_multi_pixel_dimensions_match() -> None:
    cs = _Concrete()
    raster = _FakeRaster(
        2,
        2,
        [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0)],
    )
    img = cs.to_rgb_image(raster)
    assert img is not None
    assert img.size == (2, 2)
    assert img.getpixel((0, 0)) == (0, 0, 0)
    assert img.getpixel((1, 0)) == (255, 255, 255)
    assert img.getpixel((0, 1))[0] == 255
    assert img.getpixel((1, 1))[1] == 255


def test_to_rgb_image_clamps_out_of_range_values() -> None:
    cs = _OverflowConcrete()
    raster = _FakeRaster(1, 1, [(128, 128, 128)])
    img = cs.to_rgb_image(raster)
    assert img is not None
    # -0.5 -> clamped to 0; 2.0 -> clamped to 255; 0.5 -> 127
    r, g, b = img.getpixel((0, 0))
    assert r == 0
    assert g == 255
    assert 127 <= b <= 128


def test_to_raw_image_always_returns_none() -> None:
    cs = _Concrete()
    raster = _FakeRaster(1, 1, [(0, 0, 0)])
    assert cs.to_raw_image(raster) is None
    assert cs.to_raw_image(None) is None


def test_to_string_returns_get_name() -> None:
    cs = _Concrete("Lab")
    assert cs.to_string() == "Lab"


def test_dunder_str_returns_get_name() -> None:
    cs = _Concrete("CalRGB")
    assert str(cs) == "CalRGB"


def test_to_rgb_image_uses_supplied_zero_size_raster() -> None:
    """A 0x0 raster should yield an empty image without iterating any pixels."""
    cs = _Concrete()
    raster = _FakeRaster(0, 0, [])
    img = cs.to_rgb_image(raster)
    assert img is not None
    assert img.size == (0, 0)
