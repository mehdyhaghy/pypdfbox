from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature


@pytest.mark.parametrize(
    "byte_range",
    [
        [-1, 4, 8, 4],
        [0, -4, 8, 4],
        [0, 4, -8, 4],
        [0, 4, 8, -4],
        [0, 20, 8, 4],
        [0, 4, 8, 20],
        [20, 0, 8, 4],
    ],
)
def test_get_signed_data_rejects_malformed_byte_ranges(
    byte_range: list[int],
) -> None:
    sig = PDSignature()
    sig.set_byte_range(byte_range)

    assert sig.get_signed_data(b"AAAAxxxxBBBB") is None


def test_get_signed_content_raises_for_malformed_byte_range() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 20])

    with pytest.raises(IndexError, match="ByteRange"):
        sig.get_signed_content(b"AAAAxxxxBBBB")


def test_verify_reports_malformed_byte_range_before_hashing() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 20])
    sig.set_contents(b"not-pkcs7")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.computed_digest is None
    assert result.errors == ["could not extract signed data from document"]
