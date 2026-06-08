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


def test_get_signed_content_tolerates_range_overrunning_file_end() -> None:
    # Wave 1517: oracle-corrected. Upstream getSignedContent feeds the whole
    # /ByteRange through COSFilterInputStream's monotonic cursor, which simply
    # stops at EOF when a range's length overruns the file — it does NOT raise.
    # [0,4,8,20] over a 12-byte file reads bytes [0,4) + [8,12) = "AAAABBBB".
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 20])

    assert sig.get_signed_content(b"AAAAxxxxBBBB") == b"AAAABBBB"


def test_verify_reports_malformed_byte_range_before_hashing() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 20])
    sig.set_contents(b"not-pkcs7")

    result = sig.verify(b"AAAAxxxxBBBB")

    assert result.is_valid is False
    assert result.computed_digest is None
    assert result.errors == ["could not extract signed data from document"]
