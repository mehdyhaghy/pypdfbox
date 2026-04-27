"""Upstream-named accessor parity for ``FilterFactory`` and ``Filter``.

These exercise the ``INSTANCE`` singleton, ``get_filter``,
``get_filter_by_short_name``, ``Filter.decode_result``,
``Filter.get_decode_params``, and ``Filter.is_decompression_input_size_known``
shapes that mirror ``org.apache.pdfbox.filter.FilterFactory`` /
``org.apache.pdfbox.filter.Filter``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.filter import (
    ASCII85Decode,
    ASCIIHexDecode,
    CCITTFaxDecode,
    Filter,
    FilterFactory,
    FlateDecode,
    JBIG2Decode,
    JPXDecode,
    LZWDecode,
    RunLengthDecode,
)
from pypdfbox.filter.decode_result import DecodeResult


class TestFilterFactorySingleton:
    def test_instance_exists(self):
        assert FilterFactory.INSTANCE is not None

    def test_instance_is_filter_factory(self):
        assert isinstance(FilterFactory.INSTANCE, FilterFactory)

    def test_instance_is_singleton(self):
        # Two attribute reads return the same object.
        assert FilterFactory.INSTANCE is FilterFactory.INSTANCE


class TestGetFilter:
    def test_get_filter_flate(self):
        f = FilterFactory.get_filter("FlateDecode")
        assert isinstance(f, FlateDecode)

    def test_get_filter_ascii_hex(self):
        f = FilterFactory.get_filter("ASCIIHexDecode")
        assert isinstance(f, ASCIIHexDecode)

    def test_get_filter_ascii85(self):
        f = FilterFactory.get_filter("ASCII85Decode")
        assert isinstance(f, ASCII85Decode)

    def test_get_filter_lzw(self):
        f = FilterFactory.get_filter("LZWDecode")
        assert isinstance(f, LZWDecode)

    def test_get_filter_run_length(self):
        f = FilterFactory.get_filter("RunLengthDecode")
        assert isinstance(f, RunLengthDecode)

    def test_get_filter_ccitt(self):
        f = FilterFactory.get_filter("CCITTFaxDecode")
        assert isinstance(f, CCITTFaxDecode)

    def test_get_filter_jpx(self):
        f = FilterFactory.get_filter("JPXDecode")
        assert isinstance(f, JPXDecode)

    def test_get_filter_jbig2(self):
        f = FilterFactory.get_filter("JBIG2Decode")
        assert isinstance(f, JBIG2Decode)

    def test_get_filter_accepts_cos_name(self):
        f = FilterFactory.get_filter(COSName.get_pdf_name("FlateDecode"))
        assert isinstance(f, FlateDecode)

    def test_get_filter_unknown_raises(self):
        with pytest.raises(KeyError):
            FilterFactory.get_filter("BogusDecode")


class TestGetFilterByShortName:
    def test_short_fl_returns_flate(self):
        f = FilterFactory.get_filter_by_short_name("Fl")
        assert isinstance(f, FlateDecode)

    def test_short_fl_matches_long(self):
        # The short-name lookup must return the same singleton instance
        # as the long-name lookup.
        long_inst = FilterFactory.get_filter("FlateDecode")
        short_inst = FilterFactory.get_filter_by_short_name("Fl")
        assert short_inst is long_inst

    def test_short_ahx_returns_ascii_hex(self):
        f = FilterFactory.get_filter_by_short_name("AHx")
        assert isinstance(f, ASCIIHexDecode)

    def test_short_a85_returns_ascii85(self):
        f = FilterFactory.get_filter_by_short_name("A85")
        assert isinstance(f, ASCII85Decode)

    def test_short_lzw_returns_lzw(self):
        f = FilterFactory.get_filter_by_short_name("LZW")
        assert isinstance(f, LZWDecode)

    def test_short_rl_returns_run_length(self):
        f = FilterFactory.get_filter_by_short_name("RL")
        assert isinstance(f, RunLengthDecode)

    def test_short_ccf_returns_ccitt(self):
        f = FilterFactory.get_filter_by_short_name("CCF")
        assert isinstance(f, CCITTFaxDecode)

    def test_short_jpx_returns_jpx(self):
        f = FilterFactory.get_filter_by_short_name("JPX")
        assert isinstance(f, JPXDecode)

    def test_short_name_accepts_cos_name(self):
        f = FilterFactory.get_filter_by_short_name(COSName.get_pdf_name("Fl"))
        assert isinstance(f, FlateDecode)

    def test_unknown_short_name_raises(self):
        with pytest.raises(KeyError):
            FilterFactory.get_filter_by_short_name("XYZ")

    def test_long_name_via_short_lookup_raises(self):
        # ``get_filter_by_short_name`` strictly requires an abbreviation.
        with pytest.raises(KeyError):
            FilterFactory.get_filter_by_short_name("FlateDecode")


class TestFilterDecodeResultHelper:
    def test_returns_decode_result(self):
        r = Filter.decode_result()
        assert isinstance(r, DecodeResult)

    def test_default_parameters_is_empty_cos_dict(self):
        r = Filter.decode_result()
        assert isinstance(r.parameters, COSDictionary)
        assert r.bytes_written == 0

    def test_passes_through_parameters_and_count(self):
        params = COSDictionary()
        params.set_int("Predictor", 12)
        r = Filter.decode_result(params, 1024)
        assert r.parameters is params
        assert r.bytes_written == 1024


class TestFilterGetDecodeParams:
    def test_none_parameters_returns_empty_dict(self):
        out = Filter.get_decode_params(None, 0)
        assert isinstance(out, COSDictionary)
        assert out.size() == 0

    def test_single_dict_decode_parms(self):
        parameters = COSDictionary()
        inner = COSDictionary()
        inner.set_int("Predictor", 15)
        parameters.set_item("DecodeParms", inner)
        out = Filter.get_decode_params(parameters, 0)
        assert out is inner

    def test_dp_abbreviation(self):
        parameters = COSDictionary()
        inner = COSDictionary()
        inner.set_int("Predictor", 2)
        parameters.set_item("DP", inner)
        out = Filter.get_decode_params(parameters, 0)
        assert out is inner

    def test_array_indexed(self):
        parameters = COSDictionary()
        arr = COSArray()
        first = COSDictionary()
        first.set_int("Predictor", 1)
        second = COSDictionary()
        second.set_int("Predictor", 12)
        arr.add(first)
        arr.add(second)
        parameters.set_item("DecodeParms", arr)
        assert Filter.get_decode_params(parameters, 0) is first
        assert Filter.get_decode_params(parameters, 1) is second

    def test_array_out_of_range_returns_empty(self):
        parameters = COSDictionary()
        arr = COSArray()
        parameters.set_item("DecodeParms", arr)
        out = Filter.get_decode_params(parameters, 7)
        assert isinstance(out, COSDictionary)
        assert out.size() == 0

    def test_missing_key_returns_empty(self):
        parameters = COSDictionary()
        out = Filter.get_decode_params(parameters, 0)
        assert isinstance(out, COSDictionary)
        assert out.size() == 0


class TestIsDecompressionInputSizeKnown:
    def test_default_true_on_flate(self):
        # The base implementation defaults to True; concrete filters
        # inherit unless they override. FlateDecode does not override,
        # so the default applies.
        assert FilterFactory.get_filter("FlateDecode").is_decompression_input_size_known() is True

    def test_default_true_on_lzw(self):
        assert FilterFactory.get_filter("LZWDecode").is_decompression_input_size_known() is True
