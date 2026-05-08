from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature import compute_signed_digest


@pytest.mark.parametrize(
    "byte_range",
    [
        [-1, 4, 8, 4],
        [0, -4, 8, 4],
        [0, 4, -8, 4],
        [0, 4, 8, -4],
    ],
)
def test_compute_signed_digest_wave325_rejects_negative_byte_range_entries(
    byte_range: list[int],
) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        compute_signed_digest(b"x" * 16, byte_range)


@pytest.mark.parametrize(
    "byte_range",
    [
        [0, 17, 8, 4],
        [0, 4, 17, 0],
        [0, 4, 8, 9],
    ],
)
def test_compute_signed_digest_wave325_rejects_out_of_bounds_byte_range(
    byte_range: list[int],
) -> None:
    with pytest.raises(ValueError, match="out of bounds"):
        compute_signed_digest(b"x" * 16, byte_range)
