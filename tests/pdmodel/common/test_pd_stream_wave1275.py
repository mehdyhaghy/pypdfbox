"""Wave 1275 — PDStream.internal_get_decode_params public helper."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")
_DP = COSName.get_pdf_name("DP")
_F_DECODE_PARMS = COSName.get_pdf_name("FDecodeParms")


def test_returns_none_when_entry_absent() -> None:
    pds = PDStream(COSStream())
    assert pds.internal_get_decode_params(_DECODE_PARMS, _DP) is None


def test_dict_value_wraps_in_single_element_list() -> None:
    cos = COSStream()
    parms = COSDictionary()
    parms.set_int("Predictor", 12)
    cos.set_item(_DECODE_PARMS, parms)
    pds = PDStream(cos)

    result = pds.internal_get_decode_params(_DECODE_PARMS, _DP)
    assert result == [parms]


def test_array_value_returns_each_dictionary() -> None:
    cos = COSStream()
    arr = COSArray()
    a = COSDictionary()
    a.set_int("Predictor", 12)
    b = COSDictionary()
    b.set_int("Predictor", 15)
    arr.add(a)
    arr.add(b)
    cos.set_item(_DECODE_PARMS, arr)
    pds = PDStream(cos)

    result = pds.internal_get_decode_params(_DECODE_PARMS, _DP)
    assert result == [a, b]


def test_falls_back_to_alias_name() -> None:
    # Some producers spell /DecodeParms as /DP — internal_get_decode_params
    # honours the upstream two-key fallback.
    cos = COSStream()
    parms = COSDictionary()
    cos.set_item(_DP, parms)
    pds = PDStream(cos)

    assert pds.internal_get_decode_params(_DECODE_PARMS, _DP) == [parms]


def test_no_alias_returns_none_when_only_alias_key_used() -> None:
    cos = COSStream()
    cos.set_item(_DP, COSDictionary())
    pds = PDStream(cos)
    # /FDecodeParms has no alias — pass name2=None.
    assert pds.internal_get_decode_params(_F_DECODE_PARMS, None) is None


def test_cosnull_array_entry_yields_empty_dict() -> None:
    cos = COSStream()
    arr = COSArray()
    arr.add(COSNull.NULL)
    valid = COSDictionary()
    valid.set_int("Predictor", 12)
    arr.add(valid)
    cos.set_item(_DECODE_PARMS, arr)
    pds = PDStream(cos)

    result = pds.internal_get_decode_params(_DECODE_PARMS, _DP)
    assert result is not None
    assert len(result) == 2
    # Empty placeholder for COSNull
    assert isinstance(result[0], COSDictionary)
    assert result[0].is_empty()
    assert result[1] is valid


def test_unexpected_type_raises() -> None:
    cos = COSStream()
    cos.set_int(_DECODE_PARMS, 42)
    pds = PDStream(cos)

    with pytest.raises(TypeError):
        pds.internal_get_decode_params(_DECODE_PARMS, _DP)
