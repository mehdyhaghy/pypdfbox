"""Fuzz parity for COSName #-hex escape parse/write round-trips (wave 1570).

Hammers ``BaseParser.read_name_bytes`` (upstream ``BaseParser.parseCOSName``)
and ``COSName.write_pdf`` (upstream ``COSName.writePDF``) against the PDFBox
3.0.7 contract:

* parse: ``#XX`` decodes the hex byte (both cases), ``#`` followed by a
  non-hex pair is kept literally, a premature-EOF ``#`` is discarded;
* write: only ``A-Z a-z 0-9 + - _ @ * $ ; .`` pass through verbatim — every
  other byte (whitespace, delimiters, ``#`` itself, bytes <0x21 / >0x7e,
  high bytes 0x80-0xFF) is written as uppercase ``#XX``;
* round-trip identity: parse(write(name)) preserves the raw bytes.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BaseParser


def _parse(data: bytes) -> bytes:
    """Run ``read_name_bytes`` over ``data`` and return the decoded bytes."""
    return BaseParser(RandomAccessReadBuffer(data)).read_name_bytes()


def _write(name_bytes: bytes) -> bytes:
    """Run ``COSName.write_pdf`` and return the serialised bytes."""
    out = io.BytesIO()
    COSName.get_pdf_name(name_bytes).write_pdf(out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# parse side: #XX hex decoding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("encoded", "expected"),
    [
        (b"/A#20B", b"A B"),  # #20 -> space
        (b"/A#23B", b"A#B"),  # #23 -> '#'
        (b"/Lime#20Green", b"Lime Green"),  # upstream COSName javadoc example
        (b"/paired#23#23", b"paired##"),  # multi-escape
        (b"/#41#42#43", b"ABC"),  # leading escapes
        (b"/F#6F#6F", b"Foo"),  # lowercase hex digits
        (b"/F#6f#6F", b"Foo"),  # mixed-case hex digits
        (b"/#2f", b"/"),  # escaped slash (delimiter)
        (b"/#28#29", b"()"),  # escaped parens
        (b"/#00", b"\x00"),  # escaped NUL
        (b"/#ff", b"\xff"),  # escaped high byte (low-hex)
        (b"/#FF", b"\xff"),  # escaped high byte (up-hex)
        (b"/#80", b"\x80"),  # 0x80 boundary
    ],
    ids=[
        "space",
        "hash",
        "lime_green",
        "double_hash",
        "leading_abc",
        "lower_hex",
        "mixed_hex",
        "slash",
        "parens",
        "nul",
        "ff_low",
        "ff_up",
        "x80",
    ],
)
def test_parse_hex_escape(encoded: bytes, expected: bytes) -> None:
    assert _parse(encoded) == expected


def test_parse_terminator_stops_name() -> None:
    # Name terminates at the first delimiter / whitespace, leaving it unread.
    src = RandomAccessReadBuffer(b"/Foo Bar")
    p = BaseParser(src)
    assert p.read_name_bytes() == b"Foo"
    # The terminating space was rewound, not consumed.
    assert src.read() == 0x20


def test_parse_empty_name() -> None:
    # '/' immediately followed by a terminator yields the empty name.
    assert _parse(b"/ ") == b""
    assert _parse(b"/") == b""
    assert _parse(b"/[") == b""


def test_parse_embedded_null_terminates() -> None:
    # A raw NUL byte is whitespace per the PDF spec -> terminates the name.
    assert _parse(b"/Foo\x00Bar") == b"Foo"


# ---------------------------------------------------------------------------
# parse side: incomplete / malformed escapes (upstream BaseParser semantics)
# ---------------------------------------------------------------------------


def test_parse_hash_at_eof_discarded() -> None:
    # '#' with no following bytes: premature EOF -> dangling '#' dropped.
    assert _parse(b"/AB#") == b"AB"


def test_parse_hash_one_digit_eof_discarded() -> None:
    # '#' + single hex digit then EOF: still premature EOF -> '#' dropped,
    # and the single digit is consumed with it (matches PDFBox 3.0.7).
    assert _parse(b"/AB#4") == b"AB"


def test_parse_hash_non_hex_kept_literal() -> None:
    # '#' followed by a non-hex pair (neither EOF): '#' kept, first byte
    # reprocessed -> '#GB' survives literally.
    assert _parse(b"/A#GB ") == b"A#GB"


def test_parse_hash_first_hex_second_non_hex() -> None:
    # '#4G': ch1='4' is hex, ch2='G' is not -> not a valid pair, so '#'
    # literal, then '4' and 'G' reprocessed verbatim.
    assert _parse(b"/A#4G ") == b"A#4G"


def test_parse_hash_followed_by_terminator_then_eof() -> None:
    # '#' then a delimiter '/' (a name terminator) as ch1: not hex, not EOF
    # for ch1 but ch2 is the rest -> '#' literal then '/' terminates.
    src = RandomAccessReadBuffer(b"/A#/B")
    p = BaseParser(src)
    # ch1='/', ch2='B': ch1 is not hex and not EOF -> rewind ch2, '#' kept,
    # reprocess '/', which is a terminator -> name is 'A#'.
    assert p.read_name_bytes() == b"A#"


# ---------------------------------------------------------------------------
# write side: pass-through set vs escaped set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "passthrough",
    [
        b"Type",
        b"ABCXYZ",
        b"abcxyz",
        b"0123456789",
        b"a+b-c_d@e*f$g;h.i",  # every allowed punctuation byte
    ],
    ids=["type", "upper", "lower", "digits", "punct"],
)
def test_write_passthrough(passthrough: bytes) -> None:
    assert _write(passthrough) == b"/" + passthrough


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"A B", b"/A#20B"),  # space
        (b"A\tB", b"/A#09B"),  # tab
        (b"A\nB", b"/A#0AB"),  # newline
        (b"A\rB", b"/A#0DB"),  # carriage return
        (b"A#B", b"/A#23B"),  # the '#' char itself MUST escape
        (b"A(B)C", b"/A#28B#29C"),  # parens
        (b"A<B>C", b"/A#3CB#3EC"),  # angle brackets
        (b"A[B]C", b"/A#5BB#5DC"),  # square brackets
        (b"A{B}C", b"/A#7BB#7DC"),  # curly braces
        (b"A/B", b"/A#2FB"),  # slash
        (b"A%B", b"/A#25B"),  # percent
        (b"\x00", b"/#00"),  # NUL (<0x21)
        (b"\x20", b"/#20"),  # space byte alone (0x20 == <0x21 boundary)
        (b"\x7e", b"/#7E"),  # '~' is 0x7e -> escaped (not in passthrough set)
        (b"\x7f", b"/#7F"),  # DEL (>0x7e)
        (b"\x80", b"/#80"),  # high-byte boundary
        (b"\xff", b"/#FF"),  # top high byte
    ],
    ids=[
        "space",
        "tab",
        "newline",
        "cr",
        "hash",
        "parens",
        "angle",
        "square",
        "curly",
        "slash",
        "percent",
        "nul",
        "space_byte",
        "tilde",
        "del",
        "x80",
        "xff",
    ],
)
def test_write_escape(raw: bytes, expected: bytes) -> None:
    assert _write(raw) == expected


def test_write_hex_is_uppercase() -> None:
    # %02X in upstream -> uppercase hex digits on output.
    out = _write(b"\xab\xcd\xef")
    assert out == b"/#AB#CD#EF"
    assert b"#ab" not in out  # no lowercase hex leaks


def test_write_all_low_control_bytes_escaped() -> None:
    # Every byte < 0x21 must be escaped (none are in the passthrough set).
    for b in range(0x00, 0x21):
        assert _write(bytes((b,))) == b"/#" + f"{b:02X}".encode("ascii")


def test_write_all_high_bytes_escaped() -> None:
    # Every byte > 0x7e must be escaped.
    for b in range(0x7F, 0x100):
        assert _write(bytes((b,))) == b"/#" + f"{b:02X}".encode("ascii")


def test_write_empty_name() -> None:
    assert _write(b"") == b"/"


# ---------------------------------------------------------------------------
# round-trip identity: parse(write(x)) == x
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b"Type",
        b"A B",
        b"A#B",
        b"A(B)C/D%E",
        b"\x00\x01\x1f",
        b"\x7f\x80\xff",
        b"Lime Green",
        bytes(range(0x00, 0x80)),
        bytes(range(0x80, 0x100)),
    ],
    ids=[
        "type",
        "space",
        "hash",
        "delims",
        "low_ctrl",
        "high",
        "lime_green",
        "ascii_block",
        "high_block",
    ],
)
def test_round_trip_identity(raw: bytes) -> None:
    serialised = _write(raw)
    # Append a terminator so the parser knows where the name ends; for inputs
    # whose final byte is escaped the serialisation is self-delimiting, but a
    # trailing space is harmless and required when the last byte passes through.
    assert _parse(serialised + b" ") == raw


def test_round_trip_full_byte_range_individually() -> None:
    for b in range(0x00, 0x100):
        raw = bytes((b,))
        serialised = _write(raw)
        assert _parse(serialised + b" ") == raw, f"byte {b:#04x} failed round-trip"


# ---------------------------------------------------------------------------
# interning / cache identity
# ---------------------------------------------------------------------------


def test_interning_same_bytes_same_instance() -> None:
    a = COSName.get_pdf_name(b"Wave1570Foo")
    b = COSName.get_pdf_name(b"Wave1570Foo")
    assert a is b


def test_interning_str_and_utf8_bytes_collapse() -> None:
    # get_pdf_name(str) uses UTF-8 bytes -> equal to the byte form.
    a = COSName.get_pdf_name("Wave1570Bar")
    b = COSName.get_pdf_name(b"Wave1570Bar")
    assert a is b


def test_interning_distinct_bytes_distinct_instance() -> None:
    a = COSName.get_pdf_name(b"Wave1570One")
    b = COSName.get_pdf_name(b"Wave1570Two")
    assert a is not b
    assert a != b


def test_parse_then_get_pdf_name_interns() -> None:
    raw = _parse(b"/Wave1570#20Cache ")
    assert raw == b"Wave1570 Cache"
    a = COSName.get_pdf_name(raw)
    b = COSName.get_pdf_name(b"Wave1570 Cache")
    assert a is b


# ---------------------------------------------------------------------------
# get_name UTF-8 vs cp1252 fallback byte interpretation
# ---------------------------------------------------------------------------


def test_get_name_utf8_decode() -> None:
    # Valid UTF-8 multibyte sequence decodes as UTF-8.
    raw = "Café".encode("utf-8")  # 'Café' -> 0x43 0x61 0x66 0xC3 0xA9
    assert COSName.get_pdf_name(raw).get_name() == "Café"


def test_get_name_latin1_fallback() -> None:
    # A lone 0xE9 is not valid UTF-8 -> cp1252 fallback maps it to 'é'.
    name = COSName.get_pdf_name(b"Caf\xe9").get_name()
    assert name == "Café"


def test_get_name_cp1252_high_byte() -> None:
    # 0x80 in cp1252 is the euro sign (distinct from Latin-1's U+0080).
    name = COSName.get_pdf_name(b"\x80").get_name()
    assert name == "€"
