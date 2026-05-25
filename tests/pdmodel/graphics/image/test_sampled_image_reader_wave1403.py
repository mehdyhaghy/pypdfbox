"""Wave 1403 branch-closure test for
:meth:`SampledImageReader.get_raw_raster`.

* ``330->313`` — a 4-component (CMYK) raster takes the ``elif mode ==
  "CMYK"`` pixel-write branch and then loops back to the next ``px``
  iteration. Previously only the L / RGB pixel modes were exercised, so
  the CMYK branch's continue-arc was untested.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.graphics.image.sampled_image_reader import SampledImageReader

pytest.importorskip("PIL")


class _StubColorSpace:
    def __init__(self, n: int) -> None:
        self._n = n

    def get_number_of_components(self) -> int:
        return self._n


class _StubDecode:
    def size(self) -> int:
        return 0

    def to_float_array(self) -> list[float]:
        return []


class _StubPDImage:
    def __init__(self, width: int, height: int, bpc: int, data: bytes, components: int) -> None:
        self._w = width
        self._h = height
        self._bpc = bpc
        self._data = data
        self._cs = _StubColorSpace(components)
        self._decode = _StubDecode()

    def get_width(self) -> int:
        return self._w

    def get_height(self) -> int:
        return self._h

    def get_bits_per_component(self) -> int:
        return self._bpc

    def get_color_space(self) -> _StubColorSpace:
        return self._cs

    def get_decode(self) -> _StubDecode:
        return self._decode

    def is_empty(self) -> bool:
        return False

    def is_stencil(self) -> bool:
        return False

    def create_input_stream(self, *_args, **_kwargs) -> io.BytesIO:
        return io.BytesIO(self._data)


def test_get_raw_raster_cmyk_writes_four_channel_pixels() -> None:
    """A 2x1 4-component image -> Pillow CMYK mode. Each pixel hits the
    ``elif mode == "CMYK"`` branch (330) and the inner ``px`` loop
    iterates back (330 -> 313) for the second column."""
    # 2 pixels x 4 components x 8 bpc = 8 bytes.
    data = bytes([0, 64, 128, 255, 10, 20, 30, 40])
    pd = _StubPDImage(2, 1, 8, data, components=4)
    out = SampledImageReader.get_raw_raster(pd)
    assert out.mode == "CMYK"
    assert out.size == (2, 1)
    # Both pixels are 4-tuples written via the CMYK branch.
    px0 = out.load()[0, 0]
    px1 = out.load()[1, 0]
    assert len(px0) == 4
    assert len(px1) == 4
