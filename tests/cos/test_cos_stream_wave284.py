from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream


def test_filter_presence_helpers_and_clear_filters() -> None:
    flate = COSName.get_pdf_name("FlateDecode")
    ascii85 = COSName.get_pdf_name("ASCII85Decode")

    with COSStream() as stream:
        assert not stream.has_filters()
        assert stream.get_first_filter() is None
        assert stream.get_filters_as_strings() == []

        stream.set_filters([flate, ascii85])

        assert stream.has_filters()
        assert stream.has_filter(flate)
        assert stream.has_filter("ASCII85Decode")
        assert stream.get_first_filter() is flate
        assert stream.get_filters_as_strings() == ["FlateDecode", "ASCII85Decode"]

        stream.clear_filters()

        assert stream.get_filters() is None
        assert not stream.has_filters()


def test_set_filters_preserves_empty_array_shape() -> None:
    with COSStream() as stream:
        stream.set_filters([])

        filters = stream.get_filters()
        assert isinstance(filters, COSArray)
        assert filters.size() == 0
        assert stream.get_filter_list() == []
        assert not stream.has_filters()


def test_decode_parms_helpers_fall_back_to_dp_and_clear_both_keys() -> None:
    decode_parms = COSDictionary()
    short_form = COSDictionary()

    with COSStream() as stream:
        assert not stream.has_decode_parms()

        stream.set_item("DP", short_form)
        assert stream.get_decode_parms() is short_form
        assert stream.has_decode_parms()

        stream.set_item("DecodeParms", decode_parms)
        assert stream.get_decode_parms() is decode_parms

        stream.clear_decode_parms()
        assert stream.get_dictionary_object("DecodeParms") is None
        assert stream.get_dictionary_object("DP") is None
        assert not stream.has_decode_parms()


def test_create_input_stream_accepts_single_stop_filter_string() -> None:
    payload = b"payload that stays compressed when stopping at FlateDecode"
    flate = COSName.get_pdf_name("FlateDecode")

    with COSStream() as stream:
        with stream.create_output_stream(flate) as output:
            output.write(payload)
        raw = stream.to_raw_byte_array()

        assert raw != payload
        assert stream.create_input_stream(stop_filters="FlateDecode").read() == raw
        assert stream.create_input_stream(stop_filters=flate).read() == raw


def test_create_output_stream_rejects_malformed_cos_filter_object() -> None:
    with COSStream() as stream, pytest.raises(
        TypeError,
        match="unexpected /Filter type: COSDictionary",
    ):
        stream.create_output_stream(COSDictionary())


def test_get_filter_list_lenient_on_non_name_scalar() -> None:
    # A non-name, non-array /Filter scalar (here a COSDictionary) is treated
    # leniently as "no filters" — upstream getFilterList falls through to an
    # empty list and passes the body through verbatim (wave 1564).
    with COSStream() as stream:
        stream.set_item("Filter", COSDictionary())

        assert stream.get_filter_list() == []


def test_get_filter_list_rejects_non_name_array_entry() -> None:
    # A non-name element *inside* a /Filter array is rejected — upstream
    # throws IOException ("Forbidden type in filter array: ...") -> OSError.
    with COSStream() as stream:
        stream.set_item("Filter", COSArray([COSInteger.get(1)]))

        with pytest.raises(OSError, match="Forbidden type in filter array"):
            stream.get_filter_list()
