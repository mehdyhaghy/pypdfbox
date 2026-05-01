from __future__ import annotations

import io
import zlib

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.common import PDStream


def test_wraps_existing_cos_stream_and_returns_cos_object() -> None:
    cos_stream = COSStream()
    stream = PDStream(cos_stream)
    assert stream.get_cos_object() is cos_stream


def test_embeds_bytes_and_reports_current_body_length() -> None:
    stream = PDStream(input_data=b"abc123")
    assert stream.get_length() == 6
    assert stream.to_byte_array() == b"abc123"


def test_embeds_binary_stream_and_closes_input_quietly() -> None:
    source = io.BytesIO(b"payload")
    stream = PDStream(None, source)
    assert source.closed
    assert stream.create_raw_input_stream().read() == b"payload"


def test_set_filters_normalizes_single_name_to_array() -> None:
    stream = PDStream(input_data=b"abc")
    stream.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    raw_filter = stream.get_cos_object().get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
    assert isinstance(raw_filter, COSArray)
    assert stream.get_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]


def test_create_input_stream_decodes_registered_filters() -> None:
    encoded = zlib.compress(b"decoded")
    stream = PDStream(input_data=encoded, filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.create_input_stream().read() == b"decoded"


def test_create_input_stream_stops_before_stop_filter() -> None:
    encoded = zlib.compress(b"decoded")
    stream = PDStream(input_data=encoded, filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.create_input_stream(["FlateDecode"]).read() == encoded


def test_decoded_stream_length_round_trip() -> None:
    stream = PDStream(input_data=b"abc")
    assert stream.get_decoded_stream_length() == -1
    stream.set_decoded_stream_length(12)
    assert stream.get_decoded_stream_length() == 12


def test_create_output_stream_with_filter_encodes_on_close() -> None:
    stream = PDStream()
    with stream.create_output_stream(COSName.FLATE_DECODE) as out:  # type: ignore[attr-defined]
        out.write(b"compress me")
    # /Filter is now set, raw bytes are compressed, decoded matches.
    assert stream.get_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]
    assert stream.to_byte_array() == b"compress me"
    assert stream.create_raw_input_stream().read() != b"compress me"


def test_create_output_stream_with_chain_encodes_in_reverse() -> None:
    stream = PDStream()
    with stream.create_output_stream(["ASCII85Decode", "FlateDecode"]) as out:
        out.write(b"chained payload")
    assert [n.name for n in stream.get_filters()] == ["ASCII85Decode", "FlateDecode"]
    assert stream.to_byte_array() == b"chained payload"


def test_to_byte_array_on_empty_stream_returns_empty_bytes() -> None:
    stream = PDStream()
    assert stream.to_byte_array() == b""


def test_create_input_stream_on_empty_stream_returns_empty_bytes_io() -> None:
    stream = PDStream()
    assert stream.create_input_stream().read() == b""


def test_get_decode_parms_absent_returns_none() -> None:
    stream = PDStream(input_data=b"x")
    assert stream.get_decode_parms() is None


def test_set_and_get_decode_parms_single_dict() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    parms = COSDictionary()
    parms.set_int("Predictor", 12)
    stream.set_decode_parms(parms)

    out = stream.get_decode_parms()
    assert out is not None
    assert len(out) == 1
    assert out[0].get_int("Predictor") == 12


def test_set_and_get_decode_parms_chain() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    p1 = COSDictionary()
    p1.set_int("Predictor", 1)
    p2 = COSDictionary()
    p2.set_int("Predictor", 12)
    stream.set_decode_parms([p1, p2])

    out = stream.get_decode_parms()
    assert out is not None
    assert [d.get_int("Predictor") for d in out] == [1, 12]


def test_set_decode_parms_none_removes_entry() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    stream.set_decode_parms(COSDictionary())
    assert stream.get_decode_parms() is not None
    stream.set_decode_parms(None)
    assert stream.get_decode_parms() is None


def test_get_decode_parms_falls_back_to_dp() -> None:
    """Per PDF Reference 1.5 implementation note 7, some producers spell
    the entry ``/DP`` rather than ``/DecodeParms``. ``get_decode_parms``
    should fall back to ``/DP`` when the canonical key is absent."""
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    dp = COSDictionary()
    dp.set_int("Predictor", 15)
    # Stash directly under /DP — bypasses set_decode_parms which uses
    # the canonical /DecodeParms key.
    stream.get_cos_object().set_item(COSName.get_pdf_name("DP"), dp)

    out = stream.get_decode_parms()
    assert out is not None
    assert len(out) == 1
    assert out[0].get_int("Predictor") == 15


def test_get_decode_parms_prefers_decodeparms_over_dp() -> None:
    """When both ``/DecodeParms`` and ``/DP`` are present, the canonical
    ``/DecodeParms`` key wins."""
    from pypdfbox.cos import COSDictionary

    stream = PDStream(input_data=b"x")
    canonical = COSDictionary()
    canonical.set_int("Predictor", 12)
    stream.set_decode_parms(canonical)

    legacy = COSDictionary()
    legacy.set_int("Predictor", 99)
    stream.get_cos_object().set_item(COSName.get_pdf_name("DP"), legacy)

    out = stream.get_decode_parms()
    assert out is not None
    assert out[0].get_int("Predictor") == 12


def test_get_metadata_absent_returns_none() -> None:
    stream = PDStream()
    assert stream.get_metadata() is None


def test_set_and_get_metadata_round_trip() -> None:
    stream = PDStream()
    meta = COSStream()
    meta.set_raw_data(b"<x:xmpmeta/>")
    stream.set_metadata(meta)
    assert stream.get_metadata() is meta


def test_set_metadata_none_removes_entry() -> None:
    stream = PDStream()
    stream.set_metadata(COSStream())
    assert stream.get_metadata() is not None
    stream.set_metadata(None)
    assert stream.get_metadata() is None


def test_get_length_absent_with_no_data_returns_none() -> None:
    stream = PDStream()
    assert stream.get_length() is None


def test_to_byte_array_delegates_to_cos_stream() -> None:
    payload = b"delegated"
    stream = PDStream(input_data=zlib.compress(payload), filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.to_byte_array() == payload


# ---------- /FFilter setter ----------


def test_set_file_filters_single_name_writes_one_element_array() -> None:
    stream = PDStream()
    stream.set_file_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    raw = stream.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FFilter"))
    assert isinstance(raw, COSArray)
    assert stream.get_file_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]


def test_set_file_filters_chain_round_trips() -> None:
    stream = PDStream()
    stream.set_file_filters(["ASCII85Decode", "FlateDecode"])
    assert [n.name for n in stream.get_file_filters()] == [
        "ASCII85Decode",
        "FlateDecode",
    ]


def test_set_file_filters_none_removes_entry() -> None:
    stream = PDStream()
    stream.set_file_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    assert stream.get_file_filters() != []
    stream.set_file_filters(None)
    assert stream.get_file_filters() == []


# ---------- /FDecodeParms setter ----------


def test_set_file_decode_parms_single_dict_round_trips() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream()
    parms = COSDictionary()
    parms.set_int("Predictor", 12)
    stream.set_file_decode_parms(parms)

    out = stream.get_file_decode_parms()
    assert out is not None
    assert len(out) == 1
    assert out[0].get_int("Predictor") == 12


def test_set_file_decode_parms_chain_round_trips() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream()
    p1 = COSDictionary()
    p1.set_int("Predictor", 1)
    p2 = COSDictionary()
    p2.set_int("Predictor", 12)
    stream.set_file_decode_parms([p1, p2])

    out = stream.get_file_decode_parms()
    assert out is not None
    assert [d.get_int("Predictor") for d in out] == [1, 12]


def test_set_file_decode_parms_none_removes_entry() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream()
    stream.set_file_decode_parms(COSDictionary())
    assert stream.get_file_decode_parms() is not None
    stream.set_file_decode_parms(None)
    assert stream.get_file_decode_parms() is None


# ---------- set_metadata accepts PDMetadata ----------


def test_set_metadata_accepts_pd_metadata_wrapper() -> None:
    from pypdfbox.pdmodel.common.pd_metadata import PDMetadata

    stream = PDStream()
    meta = PDMetadata(b"<x:xmpmeta/>")
    stream.set_metadata(meta)
    # Underlying COSStream identity preserved.
    assert stream.get_metadata() is meta.get_cos_object()


# ---------- constructors ----------


def test_constructor_with_pd_document_uses_scratch_file() -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    doc = PDDocument()
    stream = PDStream(doc)
    assert isinstance(stream.get_cos_object(), COSStream)
    assert stream.get_length() is None  # no body, no /Length


def test_constructor_with_pd_document_and_input_data_embeds_bytes() -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    doc = PDDocument()
    stream = PDStream(doc, b"hello", filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    # Embed stores the bytes verbatim and records /Filter.
    assert stream.create_raw_input_stream().read() == b"hello"
    assert stream.get_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]


def test_constructor_with_pd_document_and_filter_array() -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    doc = PDDocument()
    chain = COSArray(
        [
            COSName.ASCII85_DECODE,  # type: ignore[attr-defined]
            COSName.FLATE_DECODE,  # type: ignore[attr-defined]
        ]
    )
    stream = PDStream(doc, b"raw", filters=chain)
    # /Filter is set to the array as-is.
    raw = stream.get_cos_object().get_dictionary_object(COSName.FILTER)  # type: ignore[attr-defined]
    assert isinstance(raw, COSArray)
    assert [n.name for n in stream.get_filters()] == ["ASCII85Decode", "FlateDecode"]


def test_constructor_rejects_cos_stream_with_input_data() -> None:
    import pytest

    cs = COSStream()
    with pytest.raises(TypeError):
        PDStream(cs, b"oops")


# ---------- file decode params: upstream Java naming parity ----------


def test_get_file_decode_params_matches_get_file_decode_parms() -> None:
    """``get_file_decode_params`` mirrors upstream Java's
    ``getFileDecodeParams`` spelling and returns the same list as our
    earlier-named ``get_file_decode_parms``."""
    from pypdfbox.cos import COSDictionary

    stream = PDStream()
    p1 = COSDictionary()
    p1.set_int("Predictor", 12)
    stream.set_file_decode_parms([p1])

    out_legacy = stream.get_file_decode_parms()
    out_upstream_named = stream.get_file_decode_params()
    assert out_upstream_named == out_legacy
    assert out_upstream_named is not None
    assert out_upstream_named[0].get_int("Predictor") == 12


def test_set_file_decode_params_writes_through_to_dictionary() -> None:
    """``set_file_decode_params`` mirrors upstream's ``setFileDecodeParams``
    spelling and round-trips through both accessor names."""
    from pypdfbox.cos import COSDictionary

    stream = PDStream()
    p1 = COSDictionary()
    p1.set_int("Predictor", 1)
    p2 = COSDictionary()
    p2.set_int("Predictor", 12)
    stream.set_file_decode_params([p1, p2])

    # Both accessors return the same data.
    legacy = stream.get_file_decode_parms()
    upstream_named = stream.get_file_decode_params()
    assert legacy is not None
    assert upstream_named is not None
    assert [d.get_int("Predictor") for d in upstream_named] == [1, 12]
    assert [d.get_int("Predictor") for d in legacy] == [1, 12]


def test_set_file_decode_params_none_removes_entry() -> None:
    from pypdfbox.cos import COSDictionary

    stream = PDStream()
    stream.set_file_decode_params(COSDictionary())
    assert stream.get_file_decode_params() is not None
    stream.set_file_decode_params(None)
    assert stream.get_file_decode_params() is None
    assert stream.get_file_decode_parms() is None
