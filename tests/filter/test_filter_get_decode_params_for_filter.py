"""Hand-written tests for ``Filter.get_decode_params_for_filter`` —
the strict, ``/Filter``-aware variant that mirrors upstream's
``protected COSDictionary getDecodeParams(COSDictionary, int)``.
"""

from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName
from pypdfbox.filter import Filter


class TestGetDecodeParamsForFilterNullInput:
    def test_none_dictionary_returns_empty(self):
        out = Filter.get_decode_params_for_filter(None, 0)
        assert isinstance(out, COSDictionary)
        assert out.size() == 0


class TestGetDecodeParamsForFilterSingleName:
    def test_single_filter_name_with_dict_decodeparms_returns_dict(self):
        params = COSDictionary()
        params.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
        inner = COSDictionary()
        inner.set_int("Predictor", 12)
        params.set_item("DecodeParms", inner)
        out = Filter.get_decode_params_for_filter(params, 0)
        assert out is inner

    def test_short_keys_f_and_dp_resolve(self):
        # /F and /DP are the abbreviated forms — both must be honoured
        # the same way as /Filter and /DecodeParms.
        params = COSDictionary()
        params.set_item("F", COSName.get_pdf_name("Fl"))
        inner = COSDictionary()
        inner.set_int("Predictor", 2)
        params.set_item("DP", inner)
        out = Filter.get_decode_params_for_filter(params, 0)
        assert out is inner

    def test_missing_filter_with_dict_returns_empty(self):
        # Without a /Filter entry we cannot validate shape, so the
        # strict variant returns empty — upstream behaviour.
        params = COSDictionary()
        inner = COSDictionary()
        inner.set_int("Predictor", 2)
        params.set_item("DecodeParms", inner)
        out = Filter.get_decode_params_for_filter(params, 0)
        assert out.size() == 0


class TestGetDecodeParamsForFilterArray:
    def test_array_filter_with_array_decodeparms(self):
        params = COSDictionary()
        filter_arr = COSArray()
        filter_arr.add(COSName.get_pdf_name("ASCII85Decode"))
        filter_arr.add(COSName.get_pdf_name("FlateDecode"))
        params.set_item("Filter", filter_arr)

        dp_arr = COSArray()
        first = COSDictionary()
        first.set_int("Predictor", 1)
        second = COSDictionary()
        second.set_int("Predictor", 12)
        dp_arr.add(first)
        dp_arr.add(second)
        params.set_item("DecodeParms", dp_arr)

        assert Filter.get_decode_params_for_filter(params, 0) is first
        assert Filter.get_decode_params_for_filter(params, 1) is second

    def test_array_index_out_of_range_returns_empty(self):
        params = COSDictionary()
        filter_arr = COSArray()
        filter_arr.add(COSName.get_pdf_name("FlateDecode"))
        params.set_item("Filter", filter_arr)
        params.set_item("DecodeParms", COSArray())
        out = Filter.get_decode_params_for_filter(params, 5)
        assert out.size() == 0

    def test_array_filter_with_non_dict_entry_returns_empty(self):
        # If the /DecodeParms array entry at the requested index is not
        # itself a dictionary (e.g. a /Null placeholder), return empty.
        params = COSDictionary()
        filter_arr = COSArray()
        filter_arr.add(COSName.get_pdf_name("FlateDecode"))
        filter_arr.add(COSName.get_pdf_name("ASCII85Decode"))
        params.set_item("Filter", filter_arr)

        dp_arr = COSArray()
        dp_arr.add(COSBoolean.TRUE)  # bogus non-dict entry
        dp_arr.add(COSDictionary())
        params.set_item("DecodeParms", dp_arr)

        out = Filter.get_decode_params_for_filter(params, 0)
        assert out.size() == 0


class TestGetDecodeParamsForFilterShapeMismatch:
    def test_single_name_filter_with_array_decodeparms_returns_empty(self):
        # Mismatch: name + array — upstream returns empty (no logging
        # since only the array vs. dict conflict triggers the warn).
        params = COSDictionary()
        params.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
        params.set_item("DecodeParms", COSArray())
        out = Filter.get_decode_params_for_filter(params, 0)
        assert out.size() == 0

    def test_array_filter_with_dict_decodeparms_returns_empty(self):
        # Mismatch: array filter + single dict — upstream returns empty.
        params = COSDictionary()
        filter_arr = COSArray()
        filter_arr.add(COSName.get_pdf_name("FlateDecode"))
        filter_arr.add(COSName.get_pdf_name("ASCII85Decode"))
        params.set_item("Filter", filter_arr)
        params.set_item("DecodeParms", COSDictionary())
        out = Filter.get_decode_params_for_filter(params, 0)
        assert out.size() == 0

    def test_unexpected_decode_parms_type_logs_error(self, caplog):
        # When /Filter and /DecodeParms are both *not* COSArray and the
        # combination is not name+dict either, log an error per upstream.
        params = COSDictionary()
        params.set_item("Filter", COSName.get_pdf_name("FlateDecode"))
        # COSBoolean is neither a COSDictionary nor a COSArray → error.
        params.set_item("DecodeParms", COSBoolean.TRUE)
        with caplog.at_level(logging.ERROR, logger="pypdfbox.filter.filter"):
            out = Filter.get_decode_params_for_filter(params, 0)
        assert out.size() == 0
        assert any(
            "Expected DecodeParams to be an Array or Dictionary" in rec.message
            for rec in caplog.records
        )
