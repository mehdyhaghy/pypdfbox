"""Hand-written tests for ``UnitVector``: the exact isqrt normalization and Java truncation."""

import math

import pytest

from pypdfbox.fontbox.ttf.unit_vector import UnitVector


def _upstream_component(d, length_squared):
    """Upstream's float-estimate-then-correct loop, transcribed."""
    numerator = (2 * abs(d) * 0x10000) ** 2
    r = math.floor(abs(d) * 0x10000 / math.sqrt(length_squared) + 0.5)
    while r > 0 and (2 * r - 1) ** 2 * length_squared > numerator:
        r -= 1
    while (2 * r + 1) ** 2 * length_squared <= numerator:
        r += 1
    return -r if d < 0 else r


def _upstream_normalize(dx, dy):
    ls = dx * dx + dy * dy

    def trunc4(v):
        return v // 4 if v >= 0 else -((-v) // 4)  # Java int division

    return trunc4(_upstream_component(dx, ls)), trunc4(_upstream_component(dy, ls))


@pytest.mark.parametrize(
    ("dx", "dy"),
    [
        (3, 4),
        (-3, 4),
        (1, -1),
        (-7, -7),
        (32767, -32768),
        (-32768, 1),
        (100000, 3),
        (2**31 - 1, -(2**31)),
        (5, 12),
        (-1, 1000),
    ],
)
def test_normalize_matches_upstream_algorithm(dx, dy):
    v = UnitVector.normalize(dx, dy)
    assert (v.get_x(), v.get_y()) == _upstream_normalize(dx, dy)


def test_normalize_exhaustive_small_deltas():
    for dx in range(-40, 41):
        for dy in range(-40, 41):
            if dx == 0 or dy == 0:
                continue
            v = UnitVector.normalize(dx, dy)
            assert (v.get_x(), v.get_y()) == _upstream_normalize(dx, dy), (dx, dy)


def test_perpendicular_copy_equality_and_hash():
    v = UnitVector(3, 4)
    p = v.perpendicular()
    assert (p.get_x(), p.get_y()) == (-4, 3)
    c = v.copy()
    assert c == v
    assert c is not v
    assert hash(c) == 31 * 3 + 4
    assert v != "UnitVector(3, 4)"
    assert str(v) == "UnitVector(3, 4)"
    c.set(1, 2)
    assert v.get_x() == 3
