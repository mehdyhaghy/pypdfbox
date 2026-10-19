"""Port of upstream ``FixedTest``: the fixed-point math used by the interpreter."""

from pypdfbox.fontbox.ttf.fixed import Fixed


def test_int_round_trip():
    for n in range(-1000, 1001):
        assert Fixed.to_int(Fixed.from_int(n)) == n, f"round-trip {n}"
    assert Fixed.from_int(1) == 64
    assert Fixed.from_int(-2) == -128


def test_floor_ceil_round():
    assert Fixed.floor(100) == 64  # 1.5625px -> 1px
    assert Fixed.ceil(100) == 128  # -> 2px
    assert Fixed.round(70) == 64  # just above 1px rounds to 1px
    assert Fixed.round(96) == 128  # 1.5px rounds up to 2px
    assert Fixed.round(31) == 0  # just below half a pixel rounds to 0
    assert Fixed.round(32) == 64  # exactly half rounds up


def test_floor_ceil_negative():
    # & ~63 rounds towards negative infinity in two's complement, so (v + 63) & ~63 is a true
    # ceiling for every sign, exactly FreeType's FT_PIX_CEIL_LONG (used by the CEILING opcode)
    assert Fixed.ceil(-1) == 0
    assert Fixed.ceil(-63) == 0
    assert Fixed.ceil(-64) == -64
    assert Fixed.ceil(-65) == -64
    assert Fixed.ceil(-127) == -64
    assert Fixed.ceil(-128) == -128
    assert Fixed.floor(-1) == -64
    assert Fixed.floor(-64) == -64
    assert Fixed.floor(-65) == -128


def test_mul_div():
    # 2.0 * 3.0 == 6.0
    assert Fixed.mul(Fixed.from_int(2), Fixed.from_int(3)) == Fixed.from_int(6)
    # 6.0 / 2.0 == 3.0
    assert Fixed.div(Fixed.from_int(6), Fixed.from_int(2)) == Fixed.from_int(3)
    # division by zero is defined as zero
    assert Fixed.div(Fixed.from_int(5), 0) == 0
    # signed rounding
    assert Fixed.mul(Fixed.from_int(-2), Fixed.from_int(3)) == -Fixed.from_int(6)


def test_mul14():
    # multiplying by the F2Dot14 unit (1.0) is the identity
    assert Fixed.mul14(Fixed.from_int(5), Fixed.ONE_F2DOT14) == Fixed.from_int(5)
    # multiplying by 0.5 in F2Dot14 halves the value
    assert Fixed.mul14(Fixed.from_int(5), Fixed.ONE_F2DOT14 // 2) == Fixed.from_int(5) // 2


def test_scale():
    # 1000 font units at 16 ppem with unitsPerEm 2048 == 500 subpixel units == 7.8125px
    assert Fixed.scale(1000, 16, 2048) == 500
    # a flat *64 would be wrong: it must depend on unitsPerEm
    assert Fixed.scale(2048, 16, 2048) == Fixed.from_int(16)  # one em == ppem pixels
    assert Fixed.scale(1234, 16, 0) == 0  # guard against zero unitsPerEm
