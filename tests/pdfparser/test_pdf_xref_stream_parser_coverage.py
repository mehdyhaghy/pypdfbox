"""Coverage-boost tests for ``PDFXrefStreamParser``.

Targets:
 - the parse loop (normal entries, free entries, compressed entries,
   default-type-when-W0-zero path)
 - read_next_value / parse_value helpers
 - close() lifecycle
 - the public init_parser_values delegate
 - the OSError-on-init swallow path
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.pdfparser.pdf_xref_stream_parser import PDFXrefStreamParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefTrailerResolver


def _stream(
    w: list[int],
    index: list[int],
    body: bytes,
) -> COSStream:
    """Build a /XRef-style COSStream with a `/W` array, `/Index` array,
    and a raw body (no filter)."""
    stream = COSStream()
    w_arr = COSArray()
    for v in w:
        w_arr.add(COSInteger.get(v))
    stream.set_item(COSName.W, w_arr)
    idx_arr = COSArray()
    for v in index:
        idx_arr.add(COSInteger.get(v))
    stream.set_item(COSName.INDEX, idx_arr)
    out = stream.create_raw_output_stream()
    try:
        out.write(body)
    finally:
        out.close()
    return stream


# ---------------------------------------------------------------------
# Parse loop — normal in-use entries (type 1)
# ---------------------------------------------------------------------


def test_parse_normal_in_use_entry() -> None:
    # W = [1, 2, 1]: 1 byte type, 2 bytes offset, 1 byte generation.
    # One entry, obj number 5: type=1, offset=0x1234 (4660), gen=0.
    body = bytes([0x01, 0x12, 0x34, 0x00])
    stream = _stream([1, 2, 1], [5, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)

    table = resolver.get_xref_table()
    keys = list(table.keys())
    assert len(keys) == 1
    assert keys[0].get_number() == 5
    # offset is stored as the second column value
    assert table[keys[0]].offset == 0x1234


def test_parse_multiple_in_use_entries() -> None:
    # Three entries starting at obj 10: gen all 0, varying offsets.
    body = bytes([
        0x01, 0x00, 0x10, 0x00,
        0x01, 0x00, 0x20, 0x00,
        0x01, 0x01, 0x00, 0x00,
    ])
    stream = _stream([1, 2, 1], [10, 3], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    offsets = {k.get_number(): v.offset for k, v in table.items()}
    assert offsets == {10: 0x10, 11: 0x20, 12: 0x100}


# ---------------------------------------------------------------------
# Parse loop — free entries (type 0) are skipped
# ---------------------------------------------------------------------


def test_parse_free_entry_skipped() -> None:
    # First entry free (type 0), second in-use.
    body = bytes([
        0x00, 0x00, 0x00, 0xFF,
        0x01, 0x00, 0x42, 0x00,
    ])
    stream = _stream([1, 2, 1], [7, 2], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    keys = sorted(table.keys(), key=lambda k: k.get_number())
    # Free entry not recorded, only obj 8 in-use makes it through.
    assert len(keys) == 1
    assert keys[0].get_number() == 8
    assert table[keys[0]].offset == 0x42


# ---------------------------------------------------------------------
# Parse loop — compressed entries (type 2)
# ---------------------------------------------------------------------


def test_parse_compressed_entry_negative_offset_convention() -> None:
    # Type 2 entries: column 2 = parent object-stream number, column 3 =
    # index inside the object stream. Stored as -parent.
    body = bytes([
        0x02, 0x00, 0x09, 0x03,
    ])
    stream = _stream([1, 2, 1], [12, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    keys = list(table.keys())
    assert len(keys) == 1
    # Compressed entry: encoded via COSObjectKey(obj, 0, third_value).
    assert keys[0].get_number() == 12
    # offset is -parent_stream_number per the upstream sign convention.
    assert table[keys[0]].offset == -9


# ---------------------------------------------------------------------
# Parse loop — default type when W[0] == 0 (defaults to 1)
# ---------------------------------------------------------------------


def test_parse_default_type_when_w0_zero() -> None:
    # W = [0, 2, 1] — no type column, all entries default to type 1.
    body = bytes([
        0x00, 0x55, 0x00,
        0x00, 0x77, 0x00,
    ])
    stream = _stream([0, 2, 1], [1, 2], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    offsets = {k.get_number(): v.offset for k, v in table.items()}
    assert offsets == {1: 0x55, 2: 0x77}


# ---------------------------------------------------------------------
# Helpers — read_next_value + parse_value
# ---------------------------------------------------------------------


def test_parse_value_static_big_endian() -> None:
    buf = bytearray([0x01, 0x02, 0x03, 0x04])
    assert PDFXrefStreamParser.parse_value(buf, 0, 4) == 0x01020304
    assert PDFXrefStreamParser.parse_value(buf, 1, 2) == 0x0203
    assert PDFXrefStreamParser.parse_value(buf, 0, 0) == 0
    # Single-byte value
    assert PDFXrefStreamParser.parse_value(buf, 3, 1) == 0x04


def test_parse_value_private_alias_matches_public() -> None:
    buf = bytearray([0xFF, 0x00, 0xAA])
    assert PDFXrefStreamParser._parse_value(buf, 0, 3) == 0xFF00AA


def test_read_next_value_fills_buffer() -> None:
    body = bytes([0x01, 0x00, 0x10, 0x00])
    stream = _stream([1, 2, 1], [1, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    # Read all 4 bytes into a fresh buffer via the public helper.
    target = bytearray(4)
    parser.read_next_value(target)
    assert bytes(target) == body
    parser.close()


def test_read_next_value_handles_short_read_loop() -> None:
    # Body shorter than the buffer — read_next_value should bail at EOF.
    body = bytes([0xAA, 0xBB])
    stream = _stream([1, 2, 1], [1, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    target = bytearray(5)
    parser.read_next_value(target)
    # First two bytes read; remainder stays at zero (initial bytearray).
    assert target[0] == 0xAA
    assert target[1] == 0xBB
    parser.close()


# ---------------------------------------------------------------------
# close() lifecycle
# ---------------------------------------------------------------------


def test_close_releases_source_and_object_numbers() -> None:
    body = bytes([0x01, 0x00, 0x10, 0x00])
    stream = _stream([1, 2, 1], [1, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    assert parser._object_numbers is not None
    parser.close()
    assert parser._object_numbers is None
    # Calling close twice (via alias) is safe — _close === close.
    parser._close()


def test_parse_invokes_close_when_done() -> None:
    body = bytes([0x01, 0x00, 0x10, 0x00])
    stream = _stream([1, 2, 1], [1, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    # After parse, the public surface mirrors close()'s post-state.
    assert parser._object_numbers is None


# ---------------------------------------------------------------------
# Public init_parser_values delegate
# ---------------------------------------------------------------------


def test_init_parser_values_public_alias_delegates() -> None:
    body = bytes([0x01, 0x00, 0x10, 0x00])
    stream = _stream([1, 2, 1], [1, 1], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    # Calling the public alias re-runs the init logic against a new
    # /Index — verify it does not throw and re-assigns the iterator.
    new_stream = _stream([1, 2, 1], [99, 1], body)
    parser.init_parser_values(new_stream)
    assert parser._object_numbers is not None
    parser.close()


# ---------------------------------------------------------------------
# Parse loop termination — exhaustion / empty body
# ---------------------------------------------------------------------


def test_parse_with_zero_size_index() -> None:
    # /Index covers zero objects — has_next() is false from the start.
    body = b""
    stream = _stream([1, 2, 1], [0, 0], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    assert resolver.get_xref_table() == {}


def test_parse_stops_when_eof_reached_before_index_exhausted() -> None:
    # /Index says 3 objects, but body only carries 1 entry — loop must
    # exit cleanly via is_eof().
    body = bytes([0x01, 0x00, 0x10, 0x00])
    stream = _stream([1, 2, 1], [50, 3], body)
    parser = PDFXrefStreamParser(stream, COSDocument())
    resolver = XrefTrailerResolver()
    resolver.begin_section(0)
    parser.parse(resolver)
    table = resolver.get_xref_table()
    # Only one entry parsed before EOF.
    assert len(table) == 1
