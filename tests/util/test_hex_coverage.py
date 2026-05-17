"""Wave 1343: targeted coverage tests for ``pypdfbox.util.hex.Hex``.

Targets the residual missing lines after wave 1281 -- the single-byte
``get_bytes`` branch, the ``write_hex_bytes`` sequence helper, the
``decode_hex`` whitespace tolerance path and the invalid-hex-pair abort
path.
"""

from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.util.hex import Hex

# ----------------------------------------------------------------------
# get_bytes -- single int branch (line 64-65)
# ----------------------------------------------------------------------


def test_get_bytes_single_int_value() -> None:
    """A plain ``int`` returns a 2-byte ASCII hex pair."""
    assert Hex.get_bytes(0x4F) == b"4F"


def test_get_bytes_single_int_masks_to_byte() -> None:
    """Values outside 0..255 are masked to a single byte."""
    # 0x14F & 0xFF -> 0x4F
    assert Hex.get_bytes(0x14F) == b"4F"


def test_get_bytes_single_int_zero() -> None:
    assert Hex.get_bytes(0) == b"00"


def test_get_bytes_single_int_max_byte() -> None:
    assert Hex.get_bytes(0xFF) == b"FF"


# ----------------------------------------------------------------------
# write_hex_bytes -- sequence helper (line 103-104)
# ----------------------------------------------------------------------


def test_write_hex_bytes_writes_all_bytes_uppercase() -> None:
    buf = io.BytesIO()
    Hex.write_hex_bytes(b"\x00\xff\x4f", buf)
    assert buf.getvalue() == b"00FF4F"


def test_write_hex_bytes_empty_data_writes_nothing() -> None:
    buf = io.BytesIO()
    Hex.write_hex_bytes(b"", buf)
    assert buf.getvalue() == b""


def test_write_hex_bytes_accepts_bytearray() -> None:
    buf = io.BytesIO()
    Hex.write_hex_bytes(bytearray(b"\x10\x20"), buf)
    assert buf.getvalue() == b"1020"


# ----------------------------------------------------------------------
# decode_hex -- CR/LF skip path (line 120-121)
# ----------------------------------------------------------------------


def test_decode_hex_skips_linefeed_mid_stream() -> None:
    """Mid-stream ``\\n`` characters are dropped and decoding resumes."""
    # "48" + "\n" + "69" -> "Hi"
    assert Hex.decode_hex("48\n69") == b"Hi"


def test_decode_hex_skips_carriage_return_mid_stream() -> None:
    assert Hex.decode_hex("48\r69") == b"Hi"


def test_decode_hex_skips_mixed_crlf() -> None:
    assert Hex.decode_hex("48\r\n69") == b"Hi"


def test_decode_hex_leading_linefeed() -> None:
    # Leading \n then "4869"
    assert Hex.decode_hex("\n4869") == b"Hi"


# ----------------------------------------------------------------------
# decode_hex -- invalid pair abort (line 126-128)
# ----------------------------------------------------------------------


def test_decode_hex_aborts_on_invalid_pair(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-hex byte triggers an error log and decode stops."""
    with caplog.at_level(logging.ERROR, logger="pypdfbox.util.hex"):
        # "48" decodes fine, "Zz" is invalid -> abort, "69" never reached
        result = Hex.decode_hex("48Zz69")
    assert result == b"H"
    assert any("Zz" in r.getMessage() for r in caplog.records)


def test_decode_hex_aborts_on_invalid_first_nibble() -> None:
    # First pair invalid -> empty result, abort immediately
    assert Hex.decode_hex("ZZ4869") == b""


def test_decode_hex_aborts_on_invalid_second_nibble() -> None:
    # "4Z" -> 16 * 4 + (-256) negative -> abort
    assert Hex.decode_hex("4Z4869") == b""


def test_decode_hex_empty_input_returns_empty() -> None:
    assert Hex.decode_hex("") == b""


def test_decode_hex_single_char_returns_empty() -> None:
    """Loop guard ``i < len(s) - 1`` means lone trailing char is dropped."""
    assert Hex.decode_hex("4") == b""


def test_decode_hex_odd_length_drops_trailing() -> None:
    """Odd-length input decodes pairs and silently drops the trailing char."""
    assert Hex.decode_hex("48696") == b"Hi"


def test_decode_hex_lowercase_hex_decoded() -> None:
    assert Hex.decode_hex("4869") == b"Hi"
    assert Hex.decode_hex("4869").decode("ascii") == "Hi"
    assert Hex.decode_hex("abcd") == b"\xab\xcd"
