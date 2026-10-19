"""Port of upstream ``UnitVectorTest``.

The vectors steer every diagonal move, and a one-unit difference in F2Dot14
shifts points by 1/64 px, so the results are checked against the unit vectors
FreeType produces for the same deltas.
"""

from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.unit_vector import UnitVector

# {dx, dy, x, y}: the expected values are the unit vectors FreeType 2.13.2 computes for these
# deltas (its output, measured offline). Nearly axis-aligned vectors show the truncation to
# F2Dot14: (1000, -7) gives (16383, -114), not the rounded (16384, -115).
FREETYPE = [
    (3, 4, 9830, 13107),
    (1, 1, 11585, 11585),
    (-64, 128, -7327, 14654),
    (1000, -7, 16383, -114),
    (7, -1000, 114, -16383),
    (-5, -5, -11585, -11585),
    (30000, 1, 16384, 0),
    (1, 2, 7327, 14654),
]


def test_normalize_matches_free_type():
    for dx, dy, x, y in FREETYPE:
        v = UnitVector.normalize(dx, dy)
        assert v.get_x() == x, f"x of ({dx},{dy})"
        assert v.get_y() == y, f"y of ({dx},{dy})"


def test_normalize_axis_and_zero():
    assert UnitVector.normalize(5, 0).get_x() == Fixed.ONE_F2DOT14
    assert UnitVector.normalize(0, -5).get_y() == -Fixed.ONE_F2DOT14
    assert UnitVector.normalize(0, 0).get_x() == Fixed.ONE_F2DOT14
