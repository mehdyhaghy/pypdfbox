"""Fuzz / parity hammering for ``PDStream`` + ``COSStream`` stream I/O.

Wave 1584 (agent E). Exercises the high-level ``PDStream`` wrapper and the
``COSStream`` create_input_stream / create_output_stream / create_raw_input_stream
filter end-to-end against the documented PDFBox 3.0.7 contract:

* uncompressed embed + decoded/raw round-trip,
* single-filter and 2-filter encode-on-write chains that round-trip through
  ``create_input_stream``,
* ``get_filters`` normalization (absent → ``[]``, single ``COSName`` → one
  element, ``COSArray`` → its entries, malformed scalar → ``[]``),
* ``set_filters`` (``None`` removes; single / iterable both stored as array),
* ``create_raw_input_stream`` returning the still-encoded bytes,
* ``create_input_stream(stop_filters)`` halting decode partway (exclusive of
  the stop filter),
* ``/Length`` reflecting the *encoded* (raw) body, ``/DL`` decode-length hint,
* empty-stream behavior,
* the encode-on-write constructor (``PDStream(doc, bytes, filters)``).

No single upstream JUnit class covers ``PDStream``/``COSStream`` directly
(PROVENANCE notes this); these are hand-written parity pins mirroring the
upstream method semantics described in ``PDStream.java`` / ``COSStream.java``.
"""

from __future__ import annotations

import io
import zlib

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.pd_document import PDDocument

_FILTER = COSName.FILTER  # type: ignore[attr-defined]
_LENGTH = COSName.LENGTH  # type: ignore[attr-defined]
_FLATE = COSName.FLATE_DECODE  # type: ignore[attr-defined]
_A85 = COSName.ASCII85_DECODE  # type: ignore[attr-defined]


# --- payload corpus -------------------------------------------------------

_PAYLOADS: list[bytes] = [
    b"",
    b"a",
    b"hello world",
    b"\x00\x01\x02\x03\x04\xfe\xff",
    b"A" * 100,
    b"the quick brown fox " * 50,
    bytes(range(256)),
    b"\n\r\t mixed whitespace \r\n",
    b"%PDF-1.7 fake header tail",
    bytes([i % 7 for i in range(1000)]),
]

_PAYLOAD_IDS = [
    "empty",
    "one",
    "hello",
    "binary7",
    "100A",
    "repeated",
    "all256",
    "whitespace",
    "pdfish",
    "modular1k",
]


# --- uncompressed embed / round-trip --------------------------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_uncompressed_round_trip(payload: bytes) -> None:
    """No filter: decoded == raw == the bytes written; ``/Filter`` absent."""
    s = PDStream()
    with s.create_output_stream() as out:
        out.write(payload)
    assert s.create_input_stream().read() == payload
    if payload:
        assert s.create_raw_input_stream().read() == payload
    assert s.get_filters() == []
    assert s.is_filter_undefined() is True


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_uncompressed_length_matches_body(payload: bytes) -> None:
    """``/Length`` reflects the raw body byte count after an unencoded write."""
    s = PDStream()
    with s.create_output_stream() as out:
        out.write(payload)
    assert s.get_length() == len(payload)
    assert s.get_filtered_stream_length() == len(payload)


# --- single-filter encode-on-write round-trip -----------------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_flate_round_trip(payload: bytes) -> None:
    """FlateDecode: write decoded bytes, read them back through the filter."""
    s = PDStream()
    with s.create_output_stream(_FLATE) as out:
        out.write(payload)
    assert s.create_input_stream().read() == payload
    # /Filter recorded; get_filters normalizes the bare single name.
    assert [f.name for f in s.get_filters()] == ["FlateDecode"]
    assert s.has_filter("FlateDecode") is True
    assert s.is_filter_undefined() is False


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_flate_raw_is_encoded(payload: bytes) -> None:
    """The raw stream returns the *encoded* (deflated) bytes — and
    re-inflating them with stdlib zlib recovers the payload (byte-parity
    with the upstream Deflater on these payloads)."""
    s = PDStream()
    with s.create_output_stream(_FLATE) as out:
        out.write(payload)
    raw = s.create_raw_input_stream().read()
    assert zlib.decompress(raw) == payload
    assert s.get_length() == len(raw)


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_ascii85_round_trip(payload: bytes) -> None:
    s = PDStream()
    with s.create_output_stream(_A85) as out:
        out.write(payload)
    assert s.create_input_stream().read() == payload
    assert [f.name for f in s.get_filters()] == ["ASCII85Decode"]


# --- 2-filter chain decodes fully -----------------------------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_two_filter_chain_full_decode(payload: bytes) -> None:
    """``/Filter [ASCII85Decode FlateDecode]`` round-trips fully."""
    s = PDStream()
    with s.create_output_stream([_A85, _FLATE]) as out:
        out.write(payload)
    assert s.create_input_stream().read() == payload
    assert [f.name for f in s.get_filters()] == ["ASCII85Decode", "FlateDecode"]


# --- stop_filters halts decode partway ------------------------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_stop_before_second_filter(payload: bytes) -> None:
    """stop_filters=[second] returns the partially-decoded bytes (the first
    filter applied, the second left encoded). Exclusive of the stop filter:
    stopping before FlateDecode yields the A85-decoded-but-still-flated
    bytes, which re-inflate to the payload."""
    s = PDStream()
    with s.create_output_stream([_A85, _FLATE]) as out:
        out.write(payload)
    partial = s.create_input_stream(["FlateDecode"]).read()
    # First filter (ASCII85) applied; FlateDecode not yet → still deflated.
    assert zlib.decompress(partial) == payload


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_stop_before_first_filter_is_raw(payload: bytes) -> None:
    """stop_filters naming the *first* filter halts immediately → raw bytes."""
    s = PDStream()
    with s.create_output_stream([_A85, _FLATE]) as out:
        out.write(payload)
    # Even an empty decoded payload produces a non-empty *encoded* body
    # (the A85-of-deflate-of-empty), so the stream always has raw data here.
    raw = s.create_raw_input_stream().read()
    assert s.create_input_stream(["ASCII85Decode"]).read() == raw


def test_stop_filters_single_string_and_name() -> None:
    """stop_filters accepts a bare ``str`` or ``COSName`` as well as a list."""
    s = PDStream()
    with s.create_output_stream([_A85, _FLATE]) as out:
        out.write(b"payload bytes" * 8)
    by_list = s.create_input_stream(["FlateDecode"]).read()
    by_str = s.create_input_stream("FlateDecode").read()
    by_name = s.create_input_stream(_FLATE).read()
    assert by_str == by_list == by_name


def test_stop_filters_none_decodes_fully() -> None:
    s = PDStream()
    with s.create_output_stream([_A85, _FLATE]) as out:
        out.write(b"full decode" * 10)
    assert s.create_input_stream(None).read() == b"full decode" * 10
    assert s.create_input_stream().read() == b"full decode" * 10


def test_stop_filter_not_in_chain_decodes_fully() -> None:
    """A stop name that never appears in the chain leaves decode complete."""
    s = PDStream()
    with s.create_output_stream(_FLATE) as out:
        out.write(b"unaffected" * 12)
    assert s.create_input_stream(["DCTDecode"]).read() == b"unaffected" * 12


# --- get_filters normalization (single / array / absent / malformed) -------


def test_get_filters_absent_is_empty() -> None:
    s = PDStream()
    assert s.get_filters() == []
    assert s.get_first_filter() is None
    assert s.get_filters_as_strings() == []


def test_get_filters_single_name() -> None:
    s = PDStream()
    s.get_cos_object().set_item(_FILTER, _FLATE)
    assert s.get_filters() == [_FLATE]
    assert s.get_first_filter() == _FLATE
    assert s.get_filters_as_strings() == ["FlateDecode"]


def test_get_filters_array() -> None:
    s = PDStream()
    s.get_cos_object().set_item(_FILTER, COSArray([_A85, _FLATE]))
    assert s.get_filters() == [_A85, _FLATE]
    assert s.get_filters_as_strings() == ["ASCII85Decode", "FlateDecode"]


def test_get_filters_malformed_scalar_is_empty() -> None:
    """A ``/Filter`` value that is neither name nor array → empty list
    (lenient, matches upstream's fall-through)."""
    s = PDStream()
    s.get_cos_object().set_item(_FILTER, COSString(b"not a filter"))
    assert s.get_filters() == []


def test_get_filters_array_preserves_malformed_entry() -> None:
    """``COSArray.to_list()`` returns raw entries verbatim (no validation),
    mirroring upstream ``getFilters()`` leniency."""
    s = PDStream()
    s.get_cos_object().set_item(_FILTER, COSArray([_FLATE, COSInteger.get(9)]))
    filters = s.get_filters()
    assert filters[0] == _FLATE
    assert isinstance(filters[1], COSInteger)


# --- set_filters -----------------------------------------------------------


def test_set_filters_single_stored_as_array() -> None:
    """Upstream ``setFilters(List)`` always wraps in a ``COSArray`` even for
    a single name."""
    s = PDStream()
    s.set_filters("FlateDecode")
    assert isinstance(s.get_cos_object().get_filters(), COSArray)
    assert s.get_filters_as_strings() == ["FlateDecode"]


def test_set_filters_iterable() -> None:
    s = PDStream()
    s.set_filters([_A85, "FlateDecode"])
    assert s.get_filters_as_strings() == ["ASCII85Decode", "FlateDecode"]


def test_set_filters_none_removes() -> None:
    s = PDStream()
    s.set_filters(_FLATE)
    s.set_filters(None)
    assert s.is_filter_undefined() is True
    assert s.get_filters() == []


def test_set_filters_cosname() -> None:
    s = PDStream()
    s.set_filters(_FLATE)
    assert s.has_filter(_FLATE) is True


# --- /Length and /DL -------------------------------------------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_length_reflects_encoded_body(payload: bytes) -> None:
    """``get_length`` is the *encoded* (raw) byte count, not the decoded."""
    s = PDStream()
    with s.create_output_stream(_FLATE) as out:
        out.write(payload)
    raw_len = len(s.create_raw_input_stream().read())
    assert s.get_length() == raw_len


def test_empty_stream_length_is_none() -> None:
    s = PDStream()
    assert s.get_length() is None
    assert s.get_filtered_stream_length() == -1


def test_decoded_stream_length_dl() -> None:
    s = PDStream()
    assert s.get_decoded_stream_length() == -1
    s.set_decoded_stream_length(4242)
    assert s.get_decoded_stream_length() == 4242


def test_set_length_writes_dict_entry() -> None:
    s = PDStream()
    with s.create_output_stream() as out:
        out.write(b"abc")
    s.set_length(999)
    assert s.get_cos_object().get_int(_LENGTH, -1) == 999


# --- raw vs decoded distinction --------------------------------------------


def test_raw_differs_from_decoded_when_compressed() -> None:
    s = PDStream()
    with s.create_output_stream(_FLATE) as out:
        out.write(b"X" * 400)
    raw = s.create_raw_input_stream().read()
    decoded = s.create_input_stream().read()
    assert raw != decoded
    assert len(raw) < len(decoded)
    assert decoded == b"X" * 400


def test_to_byte_array_and_copy_helpers() -> None:
    s = PDStream()
    with s.create_output_stream(_FLATE) as out:
        out.write(b"copy me" * 30)
    assert s.to_byte_array() == b"copy me" * 30
    assert s.get_byte_array() == b"copy me" * 30
    sink = io.BytesIO()
    assert s.copy_to(sink) == len(b"copy me" * 30)
    assert sink.getvalue() == b"copy me" * 30
    raw_sink = io.BytesIO()
    assert s.copy_raw_to(raw_sink) == s.get_length()


# --- empty stream behavior -------------------------------------------------


def test_empty_stream_decoded_is_empty_bytesio() -> None:
    """PDStream over a fresh COSStream returns an empty stream rather than
    raising (documented divergence from ``COSStream.create_input_stream``)."""
    s = PDStream()
    assert s.create_input_stream().read() == b""
    assert s.to_byte_array() == b""
    assert s.is_empty() is True


def test_empty_stream_raw_raises() -> None:
    """The wrapped COSStream still raises on a raw read with no body."""
    s = PDStream()
    with pytest.raises(OSError):
        s.create_raw_input_stream()


def test_empty_stream_copy_helpers_noop() -> None:
    s = PDStream()
    assert s.copy_to(io.BytesIO()) == 0
    assert s.copy_raw_to(io.BytesIO()) == 0


# --- encode-on-write constructor ------------------------------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_ctor_embeds_uncompressed(payload: bytes) -> None:
    doc = PDDocument()
    try:
        s = PDStream(doc, payload, None)
        assert s.create_input_stream().read() == payload
        assert s.get_filters() == []
    finally:
        doc.close()


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_ctor_embeds_with_flate(payload: bytes) -> None:
    doc = PDDocument()
    try:
        s = PDStream(doc, payload, _FLATE)
        # Stored compressed; round-trips back to the decoded payload.
        assert s.create_input_stream().read() == payload
        assert [f.name for f in s.get_filters()] == ["FlateDecode"]
        assert s.get_length() == len(s.create_raw_input_stream().read())
    finally:
        doc.close()


def test_ctor_from_binary_io() -> None:
    doc = PDDocument()
    try:
        s = PDStream(doc, io.BytesIO(b"stream input bytes"), None)
        assert s.create_input_stream().read() == b"stream input bytes"
    finally:
        doc.close()


def test_ctor_wrap_existing_cos_stream() -> None:
    cos = COSStream()
    with cos.create_output_stream() as out:
        out.write(b"wrapped")
    s = PDStream(cos)
    assert s.get_cos_object() is cos
    assert s.create_input_stream().read() == b"wrapped"


def test_ctor_rejects_cos_stream_with_input() -> None:
    cos = COSStream()
    with pytest.raises(TypeError):
        PDStream(cos, b"oops")


# --- COSStream-level parity (the engine under PDStream) --------------------


@pytest.mark.parametrize("payload", _PAYLOADS, ids=_PAYLOAD_IDS)
def test_cos_stream_create_view_round_trip(payload: bytes) -> None:
    cos = COSStream()
    with cos.create_output_stream(_FLATE) as out:
        out.write(payload)
    if payload:
        view = cos.create_view()
        assert view.length() == len(payload)


def test_cos_stream_set_data_with_filter() -> None:
    cos = COSStream()
    cos.set_data(b"data via set_data" * 5, _FLATE)
    assert cos.to_byte_array() == b"data via set_data" * 5
    assert cos.get_filters_as_strings() == ["FlateDecode"]


def test_cos_stream_set_data_no_filter_clears_existing() -> None:
    cos = COSStream()
    cos.set_data(b"first", _FLATE)
    cos.set_data(b"second", None)
    assert cos.to_byte_array() == b"second"
    assert cos.get_filters_as_strings() == []


def test_cos_stream_forbidden_filter_array_raises() -> None:
    cos = COSStream()
    cos.set_item(_FILTER, COSArray([_FLATE, COSInteger.get(3)]))
    with pytest.raises(OSError):
        cos.get_filter_list()


def test_cos_stream_unregistered_filter_raises_oserror() -> None:
    cos = COSStream()
    with cos.create_output_stream() as out:
        out.write(b"bytes")
    cos.set_item(_FILTER, COSName.get_pdf_name("NoSuchFilter"))
    with pytest.raises(OSError):
        cos.create_input_stream().read()


def test_cos_stream_writing_guard() -> None:
    """A second writer cannot be opened while one is live."""
    cos = COSStream()
    out = cos.create_output_stream()
    try:
        with pytest.raises(RuntimeError):
            cos.create_output_stream()
        with pytest.raises(RuntimeError):
            cos.create_input_stream()
    finally:
        out.close()


def test_cos_stream_abbreviated_filter_decodes() -> None:
    """Abbreviated ``Fl`` resolves to FlateDecode for decoding."""
    cos = COSStream()
    with cos.create_output_stream(COSName.get_pdf_name("Fl")) as out:
        out.write(b"Z" * 64)
    assert cos.create_input_stream().read() == b"Z" * 64


def test_cos_stream_duplicate_filter_deduped() -> None:
    """``[Fl, FlateDecode]`` collapses to a single decode (canonical dedup)."""
    cos = COSStream()
    with cos.create_output_stream(_FLATE) as out:
        out.write(b"Q" * 80)
    cos.set_item(_FILTER, COSArray([COSName.get_pdf_name("Fl"), _FLATE]))
    assert cos.create_input_stream().read() == b"Q" * 80
