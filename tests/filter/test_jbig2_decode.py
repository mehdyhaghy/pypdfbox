from __future__ import annotations

import io
from unittest import mock

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.filter import FilterFactory, JBIG2Decode

# ---------- helpers ----------------------------------------------------


def _png_bytes(width: int, height: int, fill: int = 0) -> bytes:
    """Return a 1-bit PNG buffer of the requested dimensions, all-``fill``.

    The JBIG2Decode filter post-processes the decoder's PNG output
    through Pillow, so any 1-bit PNG is a faithful stand-in for a real
    decoded JBIG2 image when we mock the underlying parser.
    """
    img = Image.new("1", (width, height), color=fill)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_globals_stream(payload: bytes) -> COSStream:
    """Build a COSStream whose decoded body is ``payload`` (no /Filter)."""
    s = COSStream()
    s.set_raw_data(payload)
    return s


def _stream_dict_with_globals(globals_stream: COSStream) -> COSDictionary:
    """Build a stream-level dict carrying ``/DecodeParms /JBIG2Globals``."""
    decode_params = COSDictionary()
    decode_params.set_item("JBIG2Globals", globals_stream)
    parent = COSDictionary()
    parent.set_item("DecodeParms", decode_params)
    return parent


# ---------- registration ----------------------------------------------


def test_jbig2_filter_registered_under_long_name_only() -> None:
    assert FilterFactory.is_registered("JBIG2Decode")
    assert isinstance(FilterFactory.get("JBIG2Decode"), JBIG2Decode)
    # ISO 32000-1 §7.4.2 Table 6 defines NO short-name abbreviation
    # for /JBIG2Decode — make sure we haven't invented one.
    with pytest.raises(KeyError):
        FilterFactory.get("JBIG2")


def test_jbig2_globals_class_constant_matches_pdf_spec_key() -> None:
    """Mirrors upstream's ``COSName.JBIG2_GLOBALS`` reference site —
    porters reaching for the constant land on a stable name on the
    filter class."""
    assert JBIG2Decode.JBIG2_GLOBALS == "JBIG2Globals"


# ---------- decode: happy paths via mocked codec ----------------------


def test_jbig2_decode_forwards_encoded_bytes_to_parser() -> None:
    encoded = b"\xfa\xce\x01jbig2-body"
    fake_png = _png_bytes(8, 4, fill=1)

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        out = io.BytesIO()
        result = JBIG2Decode().decode(io.BytesIO(encoded), out)

    parse.assert_called_once_with(encoded)
    # 8x4 packed MSB-first → 1 byte per row * 4 rows = 4 bytes
    assert result.bytes_written == 4
    assert len(out.getvalue()) == 4
    assert result.parameters.get_int("Width") == 8
    assert result.parameters.get_int("Height") == 4
    assert result.parameters.get_int("BitsPerComponent") == 1
    assert result.parameters.get_int("ColorComponents") == 1


def test_jbig2_decode_prepends_globals_from_decode_parms() -> None:
    globals_payload = b"GLOBALS-SEGMENTS"
    encoded = b"PER-IMAGE-SEGMENTS"
    fake_png = _png_bytes(16, 2)

    parent = _stream_dict_with_globals(_make_globals_stream(globals_payload))

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        out = io.BytesIO()
        JBIG2Decode().decode(io.BytesIO(encoded), out, parent)

    # Globals must logically precede the per-image segments per
    # ISO 32000-1 §7.4.7.
    parse.assert_called_once_with(globals_payload + encoded)


def test_jbig2_decode_globals_via_dp_short_key() -> None:
    """``/DP`` is the long-form alias for ``/DecodeParms`` in some
    streams; the resolver must accept both."""
    globals_payload = b"DP-GLOBALS"
    encoded = b"BODY"
    fake_png = _png_bytes(8, 1)

    decode_params = COSDictionary()
    decode_params.set_item("JBIG2Globals", _make_globals_stream(globals_payload))
    parent = COSDictionary()
    parent.set_item("DP", decode_params)

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        JBIG2Decode().decode(io.BytesIO(encoded), io.BytesIO(), parent)

    parse.assert_called_once_with(globals_payload + encoded)


def test_jbig2_decode_decode_parms_array_indexed_by_filter_position() -> None:
    """When a stream chains multiple filters, ``/DecodeParms`` is an
    array parallel to ``/Filter``; the JBIG2 entry sits at our index."""
    globals_payload = b"INDEXED-GLOBALS"
    encoded = b"BODY"
    fake_png = _png_bytes(8, 1)

    other = COSDictionary()  # placeholder for some preceding filter
    jbig2_params = COSDictionary()
    jbig2_params.set_item("JBIG2Globals", _make_globals_stream(globals_payload))

    arr = COSArray()
    arr.add(other)
    arr.add(jbig2_params)

    parent = COSDictionary()
    parent.set_item("DecodeParms", arr)

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        JBIG2Decode().decode(io.BytesIO(encoded), io.BytesIO(), parent, index=1)

    parse.assert_called_once_with(globals_payload + encoded)


def test_jbig2_decode_no_globals_passes_encoded_bytes_unchanged() -> None:
    encoded = b"NO-GLOBALS-BODY"
    fake_png = _png_bytes(8, 1)

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        JBIG2Decode().decode(io.BytesIO(encoded), io.BytesIO(), COSDictionary())

    parse.assert_called_once_with(encoded)


def test_jbig2_decode_decode_params_dict_passed_directly() -> None:
    """Hand-written tests often pass the decode-params dict in directly
    (not nested under /DecodeParms). The resolver falls back to using
    it as-is."""
    globals_payload = b"DIRECT-GLOBALS"
    encoded = b"BODY"
    fake_png = _png_bytes(8, 1)

    direct_params = COSDictionary()
    direct_params.set_item("JBIG2Globals", _make_globals_stream(globals_payload))

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        JBIG2Decode().decode(io.BytesIO(encoded), io.BytesIO(), direct_params)

    parse.assert_called_once_with(globals_payload + encoded)


def test_jbig2_decode_globals_decoded_through_filter_chain() -> None:
    """The /JBIG2Globals stream may itself carry a /Filter (commonly
    /FlateDecode). ``COSStream.to_byte_array()`` runs that chain so the
    JBIG2 codec sees raw global segments."""
    raw_globals = b"FLATE-GLOBAL-SEGMENTS"
    s = COSStream()
    # Encode through /FlateDecode — to_byte_array() will undo it.
    s.set_data(raw_globals, filters=COSName.get_pdf_name("FlateDecode"))

    encoded = b"BODY"
    fake_png = _png_bytes(8, 1)

    parent = _stream_dict_with_globals(s)

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        JBIG2Decode().decode(io.BytesIO(encoded), io.BytesIO(), parent)

    parse.assert_called_once_with(raw_globals + encoded)


# ---------- decode: edge cases ----------------------------------------


def test_jbig2_decode_empty_input_returns_no_bytes() -> None:
    out = io.BytesIO()
    result = JBIG2Decode().decode(io.BytesIO(b""), out)
    assert result.bytes_written == 0
    assert out.getvalue() == b""


def test_jbig2_decode_invalid_input_raises_oserror() -> None:
    # Real call into jbig2_parser — bogus bytes raise RuntimeError
    # which the filter wraps in OSError per the Filter contract.
    with pytest.raises(OSError, match="jbig2_parser decode failed"):
        JBIG2Decode().decode(io.BytesIO(b"not a jbig2 stream"), io.BytesIO())


def test_jbig2_decode_non_stream_globals_value_is_ignored() -> None:
    """Spec mandates a stream for /JBIG2Globals. Defensive code path:
    a malformed dict-typed value must not crash the decode."""
    encoded = b"BODY"
    fake_png = _png_bytes(8, 1)

    decode_params = COSDictionary()
    decode_params.set_item("JBIG2Globals", COSDictionary())  # wrong type
    parent = COSDictionary()
    parent.set_item("DecodeParms", decode_params)

    with mock.patch(
        "jbig2_parser.parse_jbig2", return_value=fake_png
    ) as parse:
        JBIG2Decode().decode(io.BytesIO(encoded), io.BytesIO(), parent)

    # No prepended globals — the bad value was silently dropped.
    parse.assert_called_once_with(encoded)


def test_jbig2_decode_surfaces_geometry_for_larger_page() -> None:
    """Confirm the surfaced /Width and /Height come from the decoded
    image, not from any caller-provided defaults."""
    fake_png = _png_bytes(64, 32)

    with mock.patch("jbig2_parser.parse_jbig2", return_value=fake_png):
        out = io.BytesIO()
        result = JBIG2Decode().decode(io.BytesIO(b"x"), out)

    assert result.parameters.get_int("Width") == 64
    assert result.parameters.get_int("Height") == 32
    # 64 cols / 8 = 8 bytes per row, 32 rows → 256 bytes
    assert result.bytes_written == 256


# ---------- encode -----------------------------------------------------


def test_jbig2_encode_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="decode-only"):
        JBIG2Decode().encode(io.BytesIO(b""), io.BytesIO(), COSDictionary())
