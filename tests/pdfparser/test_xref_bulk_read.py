"""Bulk-read fast paths of the xref loader must be indistinguishable from the
per-byte reader logic they replace.

* ``_read_xref_rows_fast`` decodes traditional xref rows from block reads; the
  per-row ``skip_whitespace`` / peek / ``_read_xref_entry`` loop is kept for
  the rows it defers on. Every case is parsed twice (fast path on, and forced
  off) and must leave the same entries, recovery flag, trailer and cursor.
* ``_find_bad_xref_offsets`` validates all offsets from sorted block reads and
  must agree with the per-entry ``_object_header_matches``.
* In-use rows with offset 0 are skipped, as upstream ``parseXrefTable`` does
  (oracle-confirmed on ``eu-001.pdf``).
"""
import logging
from pathlib import Path

import pytest

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_buffered_file import (
    RandomAccessReadBufferedFile,
)
from pypdfbox.pdfparser import pdf_parser as pdf_parser_module
from pypdfbox.pdfparser.cos_parser import COSParser
from pypdfbox.pdfparser.pdf_parser import PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import XrefEntry, XrefType
from pypdfbox.pdmodel.pd_document import PDDocument

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _parse_section(data: bytes, *, fast: bool, monkeypatch) -> tuple:
    if not fast:
        monkeypatch.setattr(
            PDFParser, "_read_xref_rows_fast", lambda self, first, count: 0
        )
    parser = PDFParser(RandomAccessReadBuffer(bytearray(data)))
    parser._cos_parser = COSParser(parser._src)
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    try:
        parser._parse_traditional_xref_section()
        error = None
    except Exception as exc:
        error = (type(exc), str(exc))
    entries = sorted(
        (k.object_number, k.generation_number, e.offset, e.compressed_index)
        for k, e in resolver.get_xref_table().items()
    )
    trailer = resolver.get_trailer()
    size = trailer.get_int("Size") if trailer is not None else None
    monkeypatch.undo()
    return (
        entries,
        parser._xref_table_recovery_needed,
        size,
        parser._src.get_position(),
        error,
    )


def _rows(n: int, eol: bytes = b" \n", start: int = 100) -> bytes:
    return b"".join(
        b"%010d 00000 n" % (start + 10 * i) + eol for i in range(n)
    )


TRAILER = b"trailer\n<< /Size 99 >>\n"

SECTIONS: dict[str, bytes] = {
    "lf_space": b"xref\n0 4\n0000000000 65535 f \n" + _rows(3) + TRAILER,
    "crlf": b"xref\r\n0 3\r\n" + _rows(3, b"\r\n") + TRAILER,
    "cr_only": b"xref\r0 3\r" + _rows(3, b"\r") + TRAILER,
    "lf_only": b"xref\n0 3\n" + _rows(3, b"\n") + TRAILER,
    "space_cr": b"xref\n0 3\n" + _rows(3, b" \r") + TRAILER,
    "two_subsections": (
        b"xref\n0 2\n" + _rows(2) + b"10 2\n" + _rows(2, start=900) + TRAILER
    ),
    "comment_between_rows": (
        b"xref\n0 3\n" + _rows(1) + b"% note\n" + _rows(2, start=500) + TRAILER
    ),
    "count_too_long": b"xref\n0 9\n" + _rows(3) + TRAILER,
    "count_too_short": b"xref\n0 2\n" + _rows(4) + TRAILER,
    "unknown_flag": (
        b"xref\n0 3\n" + _rows(1) + b"0000000200 00000 q \n" + _rows(1)
        + TRAILER
    ),
    "too_many_fields": (
        b"xref\n0 3\n" + _rows(1) + b"0000000200 00000 n x\n" + _rows(1)
        + TRAILER
    ),
    "non_numeric": (
        b"xref\n0 2\n" + _rows(1) + b"00000002x0 00000 n \n" + TRAILER
    ),
    "zero_offset_in_use": (
        b"xref\n0 3\n0000000000 00000 n \n" + _rows(2) + TRAILER
    ),
    "zero_offset_gen_65536": (
        b"xref\n0 3\n" + _rows(1) + b"0000000000 65536 n \n" + _rows(1)
        + TRAILER
    ),
    "rows_to_eof_no_trailer": b"xref\n0 3\n" + _rows(3),
    "last_row_no_eol_at_eof": b"xref\n0 2\n" + _rows(1) + b"0000000300 00000 n",
    "whitespace_to_eof": b"xref\n0 3\n" + _rows(1) + b"   \n\n  ",
    "nul_and_ff_whitespace": (
        b"xref\n0 3\n" + _rows(1) + b"\x00\x0c" + _rows(2) + TRAILER
    ),
    "large_table": b"xref\n0 3000\n" + _rows(3000) + TRAILER,
}


@pytest.mark.parametrize("name", list(SECTIONS), ids=list(SECTIONS))
@pytest.mark.parametrize("block", [1 << 20, 23, 41, 64])
def test_fast_rows_match_per_byte_reader(name: str, block: int, monkeypatch) -> None:
    # Small blocks force rows, CR/LF pairs and whitespace runs to straddle
    # block boundaries, exercising every refill / defer branch.
    data = SECTIONS[name]
    monkeypatch.setattr(pdf_parser_module, "_BULK_READ_BLOCK", block)
    fast = _parse_section(data, fast=True, monkeypatch=monkeypatch)
    monkeypatch.setattr(pdf_parser_module, "_BULK_READ_BLOCK", block)
    slow = _parse_section(data, fast=False, monkeypatch=monkeypatch)
    assert fast == slow


def test_zero_offset_in_use_rows_are_not_registered(monkeypatch) -> None:
    entries, *_ = _parse_section(
        SECTIONS["zero_offset_in_use"], fast=True, monkeypatch=monkeypatch
    )
    assert [e[0] for e in entries] == [1, 2]


def test_read_xref_entry_skips_zero_offset() -> None:
    parser = PDFParser(RandomAccessReadBuffer(bytearray(b"0000000000 00000 n \n")))
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    parser._read_xref_entry(3)
    assert resolver.get_xref_table() == {}
    assert parser._src.get_position() == 20


def _pdf_with_objects(count: int) -> tuple[bytes, list[int]]:
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n in range(1, count + 1):
        offsets.append(len(out))
        if n == 1:
            out += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        elif n == 2:
            out += b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
        else:
            out += b"%d 0 obj\n(object %d)\nendobj\n" % (n, n)
    return bytes(out), offsets


def _with_xref(body: bytes, offsets: list[int]) -> bytes:
    xref_at = len(body)
    table = b"xref\n0 %d\n0000000000 65535 f \n" % (len(offsets) + 1)
    table += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    trailer = b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(offsets) + 1,
        xref_at,
    )
    return body + table + trailer


@pytest.mark.parametrize("block", [1 << 20, 64, 70, 97])
def test_find_bad_offsets_matches_per_entry_check(block: int, monkeypatch) -> None:
    body, offsets = _pdf_with_objects(40)
    bad_offsets = list(offsets)
    bad_offsets[5] += 3  # into the middle of a header
    bad_offsets[9] -= 1  # the preceding newline: whitespace-tolerant accept
    bad_offsets[12] = offsets[13]  # another object's header
    bad_offsets[20] = len(body) + 500  # past EOF
    bad_offsets[30] = len(body) - 2  # header window truncated by EOF
    data = _with_xref(body, bad_offsets)
    parser = PDFParser(RandomAccessReadBuffer(bytearray(data)))
    xref = {
        COSObjectKey(i + 1, 0): XrefEntry(type=XrefType.TABLE, offset=o)
        for i, o in enumerate(bad_offsets)
    }
    xref[COSObjectKey(99, 0)] = XrefEntry(type=XrefType.COMPRESSED, offset=7)
    xref[COSObjectKey(98, 0)] = XrefEntry(
        type=XrefType.TABLE, offset=0, compressed_index=-1
    )
    parser._src.seek(17)
    monkeypatch.setattr(pdf_parser_module, "_BULK_READ_BLOCK", block)
    bad = parser._find_bad_xref_offsets(xref)
    assert parser._src.get_position() == 17
    expected = {
        key
        for key, entry in xref.items()
        if entry.type is XrefType.TABLE
        and entry.compressed_index != -1
        and not parser._object_header_matches(entry.offset, key)
    }
    assert bad == expected
    assert {k.object_number for k in bad} == {6, 13, 21, 31}


def test_bad_offsets_are_repaired_from_file_source(tmp_path: Path) -> None:
    body, offsets = _pdf_with_objects(12)
    bad_offsets = list(offsets)
    bad_offsets[4] += 2
    bad_offsets[7] = offsets[8]
    path = tmp_path / "bad_offsets.pdf"
    path.write_bytes(_with_xref(body, bad_offsets))
    doc = PDDocument.load(str(path))
    try:
        table = doc.get_document().get_xref_table()
        assert table[COSObjectKey(5, 0)] == offsets[4]
        assert table[COSObjectKey(8, 0)] == offsets[7]
        obj = doc.get_document().get_object_from_pool(COSObjectKey(8, 0))
        assert obj.get_object().get_string() == "object 8"
    finally:
        doc.close()


def test_file_source_and_memory_source_agree(tmp_path: Path) -> None:
    body, offsets = _pdf_with_objects(30)
    bad_offsets = list(offsets)
    bad_offsets[3] += 5
    data = _with_xref(body, bad_offsets)
    path = tmp_path / "agree.pdf"
    path.write_bytes(data)
    file_src = RandomAccessReadBufferedFile(path)
    try:
        doc_file = PDFParser(file_src).parse()
        from_file = dict(doc_file.get_xref_table())
    finally:
        file_src.close()
    doc_mem = PDFParser(RandomAccessReadBuffer(bytearray(data))).parse()
    assert from_file == dict(doc_mem.get_xref_table())
    assert from_file[COSObjectKey(4, 0)] == offsets[3]


def test_eu001_zero_offset_rows_absent_and_no_errors(caplog) -> None:
    # Upstream PDFBox 3.0.8 (live oracle): rows 2, 37 and 41 carry
    # "0000000000 65536 n"; parseXrefTable skips 0 offsets, so the keys are
    # absent from the xref table and nothing is logged as an error.
    path = _FIXTURES / "text" / "input" / "eu-001.pdf"
    with caplog.at_level(logging.ERROR):
        doc = PDDocument.load(str(path))
        try:
            numbers = {
                k.object_number for k in doc.get_document().get_xref_table()
            }
            assert not numbers & {2, 37, 41}
            assert len(numbers) == 43
            cos_doc = doc.get_document()
            for key in list(cos_doc.get_xref_table()):
                assert cos_doc.get_object_from_pool(key).get_object() is not None
            assert doc.get_number_of_pages() == 3
        finally:
            doc.close()
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
