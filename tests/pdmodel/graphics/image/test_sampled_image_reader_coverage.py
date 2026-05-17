"""Coverage-boost tests for ``pypdfbox.pdmodel.graphics.image.sampled_image_reader``.

Covers paths the Wave-1285 suite didn't reach:
- ``_BitReader``: zero-width read, EOF padding, ``align_to_byte``
- ``SampledImageReader`` constructor rejects instantiation
- ``get_stencil_image`` happy paths (paint as 3-tuple, 4-tuple), no-paint fallback
- ``get_rgb_image`` edge cases (color_space raises, color_key has wrong size,
  color_key has ``to_float_array``, short decode array, bytearray data,
  16bpc grayscale, subsampling-with-region offset)
- ``get_raw_raster`` (color_space raises, short decode, 2-component fallback to L)
- ``clip_region`` with bad tuple / None / clamping
- ``read_raster_from_any`` / ``from1_bit`` / ``from8bit`` / ``from_any``
- ``apply_color_key_mask`` (None inputs + happy path)
- ``get_decode_array`` parity passthrough
- ``_get_decode_array`` AttributeError branch (color_space lacks the method)
- ``MultipleInputStream`` read, readinto, read-all, close
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.graphics.image.sampled_image_reader import (
    MultipleInputStream,
    SampledImageReader,
    _BitReader,
    _get_decode_array,
)

pytest.importorskip("PIL")


# ---------- stubs (mirroring Wave-1285 shape so behaviour stays compatible) ----------


class _StubColorSpace:
    def __init__(self, n: int = 3) -> None:
        self._n = n

    def get_number_of_components(self) -> int:
        return self._n


class _NoComponentsCS:
    """Color space whose ``get_number_of_components`` raises ``OSError``."""

    def get_number_of_components(self) -> int:
        raise OSError("broken")


class _NoMethodCS:
    """Color space missing ``get_number_of_components`` entirely (AttributeError path)."""

    pass


class _StubDecode:
    def __init__(self, values: list[float] | None = None, raise_on_to_float: bool = False) -> None:
        self._values = values
        self._raise = raise_on_to_float

    def size(self) -> int:
        return 0 if self._values is None else len(self._values)

    def to_float_array(self) -> list[float]:
        if self._raise:
            raise TypeError("simulated")
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
        color_space: object | None = None,
        decode_obj: object | None = None,
    ) -> None:
        self._w = width
        self._h = height
        self._bpc = bpc
        self._data = data
        self._cs = color_space if color_space is not None else _StubColorSpace(components)
        self._decode = decode_obj if decode_obj is not None else _StubDecode(decode)

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


class _RaisingCSPDImage(_StubPDImage):
    """``get_color_space`` itself raises -> ``_get_decode_array`` AttributeError branch."""

    def get_color_space(self):
        raise OSError("boom")


# ---------- _BitReader ----------


def test_bit_reader_zero_width_read_returns_zero() -> None:
    r = _BitReader(b"\xff")
    assert r.read_bits(0) == 0


def test_bit_reader_pads_with_zero_past_eof() -> None:
    r = _BitReader(b"\xa0")  # 1010_0000
    # Consume 8 valid bits then 4 past-EOF bits.
    assert r.read_bits(8) == 0xA0
    assert r.read_bits(4) == 0


def test_bit_reader_align_to_byte_advances_when_partial() -> None:
    r = _BitReader(b"\xff\x55")
    assert r.read_bits(3) == 0b111
    r.align_to_byte()
    assert r.read_bits(8) == 0x55


def test_bit_reader_align_to_byte_is_noop_on_boundary() -> None:
    r = _BitReader(b"\xff\x00")
    assert r.read_bits(8) == 0xFF
    r.align_to_byte()  # already aligned
    assert r.read_bits(8) == 0


# ---------- constructor ----------


def test_constructor_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="static utility"):
        SampledImageReader()


# ---------- get_stencil_image ----------


def test_get_stencil_image_with_3tuple_paint_adds_alpha() -> None:
    # 2x1 image, bit pattern 10 -> first pixel painted, second masked out.
    pd = _StubPDImage(2, 1, 1, bytes([0b10000000]), components=1)
    out = SampledImageReader.get_stencil_image(pd, (200, 100, 50))
    assert out is not None
    assert out.mode == "RGBA"
    px = out.load()
    # Pixel 0 has bit=1, value=1 -> masked-to-transparent ((0,0,0,0)).
    assert px[0, 0] == (0, 0, 0, 0)
    # Pixel 1 has bit=0 -> keeps the paint fill with appended alpha=255.
    assert px[1, 0] == (200, 100, 50, 255)


def test_get_stencil_image_with_4tuple_paint_preserves_alpha() -> None:
    pd = _StubPDImage(2, 1, 1, bytes([0b01000000]), components=1)
    out = SampledImageReader.get_stencil_image(pd, (10, 20, 30, 128))
    px = out.load()
    # bit=0 at index 0 keeps paint with the supplied alpha.
    assert px[0, 0] == (10, 20, 30, 128)
    # bit=1 at index 1 masked out.
    assert px[1, 0] == (0, 0, 0, 0)


def test_get_stencil_image_without_paint_returns_image() -> None:
    pd = _StubPDImage(2, 1, 1, bytes([0b11000000]), components=1)
    out = SampledImageReader.get_stencil_image(pd, None)
    # All transparent (no fill applied), but call must not crash.
    assert out is not None
    assert out.size == (2, 1)


def test_get_stencil_image_short_data_breaks_early() -> None:
    pd = _StubPDImage(2, 2, 1, b"", components=1)
    out = SampledImageReader.get_stencil_image(pd, (1, 2, 3))
    assert out is not None
    assert out.size == (2, 2)


# ---------- get_rgb_image edge cases ----------


def test_get_rgb_image_color_space_oserror_defaults_to_single_component() -> None:
    # bpc=8, 1x1 with broken color space -> ``num_components`` defaults to 1.
    pd = _StubPDImage(1, 1, 8, b"\x42", color_space=_NoComponentsCS())
    out = SampledImageReader.get_rgb_image(pd)
    assert out is not None
    assert out.load()[0, 0] == (0x42, 0x42, 0x42)


def test_get_rgb_image_with_color_key_to_float_array() -> None:
    """``color_key`` exposing ``to_float_array`` (COSArray-like) is honoured."""

    class _CKArray:
        def to_float_array(self) -> list[float]:
            return [255.0, 255.0, 0.0, 0.0, 0.0, 0.0]

    pd = _StubPDImage(2, 1, 8, bytes([255, 0, 0, 0, 0, 255]), components=3)
    out = SampledImageReader.get_rgb_image(pd, None, 1, _CKArray())
    assert out.mode == "RGBA"


def test_get_rgb_image_with_short_color_key_warning_path() -> None:
    # color_key too small -> log warning, treat as if no mask -> mode stays RGB.
    pd = _StubPDImage(1, 1, 8, b"\x10\x20\x30", components=3)
    out = SampledImageReader.get_rgb_image(pd, None, 1, [0.0, 0.0])
    assert out.mode == "RGB"


def test_get_rgb_image_with_invalid_color_key_object_falls_back_to_no_mask() -> None:
    """``color_key`` whose iteration raises ``TypeError`` -> treated as no mask."""

    class _Bad:
        def __iter__(self):
            raise TypeError("nope")

    pd = _StubPDImage(1, 1, 8, b"\x10\x20\x30", components=3)
    out = SampledImageReader.get_rgb_image(pd, None, 1, _Bad())
    assert out.mode == "RGB"


def test_get_rgb_image_with_short_decode_array_gets_padded() -> None:
    # decode list of just one float -> defensive padding kicks in.
    pd = _StubPDImage(1, 1, 8, b"\xff\x00\x80", components=3, decode=[0.0])
    out = SampledImageReader.get_rgb_image(pd)
    assert out is not None


def test_get_rgb_image_accepts_bytearray_stream_data() -> None:
    class _BA(_StubPDImage):
        def create_input_stream(self, *_args, **_kwargs):
            class _Reader:
                def __init__(self, b):
                    self._b = bytearray(b)

                def read(self):
                    return self._b  # bytearray, not bytes

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

            return _Reader(self._data)

    pd = _BA(1, 1, 8, b"\x55\x66\x77", components=3)
    out = SampledImageReader.get_rgb_image(pd)
    assert out.load()[0, 0] == (0x55, 0x66, 0x77)


def test_get_rgb_image_16bpc_grayscale_scales_to_8bit() -> None:
    # 2 pixels gray @ 16bpc -> 4 bytes total.
    data = bytes([0xFF, 0xFF, 0x00, 0x00])
    pd = _StubPDImage(2, 1, 16, data, components=1)
    out = SampledImageReader.get_rgb_image(pd)
    px = out.load()
    assert px[0, 0] == (255, 255, 255)
    assert px[1, 0] == (0, 0, 0)


def test_get_rgb_image_region_with_subsampling_skips_offset_pixels() -> None:
    # 4x1 @ 8bpc gray, region (1,0,3,1), sub=2 -> takes src_x=1,3.
    data = bytes([10, 20, 30, 40])
    pd = _StubPDImage(4, 1, 8, data, components=1)
    out = SampledImageReader.get_rgb_image(pd, (1, 0, 3, 1), 2, None)
    px = out.load()
    assert out.size[1] == 1
    # src_x=1 -> gray=20, src_x=3 -> gray=40.
    assert px[0, 0] == (20, 20, 20)


# ---------- get_raw_raster ----------


def test_get_raw_raster_color_space_oserror_defaults_to_L_mode() -> None:
    pd = _StubPDImage(1, 1, 8, b"\x77", color_space=_NoComponentsCS())
    out = SampledImageReader.get_raw_raster(pd)
    assert out.mode == "L"
    assert out.load()[0, 0] == 0x77


def test_get_raw_raster_two_components_falls_back_to_L() -> None:
    # 2-component image has no Pillow mode -> falls back to "L".
    pd = _StubPDImage(1, 1, 8, b"\x10\x20", components=2)
    out = SampledImageReader.get_raw_raster(pd)
    assert out.mode == "L"


def test_get_raw_raster_short_decode_array_is_padded() -> None:
    pd = _StubPDImage(1, 1, 8, b"\xff\x80\x00", components=3, decode=[0.0])
    out = SampledImageReader.get_raw_raster(pd)
    assert out.mode == "RGB"


def test_get_raw_raster_raises_on_empty() -> None:
    class _E(_StubPDImage):
        def is_empty(self) -> bool:
            return True

    with pytest.raises(OSError, match="empty"):
        SampledImageReader.get_raw_raster(_E(1, 1, 8, b"", components=1))


def test_get_raw_raster_raises_on_nonpositive_dim() -> None:
    pd = _StubPDImage(0, 1, 8, b"", components=1)
    with pytest.raises(OSError, match="must be positive"):
        SampledImageReader.get_raw_raster(pd)


# ---------- clip_region ----------


def test_clip_region_with_none_returns_full_image() -> None:
    pd = _StubPDImage(10, 20, 8, b"", components=1)
    assert SampledImageReader.clip_region(pd, None) == (0, 0, 10, 20)


def test_clip_region_with_unpackable_region_returns_full_image() -> None:
    pd = _StubPDImage(10, 20, 8, b"", components=1)
    assert SampledImageReader.clip_region(pd, (1, 2, 3)) == (0, 0, 10, 20)
    assert SampledImageReader.clip_region(pd, "bad") == (0, 0, 10, 20)


def test_clip_region_clamps_to_image_bounds() -> None:
    pd = _StubPDImage(10, 10, 8, b"", components=1)
    assert SampledImageReader.clip_region(pd, (5, 5, 100, 100)) == (5, 5, 5, 5)


def test_clip_region_negative_origin_is_clamped() -> None:
    pd = _StubPDImage(10, 10, 8, b"", components=1)
    assert SampledImageReader.clip_region(pd, (-3, -3, 4, 4)) == (0, 0, 4, 4)


# ---------- thin parity stubs ----------


def test_read_raster_from_any_is_a_noop() -> None:
    pd = _StubPDImage(1, 1, 8, b"\x00", components=1)
    assert SampledImageReader.read_raster_from_any(pd, None) is None


def test_from1_bit_delegates_to_get_rgb_image() -> None:
    pd = _StubPDImage(8, 1, 1, bytes([0b11001100]), components=1)
    out = SampledImageReader.from1_bit(pd, None, 1, 8, 1)
    assert out is not None
    assert out.size == (8, 1)


def test_from8bit_delegates_to_get_rgb_image() -> None:
    pd = _StubPDImage(1, 1, 8, b"\x40", components=1)
    out = SampledImageReader.from8bit(pd, None, None, 1, 1, 1)
    assert out.load()[0, 0] == (0x40, 0x40, 0x40)


def test_from_any_delegates_with_color_key() -> None:
    pd = _StubPDImage(1, 1, 8, b"\x10\x20\x30", components=3)
    out = SampledImageReader.from_any(pd, None, None, None, 1, 1, 1)
    assert out is not None


# ---------- apply_color_key_mask ----------


def test_apply_color_key_mask_with_none_image_returns_none() -> None:
    assert SampledImageReader.apply_color_key_mask(None, object()) is None


def test_apply_color_key_mask_with_none_mask_returns_image() -> None:
    sentinel = object()
    assert SampledImageReader.apply_color_key_mask(sentinel, None) is sentinel


def test_apply_color_key_mask_calls_putalpha_when_available() -> None:
    calls = []

    class _Img:
        def putalpha(self, m):
            calls.append(m)

    img = _Img()
    out = SampledImageReader.apply_color_key_mask(img, "mask")
    assert out is img
    assert calls == ["mask"]


def test_apply_color_key_mask_swallows_attribute_error() -> None:
    class _NoMethod:
        pass  # no putalpha

    inst = _NoMethod()
    assert SampledImageReader.apply_color_key_mask(inst, "m") is inst


# ---------- get_decode_array / _get_decode_array ----------


def test_get_decode_array_passthrough() -> None:
    pd = _StubPDImage(1, 1, 8, b"\x00", components=3, decode=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    assert SampledImageReader.get_decode_array(pd) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_get_decode_array_defaults_when_decode_none() -> None:
    class _NoDecode(_StubPDImage):
        def get_decode(self):
            return None

    pd = _NoDecode(1, 1, 8, b"", components=2)
    assert _get_decode_array(pd) == [0.0, 1.0, 0.0, 1.0]


def test_get_decode_array_defaults_when_decode_empty_and_color_space_oserror() -> None:
    pd = _RaisingCSPDImage(1, 1, 8, b"", components=1)
    # Default num=1 path when both color space AND decode are unavailable.
    assert _get_decode_array(pd) == [0.0, 1.0]


def test_get_decode_array_handles_to_float_array_failure() -> None:
    # Decode object whose ``to_float_array`` raises -> returns [0.0, 1.0].
    pd = _StubPDImage(
        1, 1, 8, b"", components=1,
        decode_obj=_StubDecode([0.5], raise_on_to_float=True),
    )
    assert _get_decode_array(pd) == [0.0, 1.0]


# ---------- MultipleInputStream ----------


def test_multiple_input_stream_readable_is_true() -> None:
    mis = MultipleInputStream([io.BytesIO(b"")])
    assert mis.readable() is True


def test_multiple_input_stream_read_all_concatenates() -> None:
    mis = MultipleInputStream([io.BytesIO(b"aaa"), io.BytesIO(b"bbb"), io.BytesIO(b"")])
    assert mis.read(-1) == b"aaabbb"


def test_multiple_input_stream_read_n_spans_streams() -> None:
    mis = MultipleInputStream([io.BytesIO(b"aaa"), io.BytesIO(b"bbb")])
    out = mis.read(5)
    assert out == b"aaabb"


def test_multiple_input_stream_read_more_than_available() -> None:
    mis = MultipleInputStream([io.BytesIO(b"x"), io.BytesIO(b"y")])
    assert mis.read(50) == b"xy"


def test_multiple_input_stream_readinto_fills_buffer_across_streams() -> None:
    mis = MultipleInputStream([io.BytesIO(b"abc"), io.BytesIO(b"de")])
    buf = bytearray(5)
    n = mis.readinto(buf)
    assert n == 5
    assert bytes(buf) == b"abcde"


def test_multiple_input_stream_close_closes_each_stream() -> None:
    s1, s2 = io.BytesIO(b"a"), io.BytesIO(b"b")
    mis = MultipleInputStream([s1, s2])
    mis.close()
    assert s1.closed and s2.closed


def test_multiple_input_stream_close_tolerates_oserror() -> None:
    class _BadClose:
        closed = False

        def close(self) -> None:
            raise OSError("nope")

    s = _BadClose()
    mis = MultipleInputStream([s])
    # Must not propagate even if a child's ``close`` raises.
    mis.close()
