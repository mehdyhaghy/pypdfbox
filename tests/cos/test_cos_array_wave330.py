from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSInteger


def test_wave330_pdfbox_index_methods_reject_negative_indexes() -> None:
    cos_array = COSArray([COSInteger.get(1), COSInteger.get(2)])

    with pytest.raises(IndexError):
        cos_array.get(-1)
    with pytest.raises(IndexError):
        cos_array.get_object(-1)
    with pytest.raises(IndexError):
        cos_array.set(-1, COSInteger.get(9))
    with pytest.raises(IndexError):
        cos_array.remove_at(-1)

    assert cos_array.to_list() == [COSInteger.get(1), COSInteger.get(2)]


def test_wave330_pdfbox_insert_rejects_indexes_outside_valid_range() -> None:
    cos_array = COSArray([COSInteger.get(1), COSInteger.get(2)])

    with pytest.raises(IndexError):
        cos_array.add_at(-1, COSInteger.get(0))
    with pytest.raises(IndexError):
        cos_array.add_at(3, COSInteger.get(3))

    cos_array.add_at(2, COSInteger.get(3))

    assert cos_array.to_list() == [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)]


def test_wave330_typed_accessors_reject_negative_indexes() -> None:
    cos_array = COSArray([COSInteger.get(1)])

    with pytest.raises(IndexError):
        cos_array.get_int(-1)
    with pytest.raises(IndexError):
        cos_array.set_int(-1, 2)

    assert cos_array.get_int(0) == 1
