"""The vectorized sample unpack and /Decode paths match the original loops."""

from __future__ import annotations

import math
import random

import pytest

from pypdfbox.pdmodel.graphics.image import pd_image_x_object as mod


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _reference_decode(data, pixel_count, components, decode, *, bpc=8):
    expected = pixel_count * components
    if len(data) < expected:
        return None
    if decode is None and bpc == 8:
        return data[:expected]
    if decode is None:
        decode = [0.0, 1.0] * components
    elif len(decode) != components * 2:
        return None
    max_sample = float((1 << int(bpc)) - 1)
    out = bytearray(expected)
    for i in range(expected):
        component = i % components
        dmin = decode[component * 2]
        dmax = decode[component * 2 + 1]
        value = dmin + (data[i] / max_sample) * (dmax - dmin)
        out[i] = int(round(_clamp01(value) * 255.0))
    return bytes(out)


def _reference_unpack(data, width, height, bpc, components=1):
    if bpc not in (1, 2, 4) or components <= 0:
        return None
    row_samples = int(width) * int(components)
    row_bytes = (row_samples * int(bpc) + 7) // 8
    expected = row_bytes * int(height)
    if len(data) < expected:
        return None
    mask = (1 << int(bpc)) - 1
    out = bytearray(row_samples * int(height))
    for y in range(int(height)):
        for s in range(row_samples):
            bit = s * int(bpc)
            byte = data[y * row_bytes + bit // 8]
            out[y * row_samples + s] = (byte >> (8 - int(bpc) - bit % 8)) & mask
    return bytes(out)


@pytest.mark.parametrize("bpc", [1, 2, 4])
@pytest.mark.parametrize("components", [1, 3, 4])
def test_unpack_matches_reference(bpc: int, components: int) -> None:
    rng = random.Random(bpc * 10 + components)
    for width, height in [(1, 1), (7, 3), (13, 5), (64, 2), (0, 4), (3, 0)]:
        row_bytes = (width * components * bpc + 7) // 8
        data = bytes(rng.randrange(256) for _ in range(row_bytes * height + 3))
        assert mod._unpack_sub_byte_samples(
            data, width, height, bpc, components
        ) == _reference_unpack(data, width, height, bpc, components)


def test_unpack_rejects_like_reference() -> None:
    assert mod._unpack_sub_byte_samples(b"\x00", 9, 1, 1) is None
    assert mod._unpack_sub_byte_samples(b"\x00", 1, 1, 3) is None
    assert mod._unpack_sub_byte_samples(b"\x00", 1, 1, 1, components=0) is None


_DECODES = [
    None,
    [0.0, 1.0],
    [1.0, 0.0],
    [0.25, 0.75],
    [-0.5, 1.5],
    [0, 1],
    [0.1, 0.10000001],
    [1e300, -1e300],
]


@pytest.mark.parametrize("bpc", [1, 2, 4, 8])
@pytest.mark.parametrize("components", [1, 3, 4])
@pytest.mark.parametrize("decode_index", range(len(_DECODES)))
def test_decode_matches_reference(bpc: int, components: int, decode_index: int) -> None:
    base = _DECODES[decode_index]
    decode = None if base is None else [v for _ in range(components) for v in base]
    rng = random.Random(bpc + components * 7 + decode_index * 31)
    pixel_count = 257
    data = bytes(rng.randrange(1 << bpc) for _ in range(pixel_count * components))
    # every possible sample value at least once
    data = bytes(range(1 << bpc)) * components + data
    pixel_count += 1 << bpc
    assert mod._apply_decode_to_8bit_samples(
        data, pixel_count, components, decode, bpc=bpc
    ) == _reference_decode(data, pixel_count, components, decode, bpc=bpc)


def test_decode_bytearray_and_memoryview_inputs() -> None:
    data = bytes(range(256)) * 3
    for wrapped in (bytearray(data), memoryview(data)):
        assert mod._apply_decode_to_8bit_samples(
            wrapped, 256, 3, [1.0, 0.0] * 3
        ) == _reference_decode(data, 256, 3, [1.0, 0.0] * 3)


def test_nan_decode_raises_like_the_loop() -> None:
    with pytest.raises(ValueError):
        _reference_decode(b"\x00\x01", 2, 1, [math.nan, 1.0])
    with pytest.raises(ValueError):
        mod._apply_decode_to_8bit_samples(b"\x00\x01", 2, 1, [math.nan, 1.0])


def test_unused_failing_entry_does_not_raise() -> None:
    # dmin + 0 * (inf - dmin) is NaN only for sample 0, which the data lacks
    decode = [0.0, math.inf]
    data = b"\x05\x07"
    assert mod._apply_decode_to_8bit_samples(
        data, 2, 1, decode
    ) == _reference_decode(data, 2, 1, decode)
