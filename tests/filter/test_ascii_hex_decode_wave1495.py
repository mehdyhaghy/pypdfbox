"""Wave 1495 — coverage round-out for ``ASCIIHexDecode``.

Pins the two behavioural surfaces the existing decode/encode suite left
unexercised:

* a trailing run of whitespace bytes with no following hex digit — the
  inner whitespace-skip loop walks off the end of the buffer and stops
  decoding (upstream ``ASCIIHexFilter`` treats the EOF-after-whitespace
  case identically to EOD: nothing more is written);
* ``is_decompression_input_size_known()`` — ``False`` for the hex filter,
  mirroring upstream ``ASCIIHexFilter`` (the decoded size cannot be
  predicted from the encoded byte count because whitespace and the EOD
  marker are not 1:1 with output bytes).
"""

from __future__ import annotations

import io

from pypdfbox.filter import ASCIIHexDecode


def _decode(encoded: bytes) -> bytes:
    out = io.BytesIO()
    ASCIIHexDecode().decode(io.BytesIO(encoded), out)
    return out.getvalue()


def test_trailing_whitespace_after_complete_pairs_stops_cleanly() -> None:
    # "4142" decodes to "AB"; the trailing whitespace run has no following
    # nibble, so the whitespace-skip loop hits EOF and decoding stops with
    # no extra byte emitted.
    assert _decode(b"4142   \n\t ") == b"AB"


def test_only_whitespace_decodes_to_empty() -> None:
    # A buffer that is nothing but whitespace: the first-nibble skip loop
    # walks off the end on the very first iteration (``first = -1``) and the
    # decoder emits nothing.
    assert _decode(b" \t\r\n\x00\x0c") == b""


def test_whitespace_splitting_a_pair_is_an_invalid_low_nibble() -> None:
    # "A " — the high nibble "A" (10) is read, then the low-nibble read does
    # NOT skip whitespace, so the space byte maps through REVERSE_HEX to -1:
    # 10*16 + (-1) = 159 = 0x9f (low 8 bits). Verified against the live
    # PDFBox 3.0.7 oracle's ASCIIHexFilter (wave 1412).
    assert _decode(b"A ") == b"\x9f"


def test_lone_high_nibble_at_eof_pads_low_nibble_with_zero() -> None:
    # A single hex digit with no following byte at all: the low-nibble read
    # hits EOF and the high nibble is written with a 0 low nibble -> 0xA0.
    assert _decode(b"A") == b"\xa0"


def test_is_decompression_input_size_known_is_false() -> None:
    assert ASCIIHexDecode().is_decompression_input_size_known() is False
