from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull, COSStream, COSString
from pypdfbox.pdmodel.common import PDStream

_DECODE_PARMS = COSName.get_pdf_name("DecodeParms")
_DP = COSName.get_pdf_name("DP")
_FDECODE_PARMS = COSName.get_pdf_name("FDecodeParms")
_FFILTER = COSName.get_pdf_name("FFilter")
_FILTER = COSName.get_pdf_name("Filter")
_METADATA = COSName.get_pdf_name("Metadata")


def test_decode_parms_falls_back_to_dp_alias_wave493() -> None:
    stream = PDStream()
    parms = COSDictionary()
    parms.set_int("Predictor", 12)
    stream.get_cos_object().set_item(_DP, parms)

    out = stream.get_decode_parms()

    assert out is not None
    assert len(out) == 1
    assert out[0].get_int("Predictor") == 12


def test_decode_parms_array_preserves_null_slots_wave493() -> None:
    stream = PDStream()
    first = COSDictionary()
    first.set_int("Columns", 4)
    second = COSDictionary()
    second.set_int("Colors", 3)
    stream.get_cos_object().set_item(
        _DECODE_PARMS,
        COSArray([first, COSNull.NULL, second]),
    )

    out = stream.get_decode_parms()

    assert out is not None
    assert [d.get_int("Columns", -1) for d in out] == [4, -1, -1]
    assert [d.get_int("Colors", -1) for d in out] == [-1, -1, 3]


def test_set_decode_parms_none_removes_canonical_and_alias_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(_DECODE_PARMS, COSDictionary())
    stream.get_cos_object().set_item(_DP, COSDictionary())

    stream.set_decode_parms(None)

    assert stream.get_cos_object().contains_key(_DECODE_PARMS) is False
    assert stream.get_cos_object().contains_key(_DP) is False


def test_decode_parms_rejects_unexpected_array_entry_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(_DECODE_PARMS, COSArray([COSString("bad")]))

    with pytest.raises(TypeError, match="unexpected /DecodeParms entry type"):
        stream.get_decode_parms()


def test_filter_arrays_reject_non_name_entries_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(_FILTER, COSArray([COSString("FlateDecode")]))

    with pytest.raises(TypeError, match="non-name entry in /Filter array"):
        stream.get_filters()


def test_metadata_rejects_non_stream_entry_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(_METADATA, COSDictionary())

    with pytest.raises(TypeError, match="unexpected /Metadata type"):
        stream.get_metadata()


def test_set_metadata_accepts_pd_metadata_like_wrapper_wave493() -> None:
    class MetadataWrapper:
        def __init__(self, cos_stream: COSStream) -> None:
            self._cos_stream = cos_stream

        def get_cos_object(self) -> COSStream:
            return self._cos_stream

    stream = PDStream()
    metadata_stream = COSStream()

    stream.set_metadata(MetadataWrapper(metadata_stream))  # type: ignore[arg-type]

    assert stream.get_metadata() is metadata_stream
    assert stream.has_metadata() is True


def test_file_filter_helpers_round_trip_and_clear_wave493() -> None:
    stream = PDStream()

    stream.set_file_filters(["ASCII85Decode", COSName.FLATE_DECODE])  # type: ignore[attr-defined]

    assert stream.get_file_filters_as_strings() == ["ASCII85Decode", "FlateDecode"]
    assert isinstance(stream.get_cos_object().get_dictionary_object(_FFILTER), COSArray)

    stream.set_file_filters(None)
    assert stream.get_file_filters() == []


def test_file_filter_array_rejects_non_name_entries_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(_FFILTER, COSArray([COSString("bad")]))

    with pytest.raises(TypeError, match="non-name entry in /FFilter array"):
        stream.get_file_filters()


def test_file_decode_parms_alias_methods_round_trip_array_wave493() -> None:
    stream = PDStream()
    first = COSDictionary()
    first.set_int("Predictor", 1)
    second = COSDictionary()
    second.set_int("Predictor", 15)

    stream.set_file_decode_params([first, second])

    stored = stream.get_cos_object().get_dictionary_object(_FDECODE_PARMS)
    assert isinstance(stored, COSArray)
    out = stream.get_file_decode_params()
    assert out is not None
    assert [d.get_int("Predictor") for d in out] == [1, 15]


def test_file_decode_parms_array_preserves_null_slots_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(
        _FDECODE_PARMS,
        COSArray([COSNull.NULL, COSDictionary()]),
    )

    out = stream.get_file_decode_parms()

    assert out is not None
    assert len(out) == 2
    assert all(isinstance(entry, COSDictionary) for entry in out)


def test_file_decode_parms_rejects_unexpected_type_wave493() -> None:
    stream = PDStream()
    stream.get_cos_object().set_item(_FDECODE_PARMS, COSString("bad"))

    with pytest.raises(TypeError, match="unexpected /FDecodeParms type"):
        stream.get_file_decode_parms()

