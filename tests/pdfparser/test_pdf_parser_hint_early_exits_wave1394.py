"""Wave 1394 — hint-table early-exit branches in ``PDFParser``.

Closes the defensive ``return None`` ladders in:

* ``decode_page_offset_hint_table`` (lines 409, 412, 417, 420, 434, 437,
  440, 443, 448-449)
* ``_read_hint_stream_decoded`` (lines 472, 475, 485, 488, 491, 494,
  498-499)
* ``_hint_subtable_offset`` (lines 514, 520, 523)
* ``decode_shared_object_hint_table`` / ``decode_thumbnail_hint_table``
  early-exits (lines 558-559, 584, 590-591)

Each test feeds a hand-built linearization dict that trips exactly one
guard, asserting ``None`` is returned without raising. The PDF byte
layout reuses the helper from ``test_linearized.py`` for shape
verification, but most checks construct the parser + linearization
dict by hand and call the decode method directly — cheaper than
running ``parse()``.
"""

from __future__ import annotations

import struct
import zlib

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser

# ---------- helpers ----------


def _bare_parser() -> PDFParser:
    """Empty PDFParser whose linearization fields can be patched directly."""
    return PDFParser(RandomAccessReadBuffer(b"%PDF-1.7\n%%EOF\n"))


def _set_lin(parser: PDFParser, lin: COSDictionary | None) -> None:
    parser.linearization_dict = lin  # type: ignore[assignment]


def _h_array(*values: int | object) -> COSArray:
    arr = COSArray()
    for v in values:
        if isinstance(v, int):
            arr.add(COSInteger.get(v))
        else:
            arr.add(v)  # already a COSBase
    return arr


def _lin_dict(*, n: int | None = 1, h_array: COSArray | None | object = None) -> COSDictionary:
    d = COSDictionary()
    if n is not None:
        d.set_item(COSName.get_pdf_name("N"), COSInteger.get(n))
    if h_array is not None:
        d.set_item(COSName.get_pdf_name("H"), h_array)
    return d


# ---------- decode_page_offset_hint_table early-exits ----------


def test_decode_page_offset_returns_none_when_no_linearization_dict() -> None:
    parser = _bare_parser()
    _set_lin(parser, None)
    assert parser.decode_page_offset_hint_table() is None


def test_decode_page_offset_returns_none_when_n_missing_or_wrong_type() -> None:
    parser = _bare_parser()
    lin = COSDictionary()
    # /N is a string — not Integer/Float → line 409 return.
    lin.set_item(COSName.get_pdf_name("N"), COSName.get_pdf_name("bogus"))
    _set_lin(parser, lin)
    assert parser.decode_page_offset_hint_table() is None


def test_decode_page_offset_returns_none_when_n_zero() -> None:
    parser = _bare_parser()
    lin = _lin_dict(n=0, h_array=_h_array(100, 200))
    _set_lin(parser, lin)
    # Line 412: page_count <= 0
    assert parser.decode_page_offset_hint_table() is None


def test_decode_page_offset_returns_none_when_h_array_too_short() -> None:
    parser = _bare_parser()
    lin = _lin_dict(n=1, h_array=_h_array(100))  # only one entry
    _set_lin(parser, lin)
    # Line 417: h_arr.size() < 2
    assert parser.decode_page_offset_hint_table() is None


def test_decode_page_offset_returns_none_when_h0_wrong_type() -> None:
    parser = _bare_parser()
    h_arr = COSArray()
    h_arr.add(COSName.get_pdf_name("not-a-number"))
    h_arr.add(COSInteger.get(200))
    lin = _lin_dict(n=1, h_array=h_arr)
    _set_lin(parser, lin)
    # Line 420: h_off_obj wrong type.
    assert parser.decode_page_offset_hint_table() is None


def test_decode_page_offset_returns_none_when_no_xref_entry_matches() -> None:
    parser = _bare_parser()
    lin = _lin_dict(n=1, h_array=_h_array(999999, 200))
    _set_lin(parser, lin)
    # Line 434: target_key is None — empty xref, no match.
    assert parser.decode_page_offset_hint_table() is None


def _seed_xref(parser: PDFParser, key: COSObjectKey, offset: int) -> None:
    """Register an xref entry on the parser's resolver. ``get_xref_table()``
    returns a fresh merged dict each call, so mutations to it don't stick —
    we add the entry via the section setter."""
    from pypdfbox.pdfparser import XrefEntry, XrefType

    parser._resolver.begin_section(0)  # noqa: SLF001
    parser._resolver.set_entry(  # noqa: SLF001
        key, XrefEntry(type=XrefType.TABLE, offset=offset)
    )


def test_decode_page_offset_returns_none_when_document_missing() -> None:
    """Lines 437: document is None even when xref carries a matching entry."""
    parser = _bare_parser()
    lin = _lin_dict(n=1, h_array=_h_array(100, 200))
    # Seed xref so target_key resolves; leave _document unset.
    _seed_xref(parser, COSObjectKey(2, 0), 100)
    parser._document = None  # noqa: SLF001
    _set_lin(parser, lin)
    assert parser.decode_page_offset_hint_table() is None


# ---------- _read_hint_stream_decoded early-exits ----------


def test_read_hint_stream_decoded_returns_none_when_no_linearization() -> None:
    parser = _bare_parser()
    _set_lin(parser, None)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


def test_read_hint_stream_decoded_returns_none_when_h_array_missing() -> None:
    parser = _bare_parser()
    lin = COSDictionary()  # no /H entry at all
    _set_lin(parser, lin)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


def test_read_hint_stream_decoded_returns_none_when_h0_wrong_type() -> None:
    parser = _bare_parser()
    h_arr = COSArray()
    h_arr.add(COSName.get_pdf_name("oops"))
    h_arr.add(COSInteger.get(200))
    lin = _lin_dict(n=None, h_array=h_arr)
    _set_lin(parser, lin)
    # Line 475: h_off_obj wrong type.
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


def test_read_hint_stream_decoded_returns_none_when_xref_no_match() -> None:
    parser = _bare_parser()
    lin = _lin_dict(n=None, h_array=_h_array(123456789, 0))
    _set_lin(parser, lin)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


# ---------- _hint_subtable_offset early-exits ----------


def test_hint_subtable_offset_returns_none_when_no_linearization() -> None:
    parser = _bare_parser()
    _set_lin(parser, None)
    assert parser._hint_subtable_offset(2) is None  # noqa: SLF001


def test_hint_subtable_offset_returns_none_when_slot_wrong_type() -> None:
    parser = _bare_parser()
    h_arr = COSArray()
    h_arr.add(COSInteger.get(0))
    h_arr.add(COSInteger.get(0))
    h_arr.add(COSName.get_pdf_name("non-numeric"))  # slot 2 wrong type
    lin = _lin_dict(n=None, h_array=h_arr)
    _set_lin(parser, lin)
    assert parser._hint_subtable_offset(2) is None  # noqa: SLF001


def test_hint_subtable_offset_returns_none_when_value_negative() -> None:
    parser = _bare_parser()
    h_arr = _h_array(0, 0, -5)
    lin = _lin_dict(n=None, h_array=h_arr)
    _set_lin(parser, lin)
    assert parser._hint_subtable_offset(2) is None  # noqa: SLF001


def test_hint_subtable_offset_accepts_cosfloat_value() -> None:
    """Cover the COSFloat branch of the isinstance check (lines 519-521)."""
    parser = _bare_parser()
    h_arr = COSArray()
    h_arr.add(COSInteger.get(0))
    h_arr.add(COSInteger.get(0))
    h_arr.add(COSFloat(42.0))
    lin = _lin_dict(n=None, h_array=h_arr)
    _set_lin(parser, lin)
    assert parser._hint_subtable_offset(2) == 42  # noqa: SLF001


# ---------- shared / thumbnail decode early-exits ----------


def test_decode_shared_object_hint_table_returns_none_when_no_hint_stream() -> None:
    """Lines 558-559 path: ``decoded`` is ``None`` → early return."""
    parser = _bare_parser()
    _set_lin(parser, None)
    assert parser.decode_shared_object_hint_table() is None


def test_decode_thumbnail_hint_table_returns_none_when_no_hint_stream() -> None:
    """Lines 584/590-591 path: ``decoded`` is ``None`` → early return."""
    parser = _bare_parser()
    _set_lin(parser, None)
    assert parser.decode_thumbnail_hint_table() is None


# ---------- end-to-end: decode_page_offset with broken hint stream body ----------


def _build_page_offset_header() -> bytes:
    return struct.pack(
        ">IIHIHIHIHHH",
        5,    # least_objects
        1000, # first_page_offset
        0,    # bits_object_delta
        200,  # least_page_len
        0,    # bits_page_len_delta
        50,   # least_content_off
        0,    # bits_content_off_delta
        100,  # least_content_len
        0,    # bits_content_len_delta
        0,    # bits_shared_count
        0,    # bits_shared_id
    )


def _build_lin_pdf_with_corrupted_hint(hint_body: bytes) -> bytes:
    """Linearized PDF whose hint stream body is a deliberately broken
    blob — the FlateDecode succeeds but parse_page_offset_hint_table
    raises HintTableParseError, hitting line 452-453."""
    compressed = zlib.compress(hint_body)
    h_len = len(compressed)

    def _lin_dict_bytes(primary_off: int) -> bytes:
        return (
            b"1 0 obj\n"
            b"<< /Linearized 1 "
            b"/L 1000 "
            b"/H [" + f"{primary_off:010d}".encode("ascii") + b" "
            + f"{h_len:010d}".encode("ascii") + b"] "
            b"/O 4 "
            b"/E 0 "
            b"/N 1 "
            b"/T 0 "
            b">>\nendobj\n"
        )

    out = bytearray()
    out += b"%PDF-1.7\n"
    stub = _lin_dict_bytes(0)
    out += stub
    hint_dict = (
        b"2 0 obj\n"
        b"<< /Length " + str(len(compressed)).encode("ascii") + b" "
        b"/Filter /FlateDecode >>\nstream\n"
    )
    obj2_off = len(out)
    out += hint_dict
    out += compressed + b"\nendstream\nendobj\n"
    obj3 = len(out)
    out += b"3 0 obj\n<< /Type /Catalog /Pages 4 0 R >>\nendobj\n"
    obj4 = len(out)
    out += b"4 0 obj\n<< /Type /Pages /Kids [5 0 R] /Count 1 >>\nendobj\n"
    obj5 = len(out)
    out += b"5 0 obj\n<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    patched = _lin_dict_bytes(obj2_off)
    assert len(patched) == len(stub)
    start = out.index(b"1 0 obj\n")
    out[start : start + len(stub)] = patched
    xref_off = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in (start, obj2_off, obj3, obj4, obj5):
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 3 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_decode_page_offset_returns_none_on_parse_failure() -> None:
    """Lines 448-449 + 452-453: the body decodes (FlateDecode succeeds)
    but ``parse_page_offset_hint_table`` raises ``HintTableParseError``
    because the body is too short for the declared header → ``None``."""
    pdf = _build_lin_pdf_with_corrupted_hint(b"\x00\x00")  # 2-byte body, header needs 32
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.parse()
    assert parser.is_linearized() is True
    assert parser.decode_page_offset_hint_table() is None


def test_decode_shared_returns_none_when_h2_beyond_body() -> None:
    """Lines 554/555: shared offset >= len(decoded) → early return."""
    # Build a tiny linearized PDF whose hint body is short and whose
    # /H[2] points past the body end.
    page_off = _build_page_offset_header()
    compressed = zlib.compress(page_off)
    h_len = len(compressed)

    def _lin_dict_bytes(primary_off: int) -> bytes:
        return (
            b"1 0 obj\n"
            b"<< /Linearized 1 "
            b"/L 1000 "
            b"/H [" + f"{primary_off:010d}".encode("ascii") + b" "
            + f"{h_len:010d}".encode("ascii") + b" "
            b"0000999999 "  # H[2] far past body end (uncompressed body is 32 bytes)
            b"] "
            b"/O 4 "
            b"/E 0 "
            b"/N 1 "
            b"/T 0 "
            b">>\nendobj\n"
        )

    out = bytearray()
    out += b"%PDF-1.7\n"
    stub = _lin_dict_bytes(0)
    out += stub
    obj2 = len(out)
    out += (
        b"2 0 obj\n<< /Length " + str(len(compressed)).encode("ascii") + b" "
        b"/Filter /FlateDecode >>\nstream\n"
    )
    out += compressed + b"\nendstream\nendobj\n"
    obj3 = len(out)
    out += b"3 0 obj\n<< /Type /Catalog /Pages 4 0 R >>\nendobj\n"
    obj4 = len(out)
    out += b"4 0 obj\n<< /Type /Pages /Kids [5 0 R] /Count 1 >>\nendobj\n"
    obj5 = len(out)
    out += b"5 0 obj\n<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    patched = _lin_dict_bytes(obj2)
    assert len(patched) == len(stub)
    start = out.index(b"1 0 obj\n")
    out[start : start + len(stub)] = patched
    xref_off = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in (start, obj2, obj3, obj4, obj5):
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 3 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"

    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    parser.parse()
    assert parser.decode_shared_object_hint_table() is None


# ---------- raw stream-error coverage: lines 448-449 / 498-499 ----------


class _BoomStream(COSStream):
    """COSStream whose ``create_input_stream`` raises OSError on read."""

    def create_input_stream(self) -> object:  # type: ignore[override]
        raise OSError("boom: simulated I/O failure during hint read")


def _make_parser_with_hint_pointing_at_stream(stream: COSStream, offset: int) -> PDFParser:
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    doc = COSDocument()
    parser._document = doc  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), offset)
    # Stash the stream as a fake "object" the document can return.
    cos_object_for_stream = doc.get_object_from_pool(COSObjectKey(2, 0))
    cos_object_for_stream.set_object(stream)
    return parser


def test_decode_page_offset_returns_none_on_stream_io_error() -> None:
    """Lines 448-449 — ``create_input_stream`` raises OSError."""
    stream = _BoomStream()
    parser = _make_parser_with_hint_pointing_at_stream(stream, 5000)
    lin = _lin_dict(n=1, h_array=_h_array(5000, 200))
    _set_lin(parser, lin)
    assert parser.decode_page_offset_hint_table() is None


def test_read_hint_stream_decoded_returns_none_on_stream_io_error() -> None:
    """Lines 498-499 — same stream OSError, exercised via the shared decode entry."""
    stream = _BoomStream()
    parser = _make_parser_with_hint_pointing_at_stream(stream, 6000)
    lin = _lin_dict(n=None, h_array=_h_array(6000, 200))
    _set_lin(parser, lin)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


# ---------- non-COSStream resolved target (line 442-443 / 492-494) ----------


def test_decode_page_offset_returns_none_when_target_is_not_stream() -> None:
    """Line 442-443: resolved object is a COSDictionary, not a COSStream."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 7777)
    parser._document.get_object_from_pool(COSObjectKey(2, 0)).set_object(  # noqa: SLF001
        COSDictionary()
    )
    lin = _lin_dict(n=1, h_array=_h_array(7777, 200))
    _set_lin(parser, lin)
    assert parser.decode_page_offset_hint_table() is None


def test_read_hint_stream_decoded_returns_none_when_target_is_not_stream() -> None:
    """Line 492-494 mirror."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 8888)
    parser._document.get_object_from_pool(COSObjectKey(2, 0)).set_object(  # noqa: SLF001
        COSDictionary()
    )
    lin = _lin_dict(n=None, h_array=_h_array(8888, 200))
    _set_lin(parser, lin)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


def test_decode_page_offset_returns_none_when_target_obj_missing_from_document() -> None:
    """Line 440 — ``document.get_object(target_key)`` returns ``None``.
    The xref carries the entry, the document is not None, but the object
    pool hasn't seen the key yet."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 9999)
    # Do NOT register the object in the pool → get_object returns None.
    lin = _lin_dict(n=1, h_array=_h_array(9999, 200))
    _set_lin(parser, lin)
    assert parser.decode_page_offset_hint_table() is None


def test_read_hint_stream_decoded_returns_none_when_target_obj_missing() -> None:
    """Line 491 mirror."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 4444)
    lin = _lin_dict(n=None, h_array=_h_array(4444, 200))
    _set_lin(parser, lin)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


def test_read_hint_stream_decoded_returns_none_when_document_missing() -> None:
    """Line 488 — ``self._document is None`` in ``_read_hint_stream_decoded``."""
    parser = _bare_parser()
    _seed_xref(parser, COSObjectKey(2, 0), 1234)
    parser._document = None  # noqa: SLF001
    lin = _lin_dict(n=None, h_array=_h_array(1234, 200))
    _set_lin(parser, lin)
    assert parser._read_hint_stream_decoded() is None  # noqa: SLF001


def test_decode_shared_object_when_h2_missing_returns_none() -> None:
    """Lines 558-559 — the decoder builds a body but ``/H[2]`` is missing
    so ``_hint_subtable_offset(2)`` returns ``None``."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    # Build a tiny COSStream whose body is non-empty.
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\x00" * 64)
    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 555)
    parser._document.get_object_from_pool(COSObjectKey(2, 0)).set_object(  # noqa: SLF001
        stream
    )
    # /H[2] missing — only two slots in the array.
    lin = _lin_dict(n=None, h_array=_h_array(555, 64))
    _set_lin(parser, lin)
    assert parser.decode_shared_object_hint_table() is None


def test_decode_thumbnail_when_h3_missing_returns_none() -> None:
    """Lines 590-591 — same shape, ``/H[3]`` missing."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\x00" * 64)
    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 666)
    parser._document.get_object_from_pool(COSObjectKey(2, 0)).set_object(  # noqa: SLF001
        stream
    )
    lin = _lin_dict(n=None, h_array=_h_array(666, 64))
    _set_lin(parser, lin)
    assert parser.decode_thumbnail_hint_table() is None


def test_decode_shared_object_when_body_malformed_returns_none() -> None:
    """Lines 558-559 — body slice is too short for the Shared Object
    header → parse_shared_object_hint_table raises HintTableParseError."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    # Decoded body must be at least h2_offset + a little, but the slice
    # past offset must be shorter than 24 bytes (the shared header size).
    body = b"\x00" * 32  # 32 bytes total
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(body)
    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 777)
    parser._document.get_object_from_pool(COSObjectKey(2, 0)).set_object(  # noqa: SLF001
        stream
    )
    # /H[2] = 16 — leaves only 16 bytes of body, not enough for the 24-
    # byte header.
    lin = _lin_dict(n=None, h_array=_h_array(777, 32, 16))
    _set_lin(parser, lin)
    assert parser.decode_shared_object_hint_table() is None


def test_decode_thumbnail_when_body_malformed_returns_none() -> None:
    """Lines 590-591 — body slice too short for Thumbnail header (20 bytes)."""
    parser = _bare_parser()
    from pypdfbox.cos import COSDocument

    body = b"\x00" * 32
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(body)
    parser._document = COSDocument()  # noqa: SLF001
    _seed_xref(parser, COSObjectKey(2, 0), 888)
    parser._document.get_object_from_pool(COSObjectKey(2, 0)).set_object(  # noqa: SLF001
        stream
    )
    # /H[3] = 20 — leaves 12 bytes after offset, not enough for the 20-
    # byte thumbnail header.
    lin = _lin_dict(n=None, h_array=_h_array(888, 32, 0, 20))
    _set_lin(parser, lin)
    assert parser.decode_thumbnail_hint_table() is None
