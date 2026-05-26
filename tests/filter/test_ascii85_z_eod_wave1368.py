"""Wave 1368 (agent D) — ASCII85Decode shortcuts: 'z', '~>', whitespace.

ISO 32000-1 §7.4.3 corner cases:

* A 4-zero group is abbreviated as the single ASCII byte ``z``.
* The end-of-data marker is the literal two bytes ``~>``.
* Whitespace ignored during decode is ONLY LF, CR and SPACE — PDFBox's
  ASCII85InputStream does NOT skip NUL / TAB / FF / VT (wave 1412 oracle).
* Partial groups: a lone trailing digit yields no byte (dropped); 2/3/4
  trailing digits map to 1/2/3 raw bytes with the missing low base-85
  digits padded with ``u``.

Tests exercise the decoder's tolerance for whitespace at various
positions and the ``z`` shortcut. A ``z`` mid-group is NOT special — it is
an ordinary base-85 digit (the shortcut only fires at a group boundary),
matching the behaviour confirmed against the live PDFBox oracle.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import ASCII85Decode


def _decode(encoded: bytes) -> bytes:
    f = ASCII85Decode()
    out = io.BytesIO()
    f.decode(io.BytesIO(encoded), out, COSDictionary(), 0)
    return out.getvalue()


def _encode(raw: bytes) -> bytes:
    f = ASCII85Decode()
    out = io.BytesIO()
    f.encode(io.BytesIO(raw), out, COSDictionary())
    return out.getvalue()


# ---- z shortcut ------------------------------------------------------


def test_z_shortcut_decodes_to_four_zero_bytes() -> None:
    """A bare 'z' in the stream becomes four NUL bytes."""
    assert _decode(b"z~>") == b"\x00\x00\x00\x00"


def test_z_shortcut_repeated() -> None:
    """Multiple 'z's expand to multiple groups of four zeros."""
    assert _decode(b"zzz~>") == b"\x00" * 12


def test_z_shortcut_mixed_with_other_groups() -> None:
    """'z' inline with real base-85 groups decodes correctly."""
    # b"!!!!!" is the base-85 encoding of four 0x00 bytes (the long form
    # of 'z'). Mixing both forms should yield 8 zero bytes.
    assert _decode(b"!!!!!z~>") == b"\x00" * 8


def test_z_mid_group_is_an_ordinary_digit() -> None:
    """A 'z' in columns 1..4 of a group is NOT the 4-zero shortcut.

    PDFBox's ASCII85InputStream only treats 'z' specially at a group
    boundary; mid-group it contributes ``0x7a - '!' == 89`` to the base-85
    accumulator like any other digit. Verified against the live oracle
    (wave 1412): ``az~>`` decodes to a single 0xCA byte, not an error.
    """
    assert _decode(b"az~>") == b"\xca"


def test_z_shortcut_round_trip_via_encode() -> None:
    """Encoder emits 'z' for an all-zero 4-byte group; decoder accepts it."""
    raw = b"\x00\x00\x00\x00"
    enc = _encode(raw)
    # Adobe-mode stdlib uses 'z' for all-zero groups; the encoded body
    # without the b'<~' framing should contain a 'z'.
    assert b"z" in enc
    assert _decode(enc + b"~>") == raw


# ---- EOD marker ------------------------------------------------------


def test_decode_strips_trailing_bytes_after_eod() -> None:
    """Bytes after the first ``~>`` are ignored."""
    encoded = b"87cURDZ~>garbage trailing bytes here"
    assert _decode(encoded) == b"Hello"


def test_decode_without_eod_still_works() -> None:
    """Spec allows a missing EOD; decoder consumes everything."""
    assert _decode(b"87cURDZ") == b"Hello"


def test_decode_empty_payload_with_eod() -> None:
    """``~>`` alone decodes to empty bytes."""
    assert _decode(b"~>") == b""


def test_decode_eod_inside_whitespace() -> None:
    """``~>`` with surrounding whitespace still terminates the stream."""
    encoded = b"  87cURDZ  ~>\n\nignored"
    assert _decode(encoded) == b"Hello"


# ---- Whitespace tolerance --------------------------------------------


def test_decode_with_embedded_whitespace() -> None:
    """Only LF, CR and SPACE are ASCII85 whitespace in PDFBox.

    b"87cURDZ" → b"Hello"; sprinkle the three flavours PDFBox actually
    skips (verified against the live oracle, wave 1412).
    """
    encoded = b"8 7\nc\rUR D\nZ~>"
    assert _decode(encoded) == b"Hello"


def test_decode_rejects_non_pdfbox_whitespace_mid_stream() -> None:
    """TAB, NUL and FF are NOT whitespace — they trip the range check."""
    for ws in (b"\t", b"\x00", b"\x0c"):
        with pytest.raises(OSError, match="Invalid data"):
            _decode(b"87" + ws + b"cURDZ~>")


def test_decode_leading_whitespace_only() -> None:
    """Leading whitespace doesn't shift the EOD detection."""
    assert _decode(b"\n\n\n87cURDZ~>") == b"Hello"


# ---- Out-of-range digits ---------------------------------------------


def test_decode_rejects_byte_below_bang() -> None:
    """A byte below 0x21 (excluding LF/CR/SPACE) trips the range check."""
    with pytest.raises(OSError, match="Invalid data"):
        _decode(b"BO\x01u!rDZ~>")


def test_decode_accepts_byte_above_u_up_to_tilde() -> None:
    """PDFBox accepts digits up to b'~' (0x7e), wider than b'!'..b'u'.

    The encoder never emits a digit above 'u' (0x75), but the decoder's
    range check is ``c - '!'`` in 0..93, so 'v' (0x76) and anything up to
    '~' are accepted and the per-group overflow is masked to 32 bits.
    Verified against the live oracle (wave 1412).
    """
    assert _decode(b"BOv!rDZ~>") == bytes.fromhex("686588a56f")


# ---- Partial-group handling ------------------------------------------


def test_decode_drops_single_trailing_digit() -> None:
    """A trailing partial group of one digit yields no output byte.

    5 valid digits → 4 bytes; the lone trailing 'Z' digit cannot form even
    one of the four group bytes, so PDFBox drops it silently rather than
    raising. Verified against the live oracle (wave 1412).
    """
    assert _decode(b"BOu!rZ~>") == bytes.fromhex("68656c6c")


def test_decode_partial_group_two_digits_round_trip() -> None:
    """A 2-digit partial group decodes to 1 raw byte."""
    raw = b"H"
    enc = _encode(raw)
    assert _decode(enc + b"~>") == raw


def test_decode_partial_group_three_digits_round_trip() -> None:
    """A 3-digit partial group decodes to 2 raw bytes."""
    raw = b"Hi"
    enc = _encode(raw)
    assert _decode(enc + b"~>") == raw


def test_decode_partial_group_four_digits_round_trip() -> None:
    """A 4-digit partial group decodes to 3 raw bytes."""
    raw = b"Hi!"
    enc = _encode(raw)
    assert _decode(enc + b"~>") == raw


# ---- Full round-trips ------------------------------------------------


def test_full_round_trip_all_bytes() -> None:
    """Every byte value 0..255 round-trips."""
    raw = bytes(range(256))
    enc = _encode(raw)
    assert _decode(enc + b"~>") == raw


def test_full_round_trip_empty() -> None:
    """Empty raw bytes round-trip to empty."""
    enc = _encode(b"")
    assert _decode(enc + b"~>") == b""


def test_decode_pure_z_zeros_no_eod() -> None:
    """Stream of only 'z' bytes without EOD still decodes correctly."""
    assert _decode(b"zz") == b"\x00" * 8
