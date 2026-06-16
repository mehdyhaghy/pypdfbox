"""Wave 1368 — COSStream filter chain pipeline + ``/Filter`` shape parity.

Round-out tests for paths not yet covered:

* Filter pipeline round-trip with multiple chains
  (``[Flate, ASCIIHex]``, ``[Flate, ASCII85]``, ``[Flate, LZW]``,
  ``[ASCIIHex, Flate]``).
* ``/Filter`` stored as a single name vs as a one-element ``COSArray``
  (both must decode identically — readers handle either form).
* ``/Filter`` array vs single-name parity for ``get_filter_list``,
  ``has_filter``, ``get_filters_as_strings``.
* ``set_filters`` with an empty list preserves the empty form so producer
  data round-trips faithfully.
* ``has_filter`` true/false and ``has_filters`` distinguishing empty vs
  populated.
* ``get_decode_parms`` falling back to short-form ``/DP``.
* ``set_data`` writing through a filter chain and round-tripping back.
* ``stop_filters`` halting the decode chain before a named filter.
* ``create_view`` decoding through the filter chain.
* ``to_text_string`` returning empty string when the stream body is
  missing.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)

# ---------- filter-chain round-trip combos ----------


def _round_trip_chain(filters: list[str], payload: bytes) -> bytes:
    """Helper: write ``payload`` through ``filters`` and read it back
    using ``create_input_stream`` which decodes the chain.
    """
    stream = COSStream()
    with stream.create_output_stream(filters) as out:
        out.write(payload)
    with stream.create_input_stream() as src:
        return src.read()


def test_filter_chain_flate_then_ascii_hex_round_trips() -> None:
    payload = b"flate then ascii-hex"
    assert _round_trip_chain(["FlateDecode", "ASCIIHexDecode"], payload) == payload


def test_filter_chain_flate_then_ascii85_round_trips() -> None:
    payload = b"flate then ascii-85"
    assert _round_trip_chain(["FlateDecode", "ASCII85Decode"], payload) == payload


def test_filter_chain_flate_then_lzw_round_trips() -> None:
    payload = b"flate then lzw" * 8
    assert _round_trip_chain(["FlateDecode", "LZWDecode"], payload) == payload


def test_filter_chain_ascii_hex_then_flate_round_trips() -> None:
    payload = b"ascii-hex then flate"
    assert _round_trip_chain(["ASCIIHexDecode", "FlateDecode"], payload) == payload


def test_filter_chain_ascii85_then_lzw_round_trips() -> None:
    payload = b"ascii-85 then lzw" * 4
    assert _round_trip_chain(["ASCII85Decode", "LZWDecode"], payload) == payload


# ---------- /Filter shape: single name vs COSArray ----------


def test_filter_stored_as_single_name_decodes() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode"]) as out:
        out.write(b"hi")
    # The writer stores a single filter as a bare name (compact form).
    raw = stream.get_filters()
    assert isinstance(raw, COSName)
    assert stream.get_filter_list() == [COSName.get_pdf_name("FlateDecode")]


def test_filter_stored_as_array_decodes() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode", "ASCIIHexDecode"]) as out:
        out.write(b"chain")
    raw = stream.get_filters()
    assert isinstance(raw, COSArray)
    # Order preserved.
    names = stream.get_filter_list()
    assert names == [
        COSName.get_pdf_name("FlateDecode"),
        COSName.get_pdf_name("ASCIIHexDecode"),
    ]


def test_get_filter_list_accepts_single_name_form_via_manual_set() -> None:
    stream = COSStream()
    # Write raw and manually attach ``/Filter`` as a single name.
    raw_payload_compressed = _encode_with_filter(b"single name", "FlateDecode")
    stream.set_raw_data(raw_payload_compressed)
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("FlateDecode"))
    assert stream.get_filter_list() == [COSName.get_pdf_name("FlateDecode")]
    with stream.create_input_stream() as src:
        assert src.read() == b"single name"


def test_get_filter_list_rejects_non_name_array_entry() -> None:
    # Mirrors upstream getFilterList: a non-name array element throws
    # IOException ("Forbidden type in filter array: ...") -> OSError (wave 1564).
    stream = COSStream()
    bad_array = COSArray([COSName.get_pdf_name("FlateDecode"), COSDictionary()])
    stream.set_item(COSName.FILTER, bad_array)
    with pytest.raises(OSError, match="Forbidden type in filter array"):
        stream.get_filter_list()


def test_get_filter_list_returns_empty_when_absent() -> None:
    stream = COSStream()
    assert stream.get_filter_list() == []
    assert stream.has_filters() is False


def test_has_filter_returns_true_for_matching_chain_entry() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode", "ASCIIHexDecode"]) as out:
        out.write(b"data")
    assert stream.has_filter("FlateDecode") is True
    assert stream.has_filter("LZWDecode") is False


def test_has_filter_string_or_cosname_accepted() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode"]) as out:
        out.write(b"x")
    assert stream.has_filter(COSName.get_pdf_name("FlateDecode")) is True


def test_get_first_filter_returns_first_name_or_none() -> None:
    stream = COSStream()
    assert stream.get_first_filter() is None
    with stream.create_output_stream(["FlateDecode", "ASCII85Decode"]) as out:
        out.write(b"data")
    assert stream.get_first_filter() == COSName.get_pdf_name("FlateDecode")


def test_get_filters_as_strings_returns_plain_names() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode", "ASCII85Decode"]) as out:
        out.write(b"data")
    assert stream.get_filters_as_strings() == ["FlateDecode", "ASCII85Decode"]


def test_set_filters_with_none_clears_entry() -> None:
    stream = COSStream()
    stream.set_filters(["FlateDecode"])
    assert stream.has_filters() is True
    stream.set_filters(None)
    assert stream.has_filters() is False
    assert COSName.FILTER not in stream


def test_set_filters_with_empty_sequence_stores_empty_array() -> None:
    """Empty sequence is stored as an empty COSArray so an explicitly
    set ``/Filter []`` shape can round-trip through the writer rather
    than being silently coerced to absent.
    """
    stream = COSStream()
    stream.set_filters([])
    raw = stream.get_filters()
    assert isinstance(raw, COSArray)
    assert raw.size() == 0


def test_set_filters_with_single_name_stores_bare_name() -> None:
    stream = COSStream()
    stream.set_filters(["FlateDecode"])
    raw = stream.get_filters()
    assert isinstance(raw, COSName)
    assert raw.name == "FlateDecode"


def test_clear_filters_removes_entry() -> None:
    stream = COSStream()
    stream.set_filters(["FlateDecode"])
    stream.clear_filters()
    assert COSName.FILTER not in stream


# ---------- /DecodeParms + /DP fallback ----------


def test_get_decode_parms_falls_back_to_short_form_dp() -> None:
    stream = COSStream()
    parms = COSDictionary([("Columns", COSName.get_pdf_name("X"))])
    stream.set_item(COSName.get_pdf_name("DP"), parms)
    assert stream.get_decode_parms() is parms
    assert stream.has_decode_parms() is True


def test_get_decode_parms_long_form_preferred() -> None:
    stream = COSStream()
    long_form = COSDictionary([("Predictor", COSName.get_pdf_name("X"))])
    short_form = COSDictionary([("Predictor", COSName.get_pdf_name("Y"))])
    stream.set_item(COSName.get_pdf_name("DecodeParms"), long_form)
    stream.set_item(COSName.get_pdf_name("DP"), short_form)
    # PDFBox prefers the long form when both are present.
    assert stream.get_decode_parms() is long_form


def test_clear_decode_parms_removes_both_forms() -> None:
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("DecodeParms"), COSDictionary())
    stream.set_item(COSName.get_pdf_name("DP"), COSDictionary())
    stream.clear_decode_parms()
    assert stream.get_decode_parms() is None


def test_has_decode_parms_false_when_absent() -> None:
    stream = COSStream()
    assert stream.has_decode_parms() is False


# ---------- set_data convenience ----------


def test_set_data_with_filter_chain_round_trips() -> None:
    stream = COSStream()
    payload = b"set_data + filter chain"
    stream.set_data(payload, filters=["FlateDecode"])
    assert stream.to_byte_array() == payload


def test_set_data_with_none_filter_stores_verbatim_bytes() -> None:
    stream = COSStream()
    payload = b"verbatim"
    stream.set_data(payload, filters=None)
    # No /Filter is set; raw and decoded match.
    assert stream.to_byte_array() == payload
    assert stream.to_raw_byte_array() == payload
    assert stream.has_filters() is False


# ---------- stop_filters semantics ----------


def test_stop_filters_short_circuits_decode_chain() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode", "ASCIIHexDecode"]) as out:
        out.write(b"abc")
    # Decoding with stop_filters=ASCIIHexDecode means we get back the
    # bytes still wrapped in the Flate layer (i.e. the LAST step is
    # skipped — chain is [Flate, AHx], so we stop before AHx and never
    # apply the Flate stage either: decoder runs LEFT-to-RIGHT and the
    # first filter is FlateDecode, then ASCIIHexDecode. So stopping on
    # ASCIIHexDecode applies FlateDecode only.)
    with stream.create_input_stream(stop_filters=["ASCIIHexDecode"]) as src:
        partially_decoded = src.read()
    # Bytes should still be ascii-hex-encoded (post-Flate); they should
    # NOT equal the original payload.
    assert partially_decoded != b"abc"
    # And they should decode further as hex.
    assert all(chr(b) in "0123456789ABCDEFabcdef>" for b in partially_decoded)


def test_stop_filters_accepts_alias_codes() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode", "ASCIIHexDecode"]) as out:
        out.write(b"abc")
    # AHx is the alias for ASCIIHexDecode.
    with stream.create_input_stream(stop_filters="AHx") as src:
        assert src.read() != b"abc"


def test_stop_filters_no_op_for_unknown_name() -> None:
    stream = COSStream()
    with stream.create_output_stream(["FlateDecode"]) as out:
        out.write(b"abc")
    with stream.create_input_stream(stop_filters=["NotAFilter"]) as src:
        assert src.read() == b"abc"


# ---------- create_view ----------


def _view_to_bytes(view: object) -> bytes:
    """Drain a ``RandomAccessRead`` into a ``bytes`` payload."""
    view.seek(0)  # type: ignore[attr-defined]
    n = view.length()  # type: ignore[attr-defined]
    buf = bytearray(n)
    view.read_into(buf)  # type: ignore[attr-defined]
    return bytes(buf)


def test_create_view_returns_decoded_random_access_read() -> None:
    stream = COSStream()
    payload = b"create_view payload"
    with stream.create_output_stream(["FlateDecode"]) as out:
        out.write(payload)
    view = stream.create_view()
    assert _view_to_bytes(view) == payload


def test_create_view_without_filter_returns_raw_bytes() -> None:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"raw")
    view = stream.create_view()
    assert _view_to_bytes(view) == b"raw"


def test_create_view_raises_when_no_body() -> None:
    stream = COSStream()
    with pytest.raises(OSError):
        stream.create_view()


# ---------- to_text_string ----------


def test_to_text_string_returns_empty_for_no_body() -> None:
    stream = COSStream()
    assert stream.to_text_string() == ""


def test_to_text_string_decodes_pdfdoc_encoded_body() -> None:
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"hello")
    assert stream.to_text_string() == "hello"


# ---------- helpers ----------


def _encode_with_filter(payload: bytes, filter_name: str) -> bytes:
    """Run ``payload`` through a single filter and return the raw bytes."""
    helper = COSStream()
    with helper.create_output_stream([filter_name]) as out:
        out.write(payload)
    return helper.get_raw_data()
