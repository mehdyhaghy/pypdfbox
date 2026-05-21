"""Hand-written tests for ``PDShadingType6.parse_patches``.

Cover the geometry-only Coons patch-stream decoder added in wave 1374:
synthetic 1-patch and 2-patch streams (BitsPerCoordinate=8,
BitsPerComponent=8, BitsPerFlag=2, identity ``/Decode``) round-trip
through the bit reader and produce the expected control points + corner
colours. Also covers shared-edge flag handling (flag=1/2/3 carries the
previous patch's edge into the next).
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
from pypdfbox.pdmodel.graphics.shading.pd_shading_type6 import PDShadingType6


def _set_device_gray_color_space(shading: PDShadingType6) -> None:
    """Attach a 1-component ``/DeviceGray`` colour space so
    ``get_number_of_color_components()`` returns 1 (the wrapper bails on
    ``ncc <= 0`` when neither ``/ColorSpace`` nor ``/Function`` is set)."""
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
    """Encode a synthetic Type 6/7 patch stream: each item is
    ``(flag, coords, colors)`` where ``coords`` and ``colors`` are
    integer-encoded values (raw bits, pre-interpolation)."""
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
# Single free Coons patch
# ----------------------------------------------------------------------


def test_parse_patches_single_free_patch_decodes_12_points_and_4_colors() -> None:
    coords = [(i, 100 + i) for i in range(12)]
    colors = [[50], [100], [150], [200]]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=12,
    )

    assert len(patches) == 1
    patch = patches[0]
    assert isinstance(patch, ParsedPatch)
    assert patch.flag == 0
    assert len(patch.points) == 12
    assert len(patch.colors) == 4
    for i in range(12):
        assert _close(patch.points[i][0], float(i))
        assert _close(patch.points[i][1], 100.0 + float(i))
    assert [c[0] for c in patch.colors] == [50.0, 100.0, 150.0, 200.0]


def test_parse_patches_identity_decode_yields_raw_int_values() -> None:
    coords = [(0, 0)] + [(255, 255)] * 11
    colors = [[0], [0], [0], [255]]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=12,
    )

    assert len(patches) == 1
    assert _close(patches[0].points[0][0], 0.0)
    assert _close(patches[0].points[1][0], 255.0)
    assert _close(patches[0].colors[3][0], 255.0)


# ----------------------------------------------------------------------
# Two patches, second with shared edge (flag != 0)
# ----------------------------------------------------------------------


def test_parse_patches_flag2_shares_trailing_edge_with_previous_patch() -> None:
    coords1 = [(i * 10, 20 + i * 5) for i in range(12)]
    colors1 = [[10], [20], [30], [40]]
    # Second patch (flag=2) declares only 8 coords + 2 colors; the leading
    # 4 control points and 2 corner colours are inherited from patch 0's
    # trailing edge per spec (pts[6..9] / colors[2..3]).
    coords2 = [(200 + i, 100 + i * 2) for i in range(8)]
    colors2 = [[50], [60]]
    data = _build_patch_stream([(0, coords1, colors1), (2, coords2, colors2)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=12,
    )

    assert len(patches) == 2
    assert patches[0].flag == 0
    assert patches[1].flag == 2
    # First 4 control points of patch 1 == pts[6..9] of patch 0
    assert patches[1].points[:4] == patches[0].points[6:10]
    # First 2 corner colours of patch 1 == colours[2..3] of patch 0
    assert patches[1].colors[:2] == patches[0].colors[2:4]
    # Remaining 8 control points decoded fresh from the stream
    for i in range(8):
        assert _close(patches[1].points[4 + i][0], 200.0 + float(i))
        assert _close(patches[1].points[4 + i][1], 100.0 + float(i * 2))


@pytest.mark.parametrize(
    ("flag", "expected_edge_indices", "expected_color_indices"),
    [
        (1, [3, 4, 5, 6], [1, 2]),
        (2, [6, 7, 8, 9], [2, 3]),
        (3, [9, 10, 11, 0], [3, 0]),
    ],
    ids=["flag1", "flag2", "flag3"],
)
def test_parse_patches_all_shared_edge_flags_inherit_correct_edge(
    flag: int,
    expected_edge_indices: list[int],
    expected_color_indices: list[int],
) -> None:
    coords1 = [(i * 7, 50 + i * 3) for i in range(12)]
    colors1 = [[5], [25], [45], [65]]
    coords2 = [(120 + i, 30 + i * 4) for i in range(8)]
    colors2 = [[80], [90]]
    data = _build_patch_stream([(0, coords1, colors1), (flag, coords2, colors2)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=12,
    )

    assert len(patches) == 2
    assert patches[1].flag == flag
    for slot, src in enumerate(expected_edge_indices):
        assert patches[1].points[slot] == patches[0].points[src]
    for slot, src in enumerate(expected_color_indices):
        assert patches[1].colors[slot] == patches[0].colors[src]


# ----------------------------------------------------------------------
# /Decode interpolation: non-identity range maps src into dst
# ----------------------------------------------------------------------


def test_parse_patches_decode_array_remaps_raw_values_to_user_range() -> None:
    coords = [(0, 0)] * 11 + [(255, 255)]
    colors = [[0], [128], [255], [64]]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        # x in [10, 110], y in [-50, 50], colour in [0, 1]
        decode=[10, 110, -50, 50, 0, 1],
        num_color_components=1,
        control_points=12,
    )

    assert len(patches) == 1
    # Raw (0, 0) maps to the decode minimum.
    assert _close(patches[0].points[0][0], 10.0)
    assert _close(patches[0].points[0][1], -50.0)
    # Raw (255, 255) maps to the decode maximum.
    assert _close(patches[0].points[11][0], 110.0)
    assert _close(patches[0].points[11][1], 50.0)
    # Colours scaled into [0, 1].
    assert _close(patches[0].colors[0][0], 0.0)
    assert _close(patches[0].colors[1][0], 128.0 / 255.0)
    assert _close(patches[0].colors[2][0], 1.0)
    assert _close(patches[0].colors[3][0], 64.0 / 255.0)


# ----------------------------------------------------------------------
# Multi-component colours
# ----------------------------------------------------------------------


def test_parse_patches_handles_rgb_3_component_colors() -> None:
    coords = [(i * 4, i * 4) for i in range(12)]
    colors = [
        [255, 0, 0],
        [0, 255, 0],
        [0, 0, 255],
        [255, 255, 255],
    ]
    data = _build_patch_stream([(0, coords, colors)])

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        num_color_components=3,
        control_points=12,
    )

    assert len(patches) == 1
    assert patches[0].colors[0] == pytest.approx([1.0, 0.0, 0.0])
    assert patches[0].colors[1] == pytest.approx([0.0, 1.0, 0.0])
    assert patches[0].colors[2] == pytest.approx([0.0, 0.0, 1.0])
    assert patches[0].colors[3] == pytest.approx([1.0, 1.0, 1.0])


# ----------------------------------------------------------------------
# Defensive paths: empty stream, missing decode, short body
# ----------------------------------------------------------------------


def test_parse_patches_empty_stream_returns_empty_list() -> None:
    patches = parse_patch_stream(
        b"",
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=12,
    )
    assert patches == []


def test_parse_patches_truncated_stream_returns_only_complete_patches() -> None:
    coords1 = [(i, i) for i in range(12)]
    colors1 = [[10], [20], [30], [40]]
    data = _build_patch_stream([(0, coords1, colors1)])
    # Append a partial second patch (flag=0, only 4 coordinates, no colours).
    coords2 = [(100, 100)] * 4
    data += _build_patch_stream([(0, coords2, [])])[:6]

    patches = parse_patch_stream(
        data,
        bits_per_coordinate=8,
        bits_per_component=8,
        bits_per_flag=2,
        decode=[0, 255, 0, 255, 0, 255],
        num_color_components=1,
        control_points=12,
    )

    # Only the first complete patch is returned; the truncated tail is dropped.
    assert len(patches) == 1
    assert patches[0].flag == 0


def test_parse_patches_rejects_short_decode_array() -> None:
    with pytest.raises(ValueError, match="/Decode requires"):
        parse_patch_stream(
            b"\x00",
            bits_per_coordinate=8,
            bits_per_component=8,
            bits_per_flag=2,
            decode=[0, 255, 0, 255],
            num_color_components=1,
            control_points=12,
        )


def test_parse_patches_rejects_bad_control_points() -> None:
    with pytest.raises(ValueError, match="control_points must be"):
        parse_patch_stream(
            b"\x00",
            bits_per_coordinate=8,
            bits_per_component=8,
            bits_per_flag=2,
            decode=[0, 255, 0, 255, 0, 255],
            num_color_components=1,
            control_points=8,
        )


# ----------------------------------------------------------------------
# Class-level wrapper: PDShadingType6.parse_patches reads from /Decode +
# the backing COSStream when ``stream_bytes`` is omitted.
# ----------------------------------------------------------------------


def test_pd_shading_type6_parse_patches_uses_dictionary_metadata() -> None:
    coords = [(i, 200 - i * 10) for i in range(12)]
    colors = [[0], [85], [170], [255]]
    stream_body = _build_patch_stream([(0, coords, colors)])

    shading = PDShadingType6()
    _set_device_gray_color_space(shading)
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    decode_arr = COSArray()
    decode_arr.set_float_array([0, 255, 0, 255, 0, 255])
    shading.set_decode(decode_arr)

    # PDShadingType6() backs onto a COSStream; write the body directly.
    stream = shading.get_cos_object()
    assert isinstance(stream, COSStream)
    with stream.create_output_stream() as sink:
        sink.write(stream_body)

    patches = shading.parse_patches()
    assert len(patches) == 1
    assert patches[0].flag == 0
    assert len(patches[0].points) == 12
    assert _close(patches[0].points[0][0], 0.0)
    assert _close(patches[0].points[11][1], 200.0 - 110.0)
    assert [c[0] for c in patches[0].colors] == pytest.approx([0.0, 85.0, 170.0, 255.0])


def test_pd_shading_type6_parse_patches_accepts_explicit_bytes() -> None:
    coords = [(i, i) for i in range(12)]
    colors = [[1], [2], [3], [4]]
    stream_body = _build_patch_stream([(0, coords, colors)])

    shading = PDShadingType6()
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


def test_pd_shading_type6_parse_patches_returns_empty_without_decode() -> None:
    shading = PDShadingType6()
    _set_device_gray_color_space(shading)
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    # No /Decode set — should bail before parsing.
    assert shading.parse_patches(b"\xff\xff") == []


def test_pd_shading_type6_parse_patches_returns_empty_without_color_space() -> None:
    """Without /ColorSpace and without /Function, the number of colour
    components is -1 — the wrapper short-circuits to an empty list rather
    than letting the bit reader walk a stream it can't interpret."""
    shading = PDShadingType6()
    shading.set_bits_per_coordinate(8)
    shading.set_bits_per_component(8)
    shading.set_bits_per_flag(2)
    decode_arr = COSArray()
    decode_arr.set_float_array([0, 255, 0, 255, 0, 255])
    shading.set_decode(decode_arr)
    assert shading.parse_patches(b"\x00\x01\x02") == []
