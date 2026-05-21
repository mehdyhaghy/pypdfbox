"""Hand-written tests for ``PDShadingType7.parse_patches``.

Cover the geometry-only tensor-product patch-stream decoder added in
wave 1374: each patch carries 16 control points (12 boundary + 4
interior) and 4 corner colours. The decoder shares the bit-reader and
the flag-driven shared-edge logic with Type 6 but with
``control_points=16``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.shading.pd_mesh_based_shading_type import (
    ParsedPatch,
    parse_patch_stream,
)
from pypdfbox.pdmodel.graphics.shading.pd_shading_type7 import PDShadingType7


def _set_device_gray_color_space(shading: PDShadingType7) -> None:
    """Attach ``/DeviceGray`` so ``get_number_of_color_components()``
    returns 1 for the wrapper-level tests."""
    shading.set_color_space(COSName.get_pdf_name("DeviceGray"))


def _pack_bits(bits: list[int]) -> bytes:
    while len(bits) % 8:
        bits.append(0)
    return bytes(
        int("".join(str(b) for b in bits[i : i + 8]), 2)
        for i in range(0, len(bits), 8)
    )


def _bits_msb(value: int, width: int) -> list[int]:
    return [(value >> (width - 1 - i)) & 1 for i in range(width)]


def _build_patch_stream(
    items: Iterable[tuple[int, list[tuple[int, int]], list[list[int]]]],
    *,
    bpf: int = 2,
    bpc: int = 8,
    bcc: int = 8,
) -> bytes:
    out: list[int] = []
    for flag, coords, colors in items:
        out.extend(_bits_msb(flag, bpf))
        for x, y in coords:
            out.extend(_bits_msb(x, bpc))
            out.extend(_bits_msb(y, bpc))
        for color in colors:
            for component in color:
                out.extend(_bits_msb(component, bcc))
    return _pack_bits(out)


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


# ----------------------------------------------------------------------
# Single free tensor patch (16 control points)
# ----------------------------------------------------------------------


def test_parse_patches_single_free_tensor_patch_decodes_16_points() -> None:
    coords = [(i, 50 + i * 2) for i in range(16)]
    colors = [[10], [20], [30], [40]]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=16,
    )

    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, ParsedPatch)
    assert patch.flag == 0
    assert len(patch.points) == 16
    assert len(patch.colors) == 4
    for i in range(16):
        assert _close(patch.points[i][0], float(i))
        assert _close(patch.points[i][1], 50.0 + float(i * 2))
    assert [c[0] for c in patch.colors] == [10.0, 20.0, 30.0, 40.0]


def test_parse_patches_tensor_patch_interior_points_are_decoded() -> None:
    # Interior control points (indices 12-15 per upstream tensor layout)
    # are unique to Type 7 and must not be silently dropped.
    coords = [(0, 0)] * 12 + [(200, 100), (150, 80), (100, 60), (50, 40)]
    colors = [[0], [85], [170], [255]]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=16,
    )

    assert len(patches) == 1
    interior = patches[0].points[12:16]
    assert interior[0] == pytest.approx((200.0, 100.0))
    assert interior[1] == pytest.approx((150.0, 80.0))
    assert interior[2] == pytest.approx((100.0, 60.0))
    assert interior[3] == pytest.approx((50.0, 40.0))


# ----------------------------------------------------------------------
# Two tensor patches with shared edge
# ----------------------------------------------------------------------


def test_parse_patches_tensor_flag2_shares_trailing_edge_with_previous_patch() -> None:
    coords1 = [(i * 5, 20 + i * 3) for i in range(16)]
    colors1 = [[10], [20], [30], [40]]
    # flag=2: first 4 control points inherited (pts[6..9]), 2 corner
    # colours inherited (colours[2..3]); 12 fresh control points + 2
    # fresh corner colours decoded.
    coords2 = [(180 + i * 2, 40 + i) for i in range(12)]
    colors2 = [[50], [60]]
    data = _build_patch_stream([(0, coords1, colors1), (2, coords2, colors2)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=16,
    )

    assert len(patches) == 2
    assert patches[1].flag == 2
    # First 4 control points of patch 1 == pts[6..9] of patch 0
    assert patches[1].points[:4] == patches[0].points[6:10]
    # First 2 corner colours inherited
    assert patches[1].colors[:2] == patches[0].colors[2:4]
    # Remaining 12 control points are fresh from the stream
    for i in range(12):
        assert _close(patches[1].points[4 + i][0], 180.0 + float(i * 2))
        assert _close(patches[1].points[4 + i][1], 40.0 + float(i))
    # Fresh corner colours land at indices 2-3
    assert patches[1].colors[2] == [50.0]
    assert patches[1].colors[3] == [60.0]


@pytest.mark.parametrize(
    ("flag", "expected_edge_indices", "expected_color_indices"),
    [
        (1, [3, 4, 5, 6], [1, 2]),
        (3, [9, 10, 11, 0], [3, 0]),
    ],
    ids=["flag1_tensor", "flag3_tensor"],
)
def test_parse_patches_tensor_other_shared_flags_inherit_correct_edge(
    flag: int,
    expected_edge_indices: list[int],
    expected_color_indices: list[int],
) -> None:
    coords1 = [(i * 3, 100 - i * 4) for i in range(16)]
    colors1 = [[5], [25], [45], [65]]
    coords2 = [(150 + i, 25 + i) for i in range(12)]
    colors2 = [[80], [90]]
    data = _build_patch_stream([(0, coords1, colors1), (flag, coords2, colors2)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=16,
    )

    assert len(patches) == 2
    assert patches[1].flag == flag
    for slot, src in enumerate(expected_edge_indices):
        assert patches[1].points[slot] == patches[0].points[src]
    for slot, src in enumerate(expected_color_indices):
        assert patches[1].colors[slot] == patches[0].colors[src]


# ----------------------------------------------------------------------
# /Decode and multi-component interpolation
# ----------------------------------------------------------------------


def test_parse_patches_tensor_decode_remaps_to_user_range() -> None:
    coords = [(0, 0)] * 15 + [(255, 255)]
    colors = [[0], [255], [0], [255]]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[100, 200, -100, 100, 0, 1],
        num_color_components=1,
        control_points=16,
    )

    assert _close(patches[0].points[0][0], 100.0)
    assert _close(patches[0].points[0][1], -100.0)
    assert _close(patches[0].points[15][0], 200.0)
    assert _close(patches[0].points[15][1], 100.0)
    assert _close(patches[0].colors[0][0], 0.0)
    assert _close(patches[0].colors[1][0], 1.0)


def test_parse_patches_tensor_handles_cmyk_4_component_colors() -> None:
    coords = [(i, i) for i in range(16)]
    colors = [
        [255, 0, 0, 0],
        [0, 255, 0, 0],
        [0, 0, 255, 0],
        [0, 0, 0, 255],
    ]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        num_color_components=4,
        control_points=16,
    )

    assert len(patches) == 1
    assert patches[0].colors[0] == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert patches[0].colors[1] == pytest.approx([0.0, 1.0, 0.0, 0.0])
    assert patches[0].colors[2] == pytest.approx([0.0, 0.0, 1.0, 0.0])
    assert patches[0].colors[3] == pytest.approx([0.0, 0.0, 0.0, 1.0])


# ----------------------------------------------------------------------
# Defensive paths
# ----------------------------------------------------------------------


def test_parse_patches_tensor_empty_stream_returns_empty_list() -> None:
    patches = parse_patch_stream(
        b"",
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=16,
    )
    assert patches == []


def test_parse_patches_tensor_truncated_stream_drops_incomplete_patch() -> None:
    coords1 = [(i, i) for i in range(16)]
    colors1 = [[10], [20], [30], [40]]
    data = _build_patch_stream([(0, coords1, colors1)])
    # Append a partial second patch.
    coords2 = [(0, 0)] * 4
    data += _build_patch_stream([(0, coords2, [])])[:5]

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=16,
    )

    assert len(patches) == 1


# ----------------------------------------------------------------------
# Class-level wrapper exercises COSStream + /Decode plumbing
# ----------------------------------------------------------------------


def test_pd_shading_type7_parse_patches_uses_dictionary_metadata() -> None:
    coords = [(i * 2, 100 - i) for i in range(16)]
    colors = [[0], [85], [170], [255]]
    stream_body = _build_patch_stream([(0, coords, colors)])

    shading = PDShadingType7()
    _set_device_gray_color_space(shading)
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    decode_arr = COSArray()
    decode_arr.set_float_array([0, 255, 0, 255, 0, 255])
    shading.set_decode(decode_arr)

    stream = shading.get_cos_object()
    assert isinstance(stream, COSStream)
    with stream.create_output_stream() as sink:
        sink.write(stream_body)

    patches = shading.parse_patches()
    assert len(patches) == 1
    assert patches[0].flag == 0
    assert len(patches[0].points) == 16
    assert _close(patches[0].points[0][0], 0.0)
    assert _close(patches[0].points[15][0], 30.0)
    assert _close(patches[0].points[15][1], 85.0)
    assert [c[0] for c in patches[0].colors] == pytest.approx([0.0, 85.0, 170.0, 255.0])


def test_pd_shading_type7_parse_patches_accepts_explicit_bytes() -> None:
    coords = [(i, i) for i in range(16)]
    colors = [[1], [2], [3], [4]]
    stream_body = _build_patch_stream([(0, coords, colors)])

    shading = PDShadingType7()
    _set_device_gray_color_space(shading)
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    decode_arr = COSArray()
    decode_arr.set_float_array([0, 255, 0, 255, 0, 255])
    shading.set_decode(decode_arr)

    patches = shading.parse_patches(stream_body)
    assert len(patches) == 1
    assert patches[0].colors == [[1.0], [2.0], [3.0], [4.0]]


def test_pd_shading_type7_parse_patches_returns_empty_without_color_space() -> None:
    """Without /ColorSpace and /Function, the wrapper short-circuits."""
    shading = PDShadingType7()
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    decode_arr = COSArray()
    decode_arr.set_float_array([0, 255, 0, 255, 0, 255])
    shading.set_decode(decode_arr)
    assert shading.parse_patches(b"\x00\x01\x02") == []
