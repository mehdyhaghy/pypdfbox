"""Wave 1368 (agent D) — ``/DecodeParms`` alignment with ``/Filter`` array.

ISO 32000-1 §7.3.8.2 says ``/DecodeParms`` is either:

* a single dictionary when ``/Filter`` is a single name, or
* an array parallel to ``/Filter`` (entry per filter, ``null`` for
  filters with no parameters), or
* an array entry that is the null literal (mapped to an empty dict).

Upstream PDFBox enforces this in
``Filter#getDecodeParams(COSDictionary, int)`` which:

* accepts ``COSName``+``COSDictionary``;
* accepts ``COSArray``+``COSArray`` (index into the array);
* logs an error and returns an empty dictionary on any mismatch
  (``COSArray``+``COSDictionary`` is the classic malformed shape).

These tests pin down the strict resolver (``get_decode_params_for_filter``)
and the lenient per-filter resolver each filter uses internally.
"""

from __future__ import annotations

import io
import logging

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull
from pypdfbox.filter import FlateDecode, LZWDecode
from pypdfbox.filter.filter import Filter


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def test_get_decode_params_single_name_with_dict() -> None:
    """Single ``/Filter`` name + dict ``/DecodeParms`` returns that dict."""
    stream = COSDictionary()
    stream.set_item("Filter", _name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    dp.set_int("Columns", 4)
    stream.set_item("DecodeParms", dp)
    result = Filter.get_decode_params_for_filter(stream, 0)
    assert result is dp
    assert result.get_int("Predictor", 1) == 12


def test_get_decode_params_array_filter_array_params_indexed() -> None:
    """Array ``/Filter`` + array ``/DecodeParms`` returns the indexed dict."""
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    # First filter has no parameters (null literal).
    parms.add(COSNull.NULL)
    dp_flate = COSDictionary()
    dp_flate.set_int("Predictor", 15)
    dp_flate.set_int("Columns", 8)
    parms.add(dp_flate)
    stream.set_item("DecodeParms", parms)
    # Index 0 → null literal → empty dictionary.
    r0 = Filter.get_decode_params_for_filter(stream, 0)
    assert isinstance(r0, COSDictionary)
    assert r0.get_int("Predictor", 1) == 1
    # Index 1 → the FlateDecode params dict.
    r1 = Filter.get_decode_params_for_filter(stream, 1)
    assert r1 is dp_flate


def test_get_decode_params_array_filter_dict_params_returns_empty() -> None:
    """Malformed array+dict combination silently yields empty dictionary.

    Upstream Java only logs the error when *neither* filter nor params
    is a COSArray — this combination (array filter + dict params) falls
    through the if/elif chain and returns an empty dict without warning.
    """
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    stream.set_item("DecodeParms", dp)
    result = Filter.get_decode_params_for_filter(stream, 0)
    assert isinstance(result, COSDictionary)
    assert result.get_int("Predictor", 1) == 1  # not the misaligned dict


def test_get_decode_params_single_name_with_non_dict_params_logs_error(
    caplog,
) -> None:
    """Single filter + non-dict, non-array DecodeParms is malformed.

    This is the case that upstream actually logs an error for: ``obj``
    is non-null, neither ``filter`` nor ``obj`` is an array, but ``obj``
    is not a dictionary (e.g. a string or integer slipped through).
    """
    stream = COSDictionary()
    stream.set_item("Filter", _name("FlateDecode"))
    # /DecodeParms set to a COSName — neither dict nor array. The
    # resolver should log an error and return an empty dict.
    stream.set_item("DecodeParms", _name("not-a-dictionary"))
    with caplog.at_level(logging.ERROR, logger="pypdfbox.filter.filter"):
        result = Filter.get_decode_params_for_filter(stream, 0)
    assert isinstance(result, COSDictionary)
    assert result.size() == 0
    # The error log fires on this shape per upstream parity.
    assert any("DecodeParams" in rec.message for rec in caplog.records)


def test_get_decode_params_array_out_of_bounds_index_returns_empty() -> None:
    """Index past the end of the array returns an empty dict."""
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSDictionary())
    stream.set_item("DecodeParms", parms)
    # Asking for index 5 of a 1-entry array → empty dict (no exception).
    result = Filter.get_decode_params_for_filter(stream, 5)
    assert isinstance(result, COSDictionary)
    assert result.size() == 0


def test_get_decode_params_none_dictionary_returns_empty() -> None:
    """A null stream dictionary still returns an empty COSDictionary."""
    result = Filter.get_decode_params_for_filter(None, 0)
    assert isinstance(result, COSDictionary)
    assert result.size() == 0


def test_get_decode_params_dp_short_key_works() -> None:
    """``/DP`` (short form) is honoured alongside ``/DecodeParms``."""
    stream = COSDictionary()
    stream.set_item("F", _name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    stream.set_item("DP", dp)
    result = Filter.get_decode_params_for_filter(stream, 0)
    assert result is dp


def test_flate_decode_array_decode_parms_indexed_round_trip() -> None:
    """FlateDecode's internal resolver picks the right /DecodeParms entry.

    A chain ``[/ASCIIHexDecode /FlateDecode]`` with parallel array
    ``/DecodeParms`` must give the FlateDecode at index 1 its own params.
    """
    raw = bytes(range(8)) * 4  # 32 bytes, 4 rows of 8.
    flate = FlateDecode()
    # Build params dict for flate (predictor 12 over 8 cols, 8-bit, 1 color).
    flate_params = COSDictionary()
    flate_params.set_int("Predictor", 12)
    flate_params.set_int("Columns", 8)
    flate_params.set_int("BitsPerComponent", 8)
    flate_params.set_int("Colors", 1)
    # Encode with the predictor params attached directly.
    enc_buf = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc_buf, flate_params)

    # Build a stream-dictionary view: /Filter = [/ASCIIHexDecode /FlateDecode]
    # /DecodeParms = [ null  flate_params ]
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)
    parms.add(flate_params)
    stream.set_item("DecodeParms", parms)

    # Decode flate at index 1; resolver should pull flate_params.
    dec_buf = io.BytesIO()
    flate.decode(io.BytesIO(enc_buf.getvalue()), dec_buf, stream, 1)
    assert dec_buf.getvalue() == raw


def test_lzw_decode_array_decode_parms_indexed_round_trip() -> None:
    """LZW honours the same array-indexed /DecodeParms shape."""
    raw = b"ABCDEFGH" * 8  # 64 bytes
    lzw = LZWDecode()
    lzw_params = COSDictionary()
    lzw_params.set_int("EarlyChange", 1)
    enc_buf = io.BytesIO()
    lzw.encode(io.BytesIO(raw), enc_buf, lzw_params)

    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("LZWDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)
    parms.add(lzw_params)
    stream.set_item("DecodeParms", parms)

    dec_buf = io.BytesIO()
    lzw.decode(io.BytesIO(enc_buf.getvalue()), dec_buf, stream, 1)
    assert dec_buf.getvalue() == raw


def test_array_parms_with_null_entry_treated_as_empty_dict() -> None:
    """An array entry that is the null literal yields an empty dict."""
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("FlateDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)
    parms.add(COSDictionary())
    stream.set_item("DecodeParms", parms)
    # Both indices → empty dict (null literal entry, or empty dict entry).
    r0 = Filter.get_decode_params_for_filter(stream, 0)
    r1 = Filter.get_decode_params_for_filter(stream, 1)
    assert r0.size() == 0
    assert r1.size() == 0
