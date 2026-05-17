"""Coverage round-out for
:class:`pypdfbox.fontbox.ttf.glyf_simple_descript.GlyfSimpleDescript`
(wave 1343).

Covers the four short-vector / dual-flag combinations of
``read_coords``, the successful REPEAT-flag advancement in
``read_flags``, the n==0 fast-path of ``from_glyph``, and the
positive-value branch of ``_to_signed_short``.
"""

from __future__ import annotations

from types import SimpleNamespace

from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import (
    GlyfSimpleDescript,
    _to_signed_short,
)
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def test_read_coords_x_dual_short_vector_uses_unsigned_byte_positive() -> None:
    """flag = X_DUAL | X_SHORT_VECTOR | ON_CURVE — x += unsigned byte."""
    # Single contour, 1 point, instruction count = 0.
    # X_DUAL (0x10) | X_SHORT_VECTOR (0x02) | ON_CURVE (0x01) = 0x13.
    # For y, Y_DUAL set without Y_SHORT_VECTOR → "no change", no read.
    flag = (
        GlyfDescript.X_DUAL
        | GlyfDescript.X_SHORT_VECTOR
        | GlyfDescript.Y_DUAL
        | GlyfDescript.ON_CURVE
    )
    payload = bytes(
        [
            0x00, 0x00,        # endPtsOfContours[0] = 0 -> 1 point
            0x00, 0x00,        # instruction length
            flag,              # flag for point 0
            0x05,              # x delta (unsigned byte, +5)
            # no y bytes (Y_DUAL set, Y_SHORT_VECTOR clear -> 0 delta)
        ]
    )
    stream = MemoryTTFDataStream(payload)
    d = GlyfSimpleDescript(1, stream, x0=100)
    # x starts at x0=100, +5 = 105
    assert d.get_x_coordinate(0) == 105
    # y starts at 0, "no change" path keeps y at 0
    assert d.get_y_coordinate(0) == 0


def test_read_coords_x_short_vector_without_dual_subtracts_unsigned_byte() -> None:
    """flag = X_SHORT_VECTOR only (no X_DUAL) — x -= unsigned byte."""
    # X_SHORT_VECTOR (0x02) | ON_CURVE (0x01) = 0x03. No DUAL bits.
    # For y, need to read a signed short (no dual, no short).
    flag = GlyfDescript.X_SHORT_VECTOR | GlyfDescript.ON_CURVE
    payload = bytes(
        [
            0x00, 0x00,        # endPtsOfContours[0] = 0 -> 1 point
            0x00, 0x00,        # instruction length
            flag,              # flag for point 0
            0x07,              # x delta unsigned byte (subtracted)
            0x00, 0x00,        # y delta signed short (0)
        ]
    )
    stream = MemoryTTFDataStream(payload)
    d = GlyfSimpleDescript(1, stream, x0=50)
    # x starts at x0=50, -7 = 43
    assert d.get_x_coordinate(0) == 43


def test_read_coords_y_dual_short_vector_uses_unsigned_byte_positive() -> None:
    """flag = Y_DUAL | Y_SHORT_VECTOR — y += unsigned byte."""
    flag = (
        GlyfDescript.X_DUAL
        | GlyfDescript.Y_DUAL
        | GlyfDescript.Y_SHORT_VECTOR
        | GlyfDescript.ON_CURVE
    )
    payload = bytes(
        [
            0x00, 0x00,
            0x00, 0x00,
            flag,
            # X_DUAL set without X_SHORT_VECTOR -> no x byte (delta 0)
            0x0B,  # y delta unsigned byte (+11)
        ]
    )
    stream = MemoryTTFDataStream(payload)
    d = GlyfSimpleDescript(1, stream, x0=0)
    # x = 0 (no change), y = 0 + 11 = 11
    assert d.get_x_coordinate(0) == 0
    assert d.get_y_coordinate(0) == 11


def test_read_coords_y_short_vector_without_dual_subtracts_unsigned_byte() -> None:
    """flag = Y_SHORT_VECTOR only (no Y_DUAL) — y -= unsigned byte."""
    flag = (
        GlyfDescript.X_DUAL
        | GlyfDescript.Y_SHORT_VECTOR
        | GlyfDescript.ON_CURVE
    )
    payload = bytes(
        [
            0x00, 0x00,
            0x00, 0x00,
            flag,
            # X_DUAL only -> no x byte
            0x09,  # y delta unsigned byte (-9)
        ]
    )
    stream = MemoryTTFDataStream(payload)
    d = GlyfSimpleDescript(1, stream, x0=0)
    assert d.get_y_coordinate(0) == -9


def test_read_flags_repeat_advances_index() -> None:
    """A REPEAT flag with a valid count should advance ``index`` past
    the repeated slots (line 166: ``index += repeats``)."""
    # Two-point contour: flag byte sets REPEAT, repeat count = 1, so we
    # fill slots [0] and [1] with the same flag.
    # We pick a flag that requires no coordinate bytes (X_DUAL | Y_DUAL).
    base_flag = GlyfDescript.REPEAT | GlyfDescript.X_DUAL | GlyfDescript.Y_DUAL
    payload = bytes(
        [
            0x00, 0x01,        # endPtsOfContours[0] = 1 -> 2 points
            0x00, 0x00,        # instruction length
            base_flag,         # first flag (with REPEAT)
            0x01,              # repeat count = 1 (fills slot 1)
            # No coordinate bytes needed: X_DUAL/Y_DUAL set, X_SHORT/Y_SHORT clear.
        ]
    )
    stream = MemoryTTFDataStream(payload)
    d = GlyfSimpleDescript(1, stream, x0=0)
    assert d.get_point_count() == 2
    assert d.get_flags(0) == base_flag
    assert d.get_flags(1) == base_flag
    # Both x and y unchanged (DUAL without SHORT_VECTOR = "no change").
    assert d.get_x_coordinate(0) == 0
    assert d.get_x_coordinate(1) == 0
    assert d.get_y_coordinate(0) == 0
    assert d.get_y_coordinate(1) == 0


def test_from_glyph_with_zero_contours_short_circuits() -> None:
    """``from_glyph`` returns immediately when ``numberOfContours == 0``
    without invoking ``getCoordinates`` (line 188)."""

    class _RaisingGlyph:
        numberOfContours = 0  # noqa: N815  fontTools attribute name

        def getCoordinates(self, _table):  # noqa: N802  fontTools API name
            raise AssertionError("getCoordinates must not be called for n==0")

    d = GlyfSimpleDescript.from_glyph(_RaisingGlyph(), glyf_table=None)
    assert d.is_composite() is False
    assert d.get_point_count() == 0
    assert d.get_contour_count() == 0


def test_to_signed_short_positive_value_returned_as_is() -> None:
    # 0x7FFF is the largest signed-short positive; ``_to_signed_short`` should
    # return it unchanged (line 211 branch where the sign bit is clear).
    assert _to_signed_short(0x7FFF) == 0x7FFF
    assert _to_signed_short(0) == 0
    assert _to_signed_short(1) == 1
    # Sanity check: high-bit-set values still take the negative branch.
    assert _to_signed_short(0x8000) == -0x8000
    assert _to_signed_short(0xFFFF) == -1


def test_from_glyph_with_program_bytecode_captures_instructions() -> None:
    # Cover the program/bytecode branch with a tiny stub glyph that mimics
    # the fontTools shape used in ``from_glyph``.
    glyph = SimpleNamespace(
        numberOfContours=1,
        program=SimpleNamespace(bytecode=b"\x4b\x00\x0e"),
        getCoordinates=lambda _t: (
            [(0, 0), (10, 10), (20, 0)],
            [2],
            [GlyfDescript.ON_CURVE] * 3,
        ),
    )
    d = GlyfSimpleDescript.from_glyph(glyph, glyf_table=None)
    assert d.get_instructions() == [0x4B, 0x00, 0x0E]
