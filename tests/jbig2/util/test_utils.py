"""Hand-written tests for the JBIG2 numeric helpers.

Port of the working-range fast approximations in
``org.apache.pdfbox.jbig2.util.Utils`` (``clamp`` / ``floor`` / ``round`` /
``ceil``). All four are exact for ``|x| < 16384`` (the resize pipeline always
stays inside that range); the expected values below are computed from the same
``BIG_ENOUGH_INT`` integer arithmetic upstream uses, so the discrete sample
indices match the Java reference bit-for-bit.

Wave 1510 added the ``round_`` case (the only helper not reached by the resize
pipeline tests) plus the negative-input arms of ``floor`` / ``ceil``.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.util.utils import ceil, clamp, floor, round_


@pytest.mark.parametrize(
    ("value", "minimum", "maximum", "expected"),
    [
        (5.0, 0.0, 3.0, 3.0),  # above max -> clamped down
        (-1.0, 0.0, 3.0, 0.0),  # below min -> clamped up
        (2.0, 0.0, 3.0, 2.0),  # inside -> unchanged
    ],
)
def test_clamp(value: float, minimum: float, maximum: float, expected: float) -> None:
    assert clamp(value, minimum, maximum) == expected


@pytest.mark.parametrize(
    ("x", "expected"),
    [(2.9, 2), (2.0, 2), (0.0, 0), (-0.1, -1), (-2.9, -3), (100.999, 100)],
)
def test_floor(x: float, expected: int) -> None:
    assert floor(x) == expected


@pytest.mark.parametrize(
    ("x", "expected"),
    [(2.1, 3), (2.0, 2), (0.0, 0), (-0.1, 0), (-2.9, -2), (100.001, 101)],
)
def test_ceil(x: float, expected: int) -> None:
    assert ceil(x) == expected


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        (0.0, 0),
        (0.4, 0),
        (0.5, 1),  # upstream Utils.round is round-half-up
        (0.6, 1),
        (1.5, 2),
        (2.5, 3),
        (-0.4, 0),
        (-0.5, 0),  # half rounds toward positive infinity (Java semantics)
        (-0.6, -1),
        (3.49, 3),
        (3.51, 4),
        (100.5, 101),
    ],
)
def test_round_is_round_half_up(x: float, expected: int) -> None:
    assert round_(x) == expected
