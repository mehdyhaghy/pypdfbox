"""PDFBox 3.0.9 filter forward-ports (wave 1615).

PDFBOX-6330: ASCII85 skips every PDF white-space byte; ASCIIHex skips
whitespace between the two nibbles of a pair.
PDFBOX-6317: an ASCII85 stream missing its ``~>`` ends the last group at EOF.
PDFBOX-6304: a predictor with a zero row length is rejected (no hang).
"""

import io
import zlib

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCII85Decode, ASCIIHexDecode, FlateDecode, LZWDecode
from pypdfbox.filter.ascii85_input_stream import ASCII85InputStream
from pypdfbox.filter.predictor_output_stream import PredictorOutputStream

_HELLO = b"BT /F1 24 Tf 72 700 Td (Hello PDFBox) Tj ET\n"


def _a85_filter(data: bytes) -> bytes:
    out = io.BytesIO()
    ASCII85Decode().decode(io.BytesIO(data), out, COSDictionary(), 0)
    return out.getvalue()


def _a85_stream(data: bytes) -> bytes:
    return ASCII85InputStream(io.BytesIO(data)).read()


def _hex(data: bytes) -> bytes:
    out = io.BytesIO()
    ASCIIHexDecode().decode(io.BytesIO(data), out, COSDictionary(), 0)
    return out.getvalue()


@pytest.mark.parametrize("decode", [_a85_filter, _a85_stream], ids=["filter", "stream"])
@pytest.mark.parametrize(
    "ws", [b"\x00", b"\t", b"\n", b"\x0c", b"\r", b" "], ids=["nul", "ht", "lf", "ff", "cr", "sp"]
)
def test_ascii85_skips_every_pdf_whitespace(decode, ws: bytes) -> None:
    assert decode(b"87cURD" + ws + b']i,"Ebo80' + ws + b"~>") == b"Hello World!"


@pytest.mark.parametrize("decode", [_a85_filter, _a85_stream], ids=["filter", "stream"])
def test_ascii85_vertical_tab_is_not_whitespace(decode) -> None:
    with pytest.raises(OSError, match="Invalid data"):
        decode(b"87cURD\x0b]i~>")


@pytest.mark.parametrize("decode", [_a85_filter, _a85_stream], ids=["filter", "stream"])
def test_ascii85_upstream_tab_separated_sample(decode) -> None:
    s = b"6<#'\\7PQ#@\t1a#b0+?)%u\t2_Zp.<+I+\"\t87cURD]hkE\t7RD$<.3MT)\t+@T6:~>"
    assert decode(s) == _HELLO


@pytest.mark.parametrize("decode", [_a85_filter, _a85_stream], ids=["filter", "stream"])
@pytest.mark.parametrize(
    "body",
    [b'87cURD]i,"Ebo80', b"87cURD]i", b"87cURD", b"z", b"zz87cURD"],
    ids=["full", "partial", "partial2", "z", "z_then_partial"],
)
def test_ascii85_missing_eod_matches_eod(decode, body: bytes) -> None:
    # The last group is not repeated or dropped when ``~>`` is missing.
    assert decode(body) == decode(body + b"~>")
    assert decode(body + b" \n") == decode(body + b"~>")


def test_ascii85_input_stream_stops_at_first_tilde() -> None:
    assert _a85_stream(b"87cURD~X") == _a85_filter(b"87cURD~X")
    assert _a85_stream(b"<~87cURD~>") == b""


def test_ascii85_input_stream_large_input_without_eod() -> None:
    payload = bytes(range(256)) * 40
    sink = io.BytesIO()
    ASCII85Decode().encode(io.BytesIO(payload), sink, COSDictionary())
    encoded = sink.getvalue().replace(b"~>", b"")
    assert _a85_stream(encoded) == payload


def test_ascii_hex_upstream_sample_with_newline_inside_pair() -> None:
    s = (
        b"4254202F46312032342054662037322\n"
        b"0373030205464202848656C6C6F2050\n"
        b"4446426F782920546A2045540A>"
    )
    assert _hex(s) == _HELLO


@pytest.mark.parametrize(
    "ws", [b"\x00", b"\t", b"\n", b"\x0c", b"\r", b" "], ids=["nul", "ht", "lf", "ff", "cr", "sp"]
)
def test_ascii_hex_whitespace_between_nibbles(ws: bytes) -> None:
    assert _hex(b"4" + ws + ws + b"1" + ws + b"4" + ws + b"2>") == b"AB"


def test_ascii_hex_whitespace_then_eod_or_eof_pads_low_nibble() -> None:
    assert _hex(b"4 >") == b"\x40"
    assert _hex(b"4 \n") == b"\x40"


def _params(**entries: int) -> COSDictionary:
    params = COSDictionary()
    for key, value in entries.items():
        params.set_int(key, value)
    return params


@pytest.mark.parametrize(
    "predictor", [2, 10, 12, 15], ids=["tiff", "png_none", "png_up", "png_opt"]
)
def test_predictor_zero_columns_rejected(predictor: int) -> None:
    with pytest.raises(OSError, match="row length is not positive"):
        PredictorOutputStream(io.BytesIO(), predictor, 1, 8, 0)


def test_flate_decode_zero_columns_tiff_predictor_does_not_hang() -> None:
    params = _params(Predictor=2, Columns=0)
    encoded = zlib.compress(b"\x01\x02\x03\x04")
    with pytest.raises(OSError, match="row length is not positive"):
        FlateDecode().decode(io.BytesIO(encoded), io.BytesIO(), params)


def test_lzw_decode_zero_columns_tiff_predictor_does_not_hang() -> None:
    raw = b"\x01\x02\x03\x04"
    encoded = io.BytesIO()
    LZWDecode().encode(io.BytesIO(raw), encoded, COSDictionary())
    params = _params(Predictor=2, Columns=0)
    with pytest.raises(OSError, match="row length is not positive"):
        LZWDecode().decode(io.BytesIO(encoded.getvalue()), io.BytesIO(), params)


def test_predictor_positive_row_length_still_decodes() -> None:
    sink = io.BytesIO()
    stream = PredictorOutputStream(sink, 2, 1, 8, 1)
    stream.write(b"\x05\x06")
    stream.flush()
    assert sink.getvalue() == b"\x05\x06"
