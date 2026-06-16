"""Fuzz / parity tests for simple-glyph decoding in ``GlyfSimpleDescript``.

Hammers the on-disk ``glyf`` simple-glyph record decode loop ported from
``org.apache.fontbox.ttf.GlyfSimpleDescript`` (the ``readFlags`` /
``readCoords`` / instruction-skip path). Each case synthesises the raw
``glyf`` bytes for one simple glyph and checks the decoded point
coordinates + on-curve flags against an independent reference decoder
derived directly from the OpenType ``glyf`` spec
(https://learn.microsoft.com/typography/opentype/spec/glyf).

Covered surface:

* flag REPEAT (0x08) run-length expansion (incl. repeat count 0 and the
  overrun error),
* X delta decoding for all four combinations of (X_SHORT 0x02,
  X_SAME_OR_POSITIVE 0x10): short+positive, short+negative,
  long signed-16 delta, same-as-previous (delta 0); same for Y,
* on-curve (0x01) vs off-curve points,
* multi-contour glyphs via ``endPtsOfContours``,
* the instructionLength + instruction-byte skip,
* a single-point contour,
* the contour count read,
* the empty glyph (0 contours) and the PDFBOX-2939 0xFFFF sentinel.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript

# OpenType simple-glyph flag bits (mirrors GlyfDescript constants).
ON_CURVE = 0x01
X_SHORT = 0x02
Y_SHORT = 0x04
REPEAT = 0x08
X_SAME_OR_POSITIVE = 0x10  # GlyfDescript.X_DUAL
Y_SAME_OR_POSITIVE = 0x20  # GlyfDescript.Y_DUAL


def _u16(v: int) -> bytes:
    return struct.pack(">H", v & 0xFFFF)


def _s16(v: int) -> bytes:
    return struct.pack(">h", v)


def _u8(v: int) -> bytes:
    return bytes([v & 0xFF])


def _to_signed_short(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _encode_flags(flags: list[int]) -> tuple[bytes, list[int]]:
    """Encode a per-point flag list using REPEAT runs where profitable.

    Returns ``(encoded_bytes, stored_flags)`` where ``stored_flags`` is the
    per-point flag value the decoder is expected to hold. Upstream copies
    the *whole* flag byte (REPEAT bit included) into every repeated slot, so
    a run head carrying REPEAT decodes to that same REPEAT-bearing byte on
    every point of the run.
    """
    out = bytearray()
    stored: list[int] = []
    i = 0
    n = len(flags)
    while i < n:
        f = flags[i] & ~REPEAT
        # count identical following flags
        run = 0
        while i + run + 1 < n and (flags[i + run + 1] & ~REPEAT) == f:
            run += 1
        if run > 0:
            head = f | REPEAT
            out += _u8(head)
            out += _u8(run)
            stored.extend([head] * (run + 1))
            i += run + 1
        else:
            out += _u8(f)
            stored.append(f)
            i += 1
    return bytes(out), stored


def _encode_x_coords(flags: list[int], xs: list[int]) -> bytes:
    """Encode absolute x coords as deltas per the active per-point flags."""
    out = bytearray()
    prev = 0
    for f, x in zip(flags, xs, strict=True):
        delta = x - prev
        if f & X_SHORT:
            # 1-byte magnitude; sign carried by X_SAME_OR_POSITIVE bit.
            mag = delta if (f & X_SAME_OR_POSITIVE) else -delta
            assert 0 <= mag <= 255, (delta, f)
            out += _u8(mag)
        elif not (f & X_SAME_OR_POSITIVE):
            out += _s16(_to_signed_short(delta))
        # else: same-as-previous, no bytes, delta must be 0
        prev = x
    return bytes(out)


def _encode_y_coords(flags: list[int], ys: list[int]) -> bytes:
    out = bytearray()
    prev = 0
    for f, y in zip(flags, ys, strict=True):
        delta = y - prev
        if f & Y_SHORT:
            mag = delta if (f & Y_SAME_OR_POSITIVE) else -delta
            assert 0 <= mag <= 255, (delta, f)
            out += _u8(mag)
        elif not (f & Y_SAME_OR_POSITIVE):
            out += _s16(_to_signed_short(delta))
        prev = y
    return bytes(out)


def _build_simple_glyph(
    end_pts: list[int],
    flags: list[int],
    xs: list[int],
    ys: list[int],
    instructions: bytes = b"",
) -> tuple[bytes, list[int]]:
    """Build the raw glyf body (without the leading numberOfContours/bbox).

    ``GlyfSimpleDescript.__init__`` expects the stream cursor positioned
    immediately after the bbox, i.e. at the ``endPtsOfContours`` array.
    """
    body = bytearray()
    for e in end_pts:
        body += _u16(e)
    body += _u16(len(instructions))
    body += instructions
    encoded_flags, stored = _encode_flags(flags)
    body += encoded_flags
    body += _encode_x_coords(flags, xs)
    body += _encode_y_coords(flags, ys)
    return bytes(body), stored


def _decode(end_pts, flags, xs, ys, instructions=b"", x0=0):
    body, _stored = _build_simple_glyph(end_pts, flags, xs, ys, instructions)
    stream = MemoryTTFDataStream(body)
    return GlyfSimpleDescript(len(end_pts), stream, x0)


def _decode_with_stored(end_pts, flags, xs, ys, instructions=b"", x0=0):
    """Like :func:`_decode` but also returns the expected stored-flag list."""
    body, stored = _build_simple_glyph(end_pts, flags, xs, ys, instructions)
    stream = MemoryTTFDataStream(body)
    return GlyfSimpleDescript(len(end_pts), stream, x0), stored


def _ref_absolute(xs: list[int], x0: int = 0) -> list[int]:
    """Reference: pypdfbox stores x0 + accumulated, wrapped to signed-16."""
    return [_to_signed_short(x0 + x) for x in xs]


# --------------------------------------------------------------------------
# Constant sanity: the source constants match the OpenType bit layout.
# --------------------------------------------------------------------------


def test_flag_constants_match_spec():
    assert GlyfDescript.ON_CURVE == ON_CURVE
    assert GlyfDescript.X_SHORT_VECTOR == X_SHORT
    assert GlyfDescript.Y_SHORT_VECTOR == Y_SHORT
    assert GlyfDescript.REPEAT == REPEAT
    assert GlyfDescript.X_DUAL == X_SAME_OR_POSITIVE
    assert GlyfDescript.Y_DUAL == Y_SAME_OR_POSITIVE


# --------------------------------------------------------------------------
# X delta — the four (X_SHORT, X_SAME_OR_POSITIVE) combinations.
# --------------------------------------------------------------------------


def test_x_short_positive():
    # X_SHORT + X_SAME_OR_POSITIVE => +unsigned byte
    flags = [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE] * 2
    xs = [10, 10 + 200]
    d = _decode([1], flags, xs, [0, 0])
    assert [d.get_x_coordinate(i) for i in range(2)] == xs


def test_x_short_negative():
    # X_SHORT, X_SAME_OR_POSITIVE clear => -unsigned byte
    flags = [ON_CURVE | X_SHORT] * 2
    xs = [-10, -10 - 200]
    d = _decode([1], flags, xs, [0, 0])
    assert [d.get_x_coordinate(i) for i in range(2)] == xs


def test_x_long_signed_delta():
    # neither X_SHORT nor X_SAME_OR_POSITIVE => signed 16-bit delta
    flags = [ON_CURVE, ON_CURVE, ON_CURVE]
    xs = [3000, 3000 - 5000, 3000 - 5000 + 12345]
    d = _decode([2], flags, xs, [0, 0, 0])
    assert [d.get_x_coordinate(i) for i in range(3)] == xs


def test_x_same_as_previous_zero_delta():
    # X_SAME_OR_POSITIVE set, X_SHORT clear => same as previous (delta 0)
    flags = [ON_CURVE, ON_CURVE | X_SAME_OR_POSITIVE, ON_CURVE | X_SAME_OR_POSITIVE]
    xs = [500, 500, 500]
    d = _decode([2], flags, xs, [0, 0, 0])
    assert [d.get_x_coordinate(i) for i in range(3)] == [500, 500, 500]


def test_x_mixed_all_four_modes():
    flags = [
        ON_CURVE,  # long delta
        ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE,  # short +
        ON_CURVE | X_SHORT,  # short -
        ON_CURVE | X_SAME_OR_POSITIVE,  # same
    ]
    xs = [1000, 1000 + 100, 1000 + 100 - 50, 1000 + 100 - 50]
    d = _decode([3], flags, xs, [0, 0, 0, 0])
    assert [d.get_x_coordinate(i) for i in range(4)] == xs


# --------------------------------------------------------------------------
# Y delta — symmetric to X.
# --------------------------------------------------------------------------


def test_y_short_positive():
    flags = [ON_CURVE | Y_SHORT | Y_SAME_OR_POSITIVE] * 2
    ys = [7, 7 + 255]
    d = _decode([1], flags, [0, 0], ys)
    assert [d.get_y_coordinate(i) for i in range(2)] == ys


def test_y_short_negative():
    flags = [ON_CURVE | Y_SHORT] * 2
    ys = [-7, -7 - 255]
    d = _decode([1], flags, [0, 0], ys)
    assert [d.get_y_coordinate(i) for i in range(2)] == ys


def test_y_long_signed_delta():
    flags = [ON_CURVE, ON_CURVE, ON_CURVE]
    ys = [-2000, -2000 + 9000, -2000 + 9000 - 30000]
    d = _decode([2], flags, [0, 0, 0], ys)
    assert [d.get_y_coordinate(i) for i in range(3)] == [_to_signed_short(v) for v in ys]


def test_y_same_as_previous_zero_delta():
    flags = [ON_CURVE, ON_CURVE | Y_SAME_OR_POSITIVE, ON_CURVE | Y_SAME_OR_POSITIVE]
    ys = [42, 42, 42]
    d = _decode([2], flags, [0, 0, 0], ys)
    assert [d.get_y_coordinate(i) for i in range(3)] == [42, 42, 42]


def test_y_mixed_all_four_modes():
    flags = [
        ON_CURVE,
        ON_CURVE | Y_SHORT | Y_SAME_OR_POSITIVE,
        ON_CURVE | Y_SHORT,
        ON_CURVE | Y_SAME_OR_POSITIVE,
    ]
    ys = [-300, -300 + 60, -300 + 60 - 90, -300 + 60 - 90]
    d = _decode([3], flags, [0, 0, 0, 0], ys)
    assert [d.get_y_coordinate(i) for i in range(4)] == ys


# --------------------------------------------------------------------------
# X and Y vary independently within the same glyph.
# --------------------------------------------------------------------------


def test_x_and_y_independent_modes():
    flags = [
        ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE | Y_SHORT,  # +x short, -y short
        ON_CURVE | Y_SAME_OR_POSITIVE,  # x long delta, y same
    ]
    xs = [50, 50 + 20]
    ys = [-30, -30]
    d = _decode([1], flags, xs, ys)
    assert [d.get_x_coordinate(i) for i in range(2)] == xs
    assert [d.get_y_coordinate(i) for i in range(2)] == ys


# --------------------------------------------------------------------------
# REPEAT flag expansion.
# --------------------------------------------------------------------------


def test_repeat_expands_flags():
    # 5 points all sharing one flag value => encoder emits REPEAT. Upstream
    # copies the whole REPEAT-bearing byte into every slot of the run.
    flags = [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE] * 5
    xs = [i * 3 for i in range(1, 6)]
    d, stored = _decode_with_stored([4], flags, xs, [0] * 5)
    assert d.get_point_count() == 5
    assert [d.get_flags(i) for i in range(5)] == stored
    # The REPEAT run head and its copies all carry the REPEAT bit.
    assert all((d.get_flags(i) & REPEAT) != 0 for i in range(5))
    # The semantic (non-REPEAT) bits round-trip exactly.
    assert all((d.get_flags(i) & ~REPEAT) == flags[i] for i in range(5))
    assert [d.get_x_coordinate(i) for i in range(5)] == xs


def test_repeat_partial_runs():
    # Two distinct runs back to back.
    flags = (
        [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE] * 3
        + [X_SHORT | X_SAME_OR_POSITIVE] * 3  # off-curve run
    )
    xs = [i * 5 for i in range(1, 7)]
    d, stored = _decode_with_stored([5], flags, xs, [0] * 6)
    assert [d.get_flags(i) for i in range(6)] == stored
    assert all((d.get_flags(i) & ~REPEAT) == flags[i] for i in range(6))
    assert [d.get_x_coordinate(i) for i in range(6)] == xs


def test_repeat_count_zero_is_noop():
    # A flag byte with REPEAT set but a repeat count of 0 covers exactly
    # one point (upstream loop `for i in 1..0` runs zero times).
    body = bytearray()
    body += _u16(0)  # endPts: single point
    body += _u16(0)  # instructionLength
    body += _u8((ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE) | REPEAT)
    body += _u8(0)  # repeat count 0
    body += _u8(11)  # x delta +11
    # y: needs a flag => same flag had no Y bits => long signed short delta
    body += _s16(0)
    d = GlyfSimpleDescript(1, MemoryTTFDataStream(bytes(body)), 0)
    assert d.get_point_count() == 1
    assert d.get_flags(0) == (ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE) | REPEAT
    assert d.get_x_coordinate(0) == 11


def test_repeat_overrun_raises():
    # REPEAT count exceeds remaining points => OSError (upstream IOException).
    body = bytearray()
    body += _u16(1)  # 2 points
    body += _u16(0)  # no instructions
    body += _u8(ON_CURVE | REPEAT)
    body += _u8(5)  # claim 5 repeats but only 1 more slot
    with pytest.raises(OSError):
        GlyfSimpleDescript(1, MemoryTTFDataStream(bytes(body)), 0)


# --------------------------------------------------------------------------
# On-curve vs off-curve bit.
# --------------------------------------------------------------------------


def test_on_curve_vs_off_curve_flags():
    flags = [
        ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE,  # on
        X_SHORT | X_SAME_OR_POSITIVE,  # off
        ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE,  # on
        X_SHORT | X_SAME_OR_POSITIVE,  # off
    ]
    xs = [10, 20, 30, 40]
    d = _decode([3], flags, xs, [0] * 4)
    on_curve = [(d.get_flags(i) & ON_CURVE) != 0 for i in range(4)]
    assert on_curve == [True, False, True, False]


# --------------------------------------------------------------------------
# Multi-contour glyph via endPtsOfContours.
# --------------------------------------------------------------------------


def test_multi_contour_end_points():
    end_pts = [2, 5, 6]  # 3 contours, 7 points total
    flags = [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE] * 7
    xs = [i for i in range(1, 8)]
    d = _decode(end_pts, flags, xs, [0] * 7)
    assert d.get_contour_count() == 3
    assert d.get_number_of_contours() == 3
    assert d.get_point_count() == 7
    assert [d.get_end_pt_of_contours(i) for i in range(3)] == end_pts
    assert [d.get_x_coordinate(i) for i in range(7)] == xs


def test_single_point_contour():
    flags = [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE | Y_SHORT | Y_SAME_OR_POSITIVE]
    d = _decode([0], flags, [9], [4])
    assert d.get_point_count() == 1
    assert d.get_contour_count() == 1
    assert d.get_end_pt_of_contours(0) == 0
    assert d.get_x_coordinate(0) == 9
    assert d.get_y_coordinate(0) == 4


# --------------------------------------------------------------------------
# Instruction-length skip.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("instr_len", [0, 1, 5, 40, 255], ids=[str(n) for n in [0, 1, 5, 40, 255]])
def test_instruction_skip(instr_len):
    instructions = bytes((i * 7) & 0xFF for i in range(instr_len))
    flags = [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE] * 2
    xs = [13, 13 + 22]
    d = _decode([1], flags, xs, [0, 0], instructions=instructions)
    # Coordinates must decode correctly regardless of instruction length.
    assert [d.get_x_coordinate(i) for i in range(2)] == xs
    # Instructions are read into the descript.
    assert d.get_instructions() == list(instructions)


# --------------------------------------------------------------------------
# Contour count read / empty glyph / sentinel.
# --------------------------------------------------------------------------


def test_zero_contours_empty_glyph():
    d = GlyfSimpleDescript(0, None, 0)
    assert d.get_contour_count() == 0
    assert d.get_point_count() == 0
    assert d.is_composite() is False


def test_zero_contours_with_stream_short_circuits():
    # number_of_contours == 0 returns early even if a stream is supplied.
    d = GlyfSimpleDescript(0, MemoryTTFDataStream(b"\x00\x00"), 0)
    assert d.get_point_count() == 0


def test_pdfbox_2939_empty_sentinel():
    # One contour ending at 0xFFFF => empty glyph, zero points.
    body = _u16(0xFFFF)
    d = GlyfSimpleDescript(1, MemoryTTFDataStream(body), 0)
    assert d.get_point_count() == 0
    assert d.get_contour_count() == 1


def test_is_composite_false():
    d = _decode([0], [ON_CURVE], [1], [1])
    assert d.is_composite() is False


# --------------------------------------------------------------------------
# x0 (left-side-bearing) start offset.
# --------------------------------------------------------------------------


def test_x0_start_offset_applied():
    flags = [ON_CURVE | X_SHORT | X_SAME_OR_POSITIVE] * 2
    xs = [5, 5 + 10]  # deltas relative to 0
    d = _decode([1], flags, xs, [0, 0], x0=100)
    # x0 shifts all x coordinates; y is unaffected.
    assert [d.get_x_coordinate(i) for i in range(2)] == [105, 115]


def test_x0_does_not_affect_y():
    flags = [ON_CURVE | Y_SHORT | Y_SAME_OR_POSITIVE] * 2
    ys = [3, 3 + 4]
    d = _decode([1], flags, [0, 0], ys, x0=999)
    assert [d.get_y_coordinate(i) for i in range(2)] == ys


# --------------------------------------------------------------------------
# Signed-16 wrap on accumulation (Java `short` semantics).
# --------------------------------------------------------------------------


def test_x_accumulator_wraps_signed_short():
    # Two long deltas of +20000 => 40000 wraps to -25536 as Java short.
    flags = [ON_CURVE, ON_CURVE]
    d = _decode([1], flags, [20000, 40000], [0, 0])
    assert d.get_x_coordinate(0) == 20000
    assert d.get_x_coordinate(1) == _to_signed_short(40000)
    assert d.get_x_coordinate(1) == -25536


def test_x_accumulator_wrap_congruent_across_points():
    # Modular arithmetic is associative: three +20000 deltas.
    flags = [ON_CURVE, ON_CURVE, ON_CURVE]
    xs = [20000, 40000, 60000]
    d = _decode([2], flags, xs, [0, 0, 0])
    assert [d.get_x_coordinate(i) for i in range(3)] == _ref_absolute(xs)


# --------------------------------------------------------------------------
# Randomised differential against the reference decoder.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", list(range(12)), ids=[f"seed{n}" for n in range(12)])
def test_random_glyph_matches_reference(seed):
    import random

    rng = random.Random(seed)
    n_contours = rng.randint(1, 4)
    n_points = rng.randint(n_contours, n_contours + 8)
    # Build strictly increasing contour end points covering all points.
    cuts = sorted(rng.sample(range(n_points - 1), n_contours - 1)) if n_contours > 1 else []
    end_pts = [*cuts, n_points - 1]

    flags = []
    xs = []
    ys = []
    cur_x = 0
    cur_y = 0
    for _ in range(n_points):
        f = 0
        if rng.random() < 0.5:
            f |= ON_CURVE
        # choose an x mode that we can faithfully encode
        mode = rng.choice(["short+", "short-", "long", "same"])
        if mode == "short+":
            f |= X_SHORT | X_SAME_OR_POSITIVE
            cur_x += rng.randint(0, 255)
        elif mode == "short-":
            f |= X_SHORT
            cur_x -= rng.randint(0, 255)
        elif mode == "long":
            cur_x += rng.randint(-2000, 2000)
        else:  # same
            f |= X_SAME_OR_POSITIVE
        ymode = rng.choice(["short+", "short-", "long", "same"])
        if ymode == "short+":
            f |= Y_SHORT | Y_SAME_OR_POSITIVE
            cur_y += rng.randint(0, 255)
        elif ymode == "short-":
            f |= Y_SHORT
            cur_y -= rng.randint(0, 255)
        elif ymode == "long":
            cur_y += rng.randint(-2000, 2000)
        else:
            f |= Y_SAME_OR_POSITIVE
        flags.append(f)
        xs.append(cur_x)
        ys.append(cur_y)

    instr = bytes(rng.randint(0, 255) for _ in range(rng.randint(0, 12)))
    d, stored = _decode_with_stored(end_pts, flags, xs, ys, instructions=instr)

    assert d.get_point_count() == n_points
    assert [d.get_end_pt_of_contours(i) for i in range(n_contours)] == end_pts
    assert [d.get_x_coordinate(i) for i in range(n_points)] == _ref_absolute(xs)
    assert [d.get_y_coordinate(i) for i in range(n_points)] == _ref_absolute(ys)
    # Stored flags carry the REPEAT bit on run members; the semantic bits
    # (everything but REPEAT) must equal the source flags.
    assert [d.get_flags(i) for i in range(n_points)] == stored
    assert [d.get_flags(i) & ~REPEAT for i in range(n_points)] == flags
    assert d.get_instructions() == list(instr)
