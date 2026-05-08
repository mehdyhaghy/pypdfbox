from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature

_BYTE_RANGE = COSName.get_pdf_name("ByteRange")


@pytest.mark.parametrize("byte_range", [[0, 4, 8], [0, 4, 8, 4, 12, 1]])
def test_get_signed_data_rejects_numeric_byte_range_with_wrong_length(
    byte_range: list[int],
) -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_BYTE_RANGE, COSArray.of_cos_integers(byte_range))

    assert sig.get_byte_range() == byte_range
    assert sig.get_signed_data(b"AAAAxxxxBBBBx") is None


def test_get_signed_content_raises_index_error_for_wrong_length_byte_range() -> None:
    sig = PDSignature()
    sig.get_cos_object().set_item(_BYTE_RANGE, COSArray.of_cos_integers([0, 4, 8]))

    with pytest.raises(IndexError, match="ByteRange"):
        sig.get_signed_content(b"AAAAxxxxBBBB")
