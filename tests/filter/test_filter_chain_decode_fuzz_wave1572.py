"""Wave 1572 (agent E) — chained-filter decode fuzz + parity.

Hammers the multi-filter ``/Filter`` decode path and the per-filter
``/DecodeParms`` (a.k.a. ``/DP``) resolution per ISO 32000-1 §7.3.8.2,
checked against Apache PDFBox 3.0.7 semantics:

* a 2-filter chain ``[/ASCII85Decode /FlateDecode]`` round-trips (encode
  in reverse, decode in order);
* ``/DecodeParms`` as an array aligned with ``/Filter`` — ``params[i]``
  applies to ``filter[i]``, with the null literal for filters needing no
  parameters;
* the single-filter + single-dict form (NOT wrapped in arrays);
* abbreviated names (``/A85 /Fl /AHx /LZW /RL``) resolving to full filters;
* mismatched lengths (more filters than params → missing params default
  to an empty dict);
* ``/Filter`` as a single name vs an array;
* predictor params reaching the right filter in the chain;
* the malformed **array ``/Filter`` + single dict ``/DecodeParms``** shape
  — upstream applies NO params to any filter in the chain (the wave 1572
  bug fix: pypdfbox used to apply the lone dict to every filter index);
* an unknown filter name raising on the ``COSStream`` decode path;
* an empty filter list (passthrough).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull, COSStream
from pypdfbox.filter import (
    ASCII85Decode,
    ASCIIHexDecode,
    FilterFactory,
    FlateDecode,
    LZWDecode,
    RunLengthDecode,
)
from pypdfbox.filter._decode_params import resolve_decode_params
from pypdfbox.filter.filter import Filter


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _encode_reverse(filters: list[Filter], raw: bytes) -> bytes:
    """Encode ``raw`` by applying ``filters`` in reverse (producer order).

    PDF ``/Filter`` arrays decode left-to-right, so the producer encodes
    right-to-left: the rightmost filter is applied to the raw bytes first.
    """
    data = raw
    for f in reversed(filters):
        buf = io.BytesIO()
        f.encode(io.BytesIO(data), buf, COSDictionary())
        data = buf.getvalue()
    return data


def _build_stream(filters: list[COSName] | COSName, raw_body: bytes) -> COSStream:
    s = COSStream()
    s.set_filters(filters)
    s.set_raw_data(raw_body)
    return s


# ---------------------------------------------------------------------------
# 2-filter chain round-trip via the COSStream decode path.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"A",
        b"hello world",
        b"\x00\xff" * 64,
        bytes(range(256)),
        b"PDF stream payload " * 100,
    ],
    ids=["empty", "one", "ascii", "binary", "allbytes", "long"],
)
def test_ascii85_flate_chain_round_trip(raw: bytes) -> None:
    """``[/ASCII85Decode /FlateDecode]`` decodes back to the raw payload."""
    chain = [ASCII85Decode(), FlateDecode()]
    body = _encode_reverse(chain, raw)
    stream = _build_stream([_name("ASCII85Decode"), _name("FlateDecode")], body)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


@pytest.mark.parametrize(
    "names",
    [
        ["ASCIIHexDecode", "FlateDecode"],
        ["ASCII85Decode", "LZWDecode"],
        ["RunLengthDecode", "FlateDecode"],
        ["ASCIIHexDecode", "ASCII85Decode", "FlateDecode"],
    ],
    ids=["ahx_fl", "a85_lzw", "rl_fl", "three"],
)
def test_various_two_and_three_filter_chains(names: list[str]) -> None:
    raw = b"chain payload \x01\x02\x03" * 40
    instances = [FilterFactory.get(n) for n in names]
    body = _encode_reverse(instances, raw)
    stream = _build_stream([_name(n) for n in names], body)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


# ---------------------------------------------------------------------------
# Abbreviated filter names resolve in a chain.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "abbrev,full",
    [
        ("A85", "ASCII85Decode"),
        ("Fl", "FlateDecode"),
        ("AHx", "ASCIIHexDecode"),
        ("LZW", "LZWDecode"),
        ("RL", "RunLengthDecode"),
    ],
    ids=["a85", "fl", "ahx", "lzw", "rl"],
)
def test_abbreviated_name_resolves_same_instance(abbrev: str, full: str) -> None:
    assert FilterFactory.get(abbrev) is FilterFactory.get(full)


def test_abbreviated_chain_decode_round_trip() -> None:
    """An all-abbreviated chain ``[/A85 /Fl]`` decodes via the alias map."""
    raw = b"abbreviated chain" * 30
    chain = [ASCII85Decode(), FlateDecode()]
    body = _encode_reverse(chain, raw)
    stream = _build_stream([_name("A85"), _name("Fl")], body)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


def test_mixed_abbrev_and_full_names_in_chain() -> None:
    raw = b"mixed forms \xaa\xbb" * 20
    chain = [ASCIIHexDecode(), FlateDecode()]
    body = _encode_reverse(chain, raw)
    stream = _build_stream([_name("AHx"), _name("Fl")], body)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


# ---------------------------------------------------------------------------
# Single-filter + single-dict /DecodeParms (NOT wrapped in arrays).
# ---------------------------------------------------------------------------


def test_single_name_single_dict_decode_parms_predictor() -> None:
    """Single ``/Filter`` name + dict ``/DecodeParms`` feeds the predictor."""
    raw = bytes(range(8)) * 6  # 6 rows of 8 columns.
    flate = FlateDecode()
    params = COSDictionary()
    params.set_int("Predictor", 12)
    params.set_int("Columns", 8)
    params.set_int("BitsPerComponent", 8)
    params.set_int("Colors", 1)
    enc = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc, params)

    stream = COSStream()
    stream.set_filters(_name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    dp.set_int("Columns", 8)
    dp.set_int("BitsPerComponent", 8)
    dp.set_int("Colors", 1)
    stream.set_item("DecodeParms", dp)
    stream.set_raw_data(enc.getvalue())
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


def test_single_dict_resolved_for_index_zero() -> None:
    stream = COSDictionary()
    stream.set_item("Filter", _name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    stream.set_item("DecodeParms", dp)
    assert resolve_decode_params(stream, 0) is dp


# ---------------------------------------------------------------------------
# Array /DecodeParms aligned with /Filter array — params[i] → filter[i].
# ---------------------------------------------------------------------------


def test_array_decode_parms_aligned_per_filter() -> None:
    """``[/ASCIIHexDecode /FlateDecode]`` with ``[null params]`` aligns."""
    raw = bytes(range(8)) * 4
    flate = FlateDecode()
    flate_params = COSDictionary()
    flate_params.set_int("Predictor", 12)
    flate_params.set_int("Columns", 8)
    flate_params.set_int("BitsPerComponent", 8)
    flate_params.set_int("Colors", 1)
    enc = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc, flate_params)
    # Now ASCIIHex-encode the flate body to build the chain payload.
    ahx = ASCIIHexDecode()
    ahx_buf = io.BytesIO()
    ahx.encode(io.BytesIO(enc.getvalue()), ahx_buf, COSDictionary())

    stream = COSStream()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)  # ASCIIHexDecode needs no params.
    parms.add(flate_params)  # FlateDecode predictor params.
    stream.set_item("DecodeParms", parms)
    stream.set_raw_data(ahx_buf.getvalue())
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


def test_array_parms_null_entry_is_empty_dict() -> None:
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    parms.add(dp)
    stream.set_item("DecodeParms", parms)
    assert resolve_decode_params(stream, 0).size() == 0
    assert resolve_decode_params(stream, 1) is dp


def test_array_parms_indexed_predictor_reaches_right_filter() -> None:
    """The predictor params at index 1 reach FlateDecode, not index 0."""
    raw = bytes(range(8)) * 4
    flate = FlateDecode()
    flate_params = COSDictionary()
    flate_params.set_int("Predictor", 12)
    flate_params.set_int("Columns", 8)
    flate_params.set_int("BitsPerComponent", 8)
    flate_params.set_int("Colors", 1)
    enc = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc, flate_params)

    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)
    parms.add(flate_params)
    stream.set_item("DecodeParms", parms)
    # Decoding FlateDecode at index 1 must pick up the predictor.
    dec = io.BytesIO()
    flate.decode(io.BytesIO(enc.getvalue()), dec, stream, 1)
    assert dec.getvalue() == raw


# ---------------------------------------------------------------------------
# THE BUG: array /Filter + single dict /DecodeParms must apply NO params.
# ---------------------------------------------------------------------------


def test_array_filter_single_dict_parms_not_applied_to_chain() -> None:
    """A multi-filter chain carrying one dict /DecodeParms applies it to
    NO filter — upstream ``Filter#getDecodeParams`` returns an empty dict
    for the array-filter + single-dict mismatch. Before wave 1572 the
    per-filter resolver returned the lone dict for every index."""
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    dp.set_int("Columns", 8)
    stream.set_item("DecodeParms", dp)
    # Neither filter index gets the dict.
    assert resolve_decode_params(stream, 0).get_int("Predictor", 1) == 1
    assert resolve_decode_params(stream, 1).get_int("Predictor", 1) == 1


def test_array_filter_single_dict_matches_strict_resolver() -> None:
    """The lenient per-filter resolver now agrees with the strict
    ``Filter.get_decode_params_for_filter`` for the mismatch shape."""
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    dp = COSDictionary()
    dp.set_int("Predictor", 12)
    stream.set_item("DecodeParms", dp)
    for i in (0, 1):
        lenient = resolve_decode_params(stream, i)
        strict = Filter.get_decode_params_for_filter(stream, i)
        assert lenient.get_int("Predictor", 1) == strict.get_int("Predictor", 1)


def test_array_filter_single_dict_chain_decode_ignores_predictor() -> None:
    """End-to-end: a real ``[/ASCIIHexDecode /FlateDecode]`` body that was
    NOT predictor-encoded decodes cleanly even though a stray single dict
    ``/DecodeParms`` declares a predictor — because the predictor is not
    applied to the chain. Had the lone dict been (wrongly) applied to
    FlateDecode, the decode would mangle the bytes."""
    raw = b"no predictor here" * 16
    flate = FlateDecode()
    enc = io.BytesIO()
    flate.encode(io.BytesIO(raw), enc, COSDictionary())  # plain, no predictor.
    ahx = ASCIIHexDecode()
    ahx_buf = io.BytesIO()
    ahx.encode(io.BytesIO(enc.getvalue()), ahx_buf, COSDictionary())

    stream = COSStream()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    stray = COSDictionary()
    stray.set_int("Predictor", 12)
    stray.set_int("Columns", 8)
    stream.set_item("DecodeParms", stray)
    stream.set_raw_data(ahx_buf.getvalue())
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


# ---------------------------------------------------------------------------
# Mismatched lengths — more filters than params → missing params empty.
# ---------------------------------------------------------------------------


def test_more_filters_than_params_missing_treated_empty() -> None:
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("FlateDecode"))
    filt.add(_name("LZWDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    dp0 = COSDictionary()
    dp0.set_int("Predictor", 2)
    parms.add(dp0)  # only one entry for three filters.
    stream.set_item("DecodeParms", parms)
    assert resolve_decode_params(stream, 0) is dp0
    # Indices past the array end → empty dict (no exception).
    assert resolve_decode_params(stream, 1).size() == 0
    assert resolve_decode_params(stream, 2).size() == 0


def test_array_index_out_of_bounds_returns_empty() -> None:
    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSDictionary())
    stream.set_item("DecodeParms", parms)
    assert resolve_decode_params(stream, 9).size() == 0


# ---------------------------------------------------------------------------
# /DP short form precedence and parity with /DecodeParms.
# ---------------------------------------------------------------------------


def test_dp_short_form_honoured() -> None:
    stream = COSDictionary()
    stream.set_item("Filter", _name("FlateDecode"))
    dp = COSDictionary()
    dp.set_int("Predictor", 7)
    stream.set_item("DP", dp)
    assert resolve_decode_params(stream, 0) is dp


def test_decode_parms_long_form_precedence_over_dp() -> None:
    """When both keys exist, ``/DecodeParms`` (long) wins — upstream
    resolves ``getDictionaryObject(DECODE_PARMS, DP)``."""
    stream = COSDictionary()
    stream.set_item("Filter", _name("FlateDecode"))
    long_dp = COSDictionary()
    long_dp.set_int("Predictor", 11)
    short_dp = COSDictionary()
    short_dp.set_int("Predictor", 22)
    stream.set_item("DecodeParms", long_dp)
    stream.set_item("DP", short_dp)
    assert resolve_decode_params(stream, 0) is long_dp


# ---------------------------------------------------------------------------
# /Filter single name vs array shapes.
# ---------------------------------------------------------------------------


def test_filter_single_name_round_trip() -> None:
    raw = b"single filter" * 50
    flate = FlateDecode()
    body = _encode_reverse([flate], raw)
    stream = _build_stream(_name("FlateDecode"), body)
    assert stream.get_filters_as_strings() == ["FlateDecode"]
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


def test_filter_array_single_element_round_trip() -> None:
    raw = b"single-element array filter" * 20
    flate = FlateDecode()
    body = _encode_reverse([flate], raw)
    stream = COSStream()
    filt = COSArray()
    filt.add(_name("FlateDecode"))
    stream.set_item("Filter", filt)
    stream.set_raw_data(body)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


# ---------------------------------------------------------------------------
# Direct-codec convenience: flat predictor dict with no /Filter, no /DP.
# ---------------------------------------------------------------------------


def test_flat_predictor_dict_no_filter_returns_self() -> None:
    flat = COSDictionary()
    flat.set_int("Predictor", 15)
    flat.set_int("Columns", 8)
    assert resolve_decode_params(flat, 0) is flat


def test_no_filter_decode_parms_subdict_resolves() -> None:
    """A params wrapper with /DecodeParms sub-dict but no /Filter (the
    direct-codec call shape) resolves the inner dict."""
    wrapper = COSDictionary()
    inner = COSDictionary()
    inner.set_int("Predictor", 2)
    wrapper.set_item("DecodeParms", inner)
    assert resolve_decode_params(wrapper, 0) is inner


def test_none_parameters_returns_empty() -> None:
    assert resolve_decode_params(None, 0).size() == 0


# ---------------------------------------------------------------------------
# Unknown filter name and empty filter list.
# ---------------------------------------------------------------------------


def test_unknown_filter_name_raises_on_decode() -> None:
    """An unregistered /Filter name raises OSError on the decode path
    (upstream throws ``IOException("Invalid filter: ...")``)."""
    stream = COSStream()
    stream.set_item("Filter", _name("BogusDecode"))
    stream.set_raw_data(b"whatever")
    with pytest.raises(OSError, match="Invalid filter"):
        stream.create_input_stream()
    stream.close()


def test_empty_filter_list_passthrough() -> None:
    """No /Filter → decoded bytes equal raw bytes (passthrough)."""
    raw = b"unfiltered body \x00\x01\x02"
    stream = COSStream()
    stream.set_raw_data(raw)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


def test_empty_filter_array_passthrough() -> None:
    """An explicitly empty /Filter array decodes as passthrough."""
    raw = b"still unfiltered"
    stream = COSStream()
    stream.set_item("Filter", COSArray())
    stream.set_raw_data(raw)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


# ---------------------------------------------------------------------------
# RunLength + Flate chain and LZW predictor in a chain.
# ---------------------------------------------------------------------------


def test_runlength_flate_chain_round_trip() -> None:
    raw = b"\x00" * 200 + b"ABCDEF" * 30 + b"\xff" * 100
    chain = [RunLengthDecode(), FlateDecode()]
    body = _encode_reverse(chain, raw)
    stream = _build_stream([_name("RunLengthDecode"), _name("FlateDecode")], body)
    with stream.create_input_stream() as src:
        assert src.read() == raw
    stream.close()


def test_lzw_predictor_array_parms_in_chain() -> None:
    """LZWDecode at index 1 picks up its /DecodeParms predictor entry."""
    raw = bytes(range(8)) * 4
    lzw = LZWDecode()
    lzw_params = COSDictionary()
    lzw_params.set_int("Predictor", 12)
    lzw_params.set_int("Columns", 8)
    lzw_params.set_int("BitsPerComponent", 8)
    lzw_params.set_int("Colors", 1)
    lzw_params.set_int("EarlyChange", 1)
    enc = io.BytesIO()
    lzw.encode(io.BytesIO(raw), enc, lzw_params)

    stream = COSDictionary()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("LZWDecode"))
    stream.set_item("Filter", filt)
    parms = COSArray()
    parms.add(COSNull.NULL)
    parms.add(lzw_params)
    stream.set_item("DecodeParms", parms)
    dec = io.BytesIO()
    lzw.decode(io.BytesIO(enc.getvalue()), dec, stream, 1)
    assert dec.getvalue() == raw


def test_unknown_filter_in_chain_raises() -> None:
    """An unknown filter anywhere in a multi-filter chain raises."""
    stream = COSStream()
    filt = COSArray()
    filt.add(_name("ASCIIHexDecode"))
    filt.add(_name("NopeDecode"))
    stream.set_item("Filter", filt)
    ahx = ASCIIHexDecode()
    buf = io.BytesIO()
    ahx.encode(io.BytesIO(b"payload"), buf, COSDictionary())
    stream.set_raw_data(buf.getvalue())
    with pytest.raises(OSError, match="Invalid filter"):
        stream.create_input_stream()
    stream.close()
