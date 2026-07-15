"""Fast `_object_header_matches` (bulk read + in-memory scanner) must return
byte-for-byte the same verdict as the original per-byte reader logic, which is
retained verbatim as `_object_header_matches_slow`.

The fast scanner replaced ~15 per-byte reader calls per xref entry with a
single bulk read; `_check_xref_offsets_lenient` calls it for every table entry
on every lenient load, so any divergence would change xref-recovery decisions.
These tests pin the accept/reject/EOF/comment/sign semantics.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_parser import PDFParser


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(bytearray(data)))


# (body, object_number, expected verdict) — expected is what the ORIGINAL
# per-byte logic returns; the fast path must agree.
CASES: list[tuple[bytes, int, bool]] = [
    (b"12 0 obj\n", 12, True),
    (b"12  0  obj ", 12, True),          # extra whitespace between tokens
    (b"12\t0\robj ", 12, True),          # tab + CR as inter-token whitespace
    (b"12\n0\nobj ", 12, True),          # LF whitespace
    (b"\x00\t 12 0 obj ", 12, True),     # leading NUL/tab/space whitespace
    (b"12 0obj ", 12, True),             # zero whitespace before 'obj' (accepted)
    (b"120obj ", 12, False),             # single int then obj -> reject
    (b"120obj ", 120, False),            # "120" is the object number, no gen
    (b"12 0 xyz ", 12, False),           # wrong keyword
    (b"12 0 objfoo ", 12, False),        # 'objfoo' token != 'obj'
    (b"13 0 obj ", 12, False),           # object-number mismatch
    (b"12 0 obj", 12, True),             # header ends exactly at EOF
    (b"12 0 ob", 12, False),             # truncated keyword at EOF -> reject
    (b"999999 65535 obj ", 999999, True),
    (b"", 12, False),                    # empty buffer
    (b"   ", 12, False),                 # whitespace only -> EOF
    (b"xyz", 12, False),                 # non-digit start
    (b"12", 12, False),                  # single int at EOF
    (b"12 0", 12, False),                # two ints, no keyword, EOF
    # Fallback-to-slow inputs: comments and signed integers.
    (b"%hdr\n12 0 obj ", 12, True),      # leading '%' comment
    (b"+12 0 obj ", 12, True),           # signed object number
    (b"-12 0 obj ", 12, False),          # negative number never equals 12
    (b"12 +0 obj ", 12, True),           # signed generation
    (b"12 -0 obj ", 12, True),           # negative-zero generation still 'obj'
]


@pytest.mark.parametrize(
    "body,onum,expected",
    CASES,
    ids=[repr(c[0])[2:-1][:24] or "empty" for c in CASES],
)
def test_fast_matches_slow_and_expected(
    body: bytes, onum: int, expected: bool
) -> None:
    p = _parser(body)
    key = COSObjectKey(onum, 0)
    fast = p._object_header_matches(0, key)
    slow = p._object_header_matches_slow(0, key)
    assert fast == slow, f"fast/slow diverge for {body!r}"
    assert fast is expected


def test_out_of_range_offsets() -> None:
    p = _parser(b"12 0 obj\n")
    key = COSObjectKey(12, 0)
    assert p._object_header_matches(-1, key) is False
    assert p._object_header_matches(9999, key) is False
    # both guards mirror the slow method
    assert p._object_header_matches_slow(-1, key) is False
    assert p._object_header_matches_slow(9999, key) is False


def test_near_eof_short_bulk_read() -> None:
    # Header sits so the bulk-read window runs off the end of the file: the
    # scanner must reach the same verdict as the reader hitting EOF.
    data = b"........12 0 obj"
    p = _parser(data)
    key = COSObjectKey(12, 0)
    assert (
        p._object_header_matches(8, key)
        == p._object_header_matches_slow(8, key)
        is True
    )


def test_offset_sweep_parity_on_fixture() -> None:
    # Exhaustive: every byte offset x several candidate object numbers, fast
    # must equal slow. Uses a small synthetic multi-object body so the sweep is
    # cheap but exercises real inter-object boundaries.
    body = bytearray()
    offs = []
    for i in range(6):
        offs.append(len(body))
        body += f"{i} 0 obj\n<< /N {i} >>\nendobj\n".encode()
    p = _parser(bytes(body))
    for off in range(len(body) + 2):
        for onum in (0, 1, 2, 5, 12):
            key = COSObjectKey(onum, 0)
            assert p._object_header_matches(off, key) == (
                p._object_header_matches_slow(off, key)
            ), f"off={off} onum={onum}"
