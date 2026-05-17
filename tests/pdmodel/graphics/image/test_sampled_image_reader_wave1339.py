"""Coverage-boost wave 1339 tests for ``sampled_image_reader``.

Targets the remaining misses:
- Pillow-missing ``ImportError`` branches on the four entry points
- ``data = bytes(data)`` non-bytes coercion path
- ``padding_bits`` non-zero rounding (1-bit-deep, odd-width)
- subsampling tail with region offset (out-of-bounds clip)
- ``mode = "L"`` fallback when ``num_components`` is 2
- ``get_raw_raster`` Pillow-missing branch + sample_max=0 (bpc=0) edge
- ``MultipleInputStream`` exhausted-streams break path
- ``apply_color_key_mask`` Pillow-missing branch
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.graphics.image.sampled_image_reader import (
    MultipleInputStream,
    SampledImageReader,
)

pytest.importorskip("PIL")


# ---------- shared stubs ----------


class _StubColorSpace:
    def __init__(self, n: int) -> None:
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

    def create_input_stream(self, *_a, **_kw):
        return io.BytesIO(self._data)


# ---------- Pillow-missing branches ----------


def _block_pillow(monkeypatch) -> None:
    """Force ``import PIL.Image`` to raise ``ImportError``.

    We do this by inserting a sentinel into sys.modules — the ``from PIL
    import Image`` line then raises during the ``import`` lookup.
    """
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("PIL blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)


def test_get_stencil_image_returns_none_when_pillow_missing(monkeypatch) -> None:
    _block_pillow(monkeypatch)
    pd = _StubPDImage(1, 1, 1, b"\xff", components=1)
    assert SampledImageReader.get_stencil_image(pd, (1, 2, 3)) is None


def test_get_rgb_image_returns_none_when_pillow_missing(monkeypatch) -> None:
    _block_pillow(monkeypatch)
    pd = _StubPDImage(1, 1, 8, b"\x10\x20\x30", components=3)
    assert SampledImageReader.get_rgb_image(pd) is None


def test_get_raw_raster_returns_none_when_pillow_missing(monkeypatch) -> None:
    _block_pillow(monkeypatch)
    pd = _StubPDImage(1, 1, 8, b"\xff", components=1)
    assert SampledImageReader.get_raw_raster(pd) is None


def test_apply_color_key_mask_returns_image_when_pillow_missing(monkeypatch) -> None:
    _block_pillow(monkeypatch)
    sentinel = object()
    assert SampledImageReader.apply_color_key_mask(sentinel, object()) is sentinel


# ---------- bytes coercion + padding_bits ----------


class _NonBytesStream(io.RawIOBase):
    """``create_input_stream`` returns an object whose ``read()`` yields a
    ``memoryview`` (not bytes/bytearray) — exercises the ``bytes(data)``
    coercion path."""

    def __init__(self, data: bytes) -> None:
        super().__init__()
        self._data = data

    def read(self, n: int = -1) -> memoryview:
        return memoryview(self._data)

    def readable(self) -> bool:
        return True

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _MemoryViewPDImage(_StubPDImage):
    def create_input_stream(self, *_a, **_kw):
        return _NonBytesStream(self._data)


def test_get_rgb_image_coerces_memoryview_to_bytes() -> None:
    """Stream returning ``memoryview`` triggers the ``bytes(data)`` coerce."""
    pd = _MemoryViewPDImage(1, 1, 8, b"\x10\x20\x30", components=3)
    out = SampledImageReader.get_rgb_image(pd)
    assert out is not None
    assert out.load()[0, 0] == (0x10, 0x20, 0x30)


def test_get_raw_raster_coerces_memoryview_to_bytes() -> None:
    pd = _MemoryViewPDImage(1, 1, 8, b"\xab", components=1)
    out = SampledImageReader.get_raw_raster(pd)
    assert out is not None


def test_get_rgb_image_with_padding_bits_nonzero() -> None:
    """Width 3 × bpc 1 × 1 component -> 3 bits/row -> 5 padding bits per
    row. Hits the ``padding_bits = 8 - padding_bits`` branch."""
    pd = _StubPDImage(3, 1, 1, b"\xe0", components=1)  # bits: 1110_0000
    out = SampledImageReader.get_rgb_image(pd)
    assert out is not None
    assert out.size == (3, 1)


def test_get_raw_raster_with_padding_bits_nonzero() -> None:
    pd = _StubPDImage(3, 1, 1, b"\xe0", components=1)
    out = SampledImageReader.get_raw_raster(pd)
    assert out is not None


# ---------- decoded == d_min when sample_max == 0 ----------


def test_get_rgb_image_sample_max_zero_uses_dmin() -> None:
    """``bpc=0`` -> ``sample_max=0`` so the decoded value collapses to
    ``d_min`` (covers line 220)."""
    pd = _StubPDImage(1, 1, 0, b"", components=3)
    out = SampledImageReader.get_rgb_image(pd)
    assert out is not None


def test_get_raw_raster_sample_max_zero_uses_dmin() -> None:
    pd = _StubPDImage(1, 1, 0, b"", components=3)
    out = SampledImageReader.get_raw_raster(pd)
    assert out is not None


# ---------- region-offset clip skips ----------


def test_get_rgb_image_subsample_with_region_skips_outside() -> None:
    """A region whose offset clips the bottom/right rows triggers the
    ``out_y >= out_h`` / ``out_x >= out_w`` skip branches (lines 236, 244)."""
    # 4x4 image with subsampling=2 and a tiny region (1,1,2,2) starting
    # at (1,1) — the loop iterates over all 4 src rows but only y=1 and y=3
    # land inside the 2-pixel-tall region.
    data = bytes([i for i in range(4 * 4 * 3)])
    pd = _StubPDImage(4, 4, 8, data, components=3)
    out = SampledImageReader.get_rgb_image(pd, (1, 1, 2, 2), 2, None)
    assert out is not None
    assert out.size == (1, 1)


# ---------- 2-component grayscale fallback (mode=L) ----------


def test_get_raw_raster_2_components_falls_back_to_l() -> None:
    """A 2-component image (rare — alpha-masked grayscale) yields
    ``mode="L"`` per the ``else`` branch (line 252)."""
    pd = _StubPDImage(1, 1, 8, b"\xff\x00", components=2)
    out = SampledImageReader.get_raw_raster(pd)
    assert out is not None
    assert out.mode == "L"


def test_get_rgb_image_2_components_uses_l_pixel_path() -> None:
    """In the get_rgb_image RGB-output path, a 2-component sample takes
    the ``len(comps) != 1 and len(comps) < 3`` else branch which falls
    back to grayscale expansion (line 252)."""
    pd = _StubPDImage(1, 1, 8, b"\xff\x00", components=2)
    out = SampledImageReader.get_rgb_image(pd)
    assert out is not None
    assert out.mode == "RGB"


# ---------- MultipleInputStream break path ----------


def test_multiple_input_stream_readinto_breaks_when_exhausted() -> None:
    """``readinto`` with the buffer wider than the underlying total
    returns early via the ``break`` (line 456)."""
    s = MultipleInputStream([io.BytesIO(b"abc")])
    buf = bytearray(10)
    n = s.readinto(buf)
    assert n == 3
    assert bytes(buf[:3]) == b"abc"


def test_multiple_input_stream_empty_streams_returns_empty_read() -> None:
    s = MultipleInputStream([])
    assert s.read(10) == b""


# ---------- two-arg overload: color_key passed as first arg ----------


def test_get_rgb_image_color_key_via_first_positional_arg() -> None:
    """Calling ``get_rgb_image(pd_image, color_key)`` (the two-arg
    upstream overload) routes a non-4-tuple ``color_key_or_region`` into
    the ``color_key`` slot via the elif branch (line 137)."""

    class _CK:
        """Non-tuple, non-list color-key — bypasses the region detection."""

        def to_float_array(self) -> list[float]:
            return [0.0, 255.0]

    pd = _StubPDImage(1, 1, 8, b"\x10", components=1)
    out = SampledImageReader.get_rgb_image(pd, _CK())
    assert out is not None
    # Color key mask present -> RGBA output.
    assert out.mode == "RGBA"


def test_get_rgb_image_subsample_clips_outside_region_only() -> None:
    """A 4x4 image with region=(0,0,4,4) and subsampling=2 emits a 2x2
    output. The unsampled (odd) rows/cols hit the ``continue`` skip lines."""
    data = bytes([i & 0xFF for i in range(4 * 4 * 3)])
    pd = _StubPDImage(4, 4, 8, data, components=3)
    out = SampledImageReader.get_rgb_image(pd, (0, 0, 4, 4), 2, None)
    assert out is not None
    assert out.size == (2, 2)


def test_get_rgb_image_region_starts_partway_with_subsample() -> None:
    """Region offset by 1 with subsampling=2 hits both the
    ``(src_y - y) % sub != 0`` and ``out_y >= out_h`` skip branches."""
    data = bytes([i & 0xFF for i in range(6 * 6 * 3)])
    pd = _StubPDImage(6, 6, 8, data, components=3)
    out = SampledImageReader.get_rgb_image(pd, (1, 1, 3, 3), 2, None)
    assert out is not None
    # ceil(3/2) = 2 — output is 2x2.
    assert out.size == (2, 2)
