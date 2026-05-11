"""Tests for the bit-packed decode paths in ``SampledImageReader`` (Wave 1285).

Covers ``get_rgb_image`` (arbitrary bpc / colour-key mask) and
``get_raw_raster`` — both previously returned an empty / null image.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.graphics.image.sampled_image_reader import (
    SampledImageReader,
)

pytest.importorskip("PIL")


class _StubColorSpace:
    def __init__(self, n: int = 3) -> None:
        self._n = n

    def get_number_of_components(self) -> int:
        return self._n


class _StubDecode:
    def __init__(self, values: list[float] | None = None) -> None:
        self._values = values

    def size(self) -> int:
        return 0 if self._values is None else len(self._values)

    def to_float_array(self) -> list[float]:
        return list(self._values) if self._values is not None else []


class _StubPDImage:
    def __init__(
        self,
        width: int,
        height: int,
        bpc: int,
        data: bytes,
        components: int = 3,
        decode: list[float] | None = None,
    ) -> None:
        self._w = width
        self._h = height
        self._bpc = bpc
        self._data = data
        self._cs = _StubColorSpace(components)
        self._decode = _StubDecode(decode)

    def get_width(self) -> int:
        return self._w

    def get_height(self) -> int:
        return self._h

    def get_bits_per_component(self) -> int:
        return self._bpc

    def get_color_space(self):
        return self._cs

    def get_decode(self):
        return self._decode

    def is_empty(self) -> bool:
        return False

    def is_stencil(self) -> bool:
        return False

    def create_input_stream(self, *_args, **_kwargs):
        return io.BytesIO(self._data)


def test_get_rgb_image_8bpc_rgb_round_trip() -> None:
    # 2x2 RGB image: red, green, blue, white.
    data = bytes(
        [
            255, 0, 0,
            0, 255, 0,
            0, 0, 255,
            255, 255, 255,
        ]
    )
    image = SampledImageReader.get_rgb_image(
        _StubPDImage(2, 2, 8, data, components=3),
    )
    assert image is not None
    assert image.size == (2, 2)
    assert image.mode == "RGB"
    px = image.load()
    assert px[0, 0] == (255, 0, 0)
    assert px[1, 0] == (0, 255, 0)
    assert px[0, 1] == (0, 0, 255)
    assert px[1, 1] == (255, 255, 255)


def test_get_rgb_image_1bpc_gray_packs_correctly() -> None:
    # 8x1 image, 1bpc, alternating 1/0 bits => 10101010 = 0xAA
    data = bytes([0b10101010])
    img = SampledImageReader.get_rgb_image(
        _StubPDImage(8, 1, 1, data, components=1),
    )
    assert img.size == (8, 1)
    px = img.load()
    # decode default [0,1] means 1 -> 255, 0 -> 0
    expected = [255, 0, 255, 0, 255, 0, 255, 0]
    for i, v in enumerate(expected):
        assert px[i, 0] == (v, v, v)


def test_get_rgb_image_4bpc_two_pixels() -> None:
    # 2 pixels gray at 4bpc => one byte. 0xF0 -> pixel0=15, pixel1=0
    data = bytes([0xF0])
    img = SampledImageReader.get_rgb_image(
        _StubPDImage(2, 1, 4, data, components=1),
    )
    px = img.load()
    assert px[0, 0] == (255, 255, 255)
    assert px[1, 0] == (0, 0, 0)


def test_get_rgb_image_with_color_key_mask_returns_rgba() -> None:
    # 8bpc RGB, two pixels: pure red (masked) and pure blue (not masked).
    data = bytes([255, 0, 0, 0, 0, 255])
    color_key = [255.0, 255.0, 0.0, 0.0, 0.0, 0.0]  # red gets masked out
    img = SampledImageReader.get_rgb_image(
        _StubPDImage(2, 1, 8, data, components=3),
        None,
        1,
        color_key,
    )
    assert img.mode == "RGBA"
    px = img.load()
    assert px[0, 0][3] == 0  # masked
    assert px[1, 0][3] == 255  # not masked


def test_get_raw_raster_8bpc_rgb() -> None:
    data = bytes([10, 20, 30, 40, 50, 60])
    img = SampledImageReader.get_raw_raster(
        _StubPDImage(2, 1, 8, data, components=3),
    )
    assert img is not None
    assert img.mode == "RGB"
    px = img.load()
    assert px[0, 0] == (10, 20, 30)
    assert px[1, 0] == (40, 50, 60)


def test_get_raw_raster_8bpc_grayscale() -> None:
    data = bytes([10, 20, 30, 40])
    img = SampledImageReader.get_raw_raster(
        _StubPDImage(2, 2, 8, data, components=1),
    )
    assert img.mode == "L"
    px = img.load()
    assert px[0, 0] == 10
    assert px[1, 1] == 40


def test_get_raw_raster_8bpc_cmyk() -> None:
    data = bytes([10, 20, 30, 40])
    img = SampledImageReader.get_raw_raster(
        _StubPDImage(1, 1, 8, data, components=4),
    )
    assert img.mode == "CMYK"
    px = img.load()
    assert px[0, 0] == (10, 20, 30, 40)


def test_get_rgb_image_subsampling_halves_dimensions() -> None:
    data = bytes(
        [
            10, 20, 30, 40,
            50, 60, 70, 80,
            90, 100, 110, 120,
            130, 140, 150, 160,
        ]
    )
    img = SampledImageReader.get_rgb_image(
        _StubPDImage(4, 4, 8, data, components=1),
        None,
        2,
        None,
    )
    # 4x4 with subsampling=2 -> 2x2 output
    assert img.size == (2, 2)


def test_get_rgb_image_region_clips() -> None:
    data = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160])
    img = SampledImageReader.get_rgb_image(
        _StubPDImage(4, 4, 8, data, components=1),
        (1, 1, 2, 2),
        1,
        None,
    )
    assert img.size == (2, 2)
    px = img.load()
    # Top-left of the clipped region is the original (1, 1) pixel.
    assert px[0, 0] == (60, 60, 60)


def test_get_rgb_image_raises_on_empty_image() -> None:
    class _EmptyImage(_StubPDImage):
        def is_empty(self) -> bool:
            return True

    with pytest.raises(OSError, match="Image stream is empty"):
        SampledImageReader.get_rgb_image(_EmptyImage(2, 2, 8, b"", components=1))


def test_get_rgb_image_raises_on_nonpositive_dimensions() -> None:
    pd = _StubPDImage(0, 2, 8, b"", components=1)
    with pytest.raises(OSError, match="must be positive"):
        SampledImageReader.get_rgb_image(pd)
