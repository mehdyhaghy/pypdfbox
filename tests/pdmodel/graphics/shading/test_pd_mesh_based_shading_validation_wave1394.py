"""Wave 1394 — argument-validation branches in
``pypdfbox.pdmodel.graphics.shading.pd_mesh_based_shading_type``.

Covers:

* ``_PatchBitReader.read_bits`` zero-bit fast-path (line 66).
* ``_interpolate`` zero-range branch (line 89).
* ``_patch_flag_color`` invalid-flag raise (line 136).
* ``parse_patch_stream`` argument-validation raises (lines 170, 172,
  174, 176).
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.shading.pd_mesh_based_shading_type import (
    _interpolate,
    _patch_flag_color,
    _PatchBitReader,
    parse_patch_stream,
)

# ---------- _PatchBitReader.read_bits ----------


def test_patch_bit_reader_read_zero_bits_returns_zero() -> None:
    """Zero-bit read is a fast-path (line 66) — must not consume any bytes."""
    reader = _PatchBitReader(b"\xff\xff")
    assert reader.read_bits(0) == 0
    # Cursor hasn't moved — a subsequent 8-bit read still sees the full byte.
    assert reader.read_bits(8) == 0xFF


def test_patch_bit_reader_read_negative_bits_returns_zero() -> None:
    """Negative n is degenerate but harmless (line 65-66)."""
    reader = _PatchBitReader(b"\xab")
    assert reader.read_bits(-3) == 0


# ---------- _interpolate ----------


def test_interpolate_zero_range_returns_dst_min() -> None:
    """``src_max == 0`` (degenerate bits-per-coord = 0) → ``dst_min`` (line 89)."""
    assert _interpolate(src=0, src_max=0, dst_min=2.0, dst_max=8.0) == 2.0
    # src is ignored when src_max == 0.
    assert _interpolate(src=99, src_max=0, dst_min=-1.5, dst_max=5.0) == -1.5


def test_interpolate_non_zero_range_does_linear_map() -> None:
    """Sanity guard so the previous test isn't a tautology."""
    assert _interpolate(src=5, src_max=10, dst_min=0.0, dst_max=100.0) == 50.0


# ---------- _patch_flag_color ----------


def test_patch_flag_color_raises_for_invalid_flag() -> None:
    """Flags 1, 2, 3 are legal; everything else raises (line 136)."""
    color = [[1.0], [2.0], [3.0], [4.0]]
    with pytest.raises(ValueError, match="invalid flag"):
        _patch_flag_color(color, flag=0)
    with pytest.raises(ValueError, match="invalid flag"):
        _patch_flag_color(color, flag=4)
    with pytest.raises(ValueError, match="invalid flag"):
        _patch_flag_color(color, flag=-1)


# ---------- parse_patch_stream argument validation ----------


_OK_DECODE_RGB = [0.0, 1000.0, 0.0, 1000.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


def test_parse_patch_stream_raises_when_bits_per_coordinate_zero() -> None:
    """Line 170 — ``bits_per_coordinate <= 0``."""
    with pytest.raises(ValueError, match="bits_per_coordinate"):
        parse_patch_stream(
            b"\x00",
            bits_per_coordinate=0,
            bits_per_component=8,
            bits_per_flag=8,
            decode=_OK_DECODE_RGB,
            num_color_components=3,
            control_points=12,
        )


def test_parse_patch_stream_raises_when_bits_per_component_zero() -> None:
    """Line 172 — ``bits_per_component <= 0``."""
    with pytest.raises(ValueError, match="bits_per_component"):
        parse_patch_stream(
            b"\x00",
            bits_per_coordinate=16,
            bits_per_component=0,
            bits_per_flag=8,
            decode=_OK_DECODE_RGB,
            num_color_components=3,
            control_points=12,
        )


def test_parse_patch_stream_raises_when_bits_per_flag_zero() -> None:
    """Line 174 — ``bits_per_flag <= 0``."""
    with pytest.raises(ValueError, match="bits_per_flag"):
        parse_patch_stream(
            b"\x00",
            bits_per_coordinate=16,
            bits_per_component=8,
            bits_per_flag=0,
            decode=_OK_DECODE_RGB,
            num_color_components=3,
            control_points=12,
        )


def test_parse_patch_stream_raises_when_num_color_components_zero() -> None:
    """Line 176 — ``num_color_components <= 0``."""
    with pytest.raises(ValueError, match="num_color_components"):
        parse_patch_stream(
            b"\x00",
            bits_per_coordinate=16,
            bits_per_component=8,
            bits_per_flag=8,
            decode=[0.0, 1.0, 0.0, 1.0],
            num_color_components=0,
            control_points=12,
        )
