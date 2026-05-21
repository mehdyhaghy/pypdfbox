"""Wave 1368 — traditional ``xref`` table free-list edge cases.

Covers spec corners that are easy to mis-handle when parsing PDF
32000-1 §7.5.4 cross-reference tables:

* The conventional ``0000000000 65535 f`` free-root sentinel.
* Free-list cycles (``n.n.f`` offsets pointing at another free slot).
* Generation-0 in-use entries adjacent to non-zero-gen free entries.
* Multiple subsections (e.g. ``0 1`` followed by ``5 2``) in one table.
* Older-style 20-byte entries with CRLF line endings.
"""

from __future__ import annotations

from pypdfbox.cos import COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser

_HEADER = b"%PDF-1.4\n"


def _parse(pdf: bytes):
    return PDFParser(RandomAccessReadBuffer(pdf)).parse()


def test_traditional_xref_free_root_sentinel_records_only_in_use() -> None:
    """Object 0 with generation 65535 is the free-list root; it must
    never be registered as a loadable object even though the line is
    syntactically valid."""
    out = bytearray(_HEADER)
    obj1_off = len(out)
    out += b"1 0 obj\n42\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = _parse(bytes(out))
    assert doc.has_object(COSObjectKey(1, 0))
    # The free root must not surface as a loadable key.
    assert not doc.has_object(COSObjectKey(0, 65535))


def test_xref_free_list_cycle_is_not_walked_as_in_use() -> None:
    """A circular free list (object 2 -> 3 -> 2) must not produce
    spurious pool entries. Free entries store the next-free object's
    number in the offset slot; the parser must treat them as free
    regardless of what that "next" value is."""
    out = bytearray(_HEADER)
    obj1_off = len(out)
    out += b"1 0 obj\n(only-in-use)\nendobj\n"
    xref_off = len(out)
    # 4 entries: object 0 (free root), 1 (in-use), 2 -> 3 (free),
    # 3 -> 2 (free, cycle).
    out += b"xref\n0 4\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    # Cycle: 2's offset points at 3, 3's offset points back at 2.
    out += b"0000000003 00001 f \n"
    out += b"0000000002 00001 f \n"
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = _parse(bytes(out))
    assert doc.has_object(COSObjectKey(1, 0))
    # Neither cycle node nor its peer should be loadable.
    assert not doc.has_object(COSObjectKey(2, 1))
    assert not doc.has_object(COSObjectKey(3, 1))


def test_generation_zero_in_use_with_nonzero_generation_free() -> None:
    """The generation column applies per-entry: a fresh-life object can
    sit on generation 0 while a recycled slot sits on a higher
    generation in the free list. Both must round-trip."""
    out = bytearray(_HEADER)
    obj_off = len(out)
    out += b"1 0 obj\n(alive)\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n"
    out += f"{obj_off:010d} 00000 n \n".encode("ascii")
    # Object 2 once existed, was freed at generation 7, will be reused
    # next as generation 8 — represent that with a non-zero-gen 'f' entry.
    out += b"0000000000 00007 f \n"
    out += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = _parse(bytes(out))
    assert doc.has_object(COSObjectKey(1, 0))
    # The freed slot must not be loadable on either generation 7 (free)
    # or generation 8 (would-be next allocation — not yet present).
    assert not doc.has_object(COSObjectKey(2, 7))
    assert not doc.has_object(COSObjectKey(2, 8))


def test_xref_with_two_subsections_disjoint_ranges() -> None:
    """``0 N`` then ``M K`` subsections register object numbers in
    distinct ranges. Both ranges must populate the pool."""
    out = bytearray(_HEADER)
    obj1_off = len(out)
    out += b"1 0 obj\n(low)\nendobj\n"
    obj10_off = len(out)
    out += b"10 0 obj\n(high)\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += b"10 1\n"
    out += f"{obj10_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 11 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = _parse(bytes(out))
    body1 = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    body10 = doc.get_object_from_pool(COSObjectKey(10, 0)).get_object()
    assert isinstance(body1, COSString) and body1.get_bytes() == b"low"
    assert isinstance(body10, COSString) and body10.get_bytes() == b"high"
    # Nothing in between must be reachable.
    for n in range(2, 10):
        assert not doc.has_object(COSObjectKey(n, 0))


def test_xref_with_crlf_line_endings() -> None:
    """The PDF spec mandates fixed-width 20-byte records — including a
    trailing CRLF terminator. The parser should accept that form as
    readily as the bare-LF compaction most producers emit."""
    out = bytearray(_HEADER)
    obj_off = len(out)
    out += b"1 0 obj\n(crlf)\nendobj\n"
    xref_off = len(out)
    # Standard 20-byte records with CRLF terminators.
    out += b"xref\r\n0 2\r\n"
    out += b"0000000000 65535 f \r\n"
    out += f"{obj_off:010d} 00000 n \r\n".encode("ascii")
    out += b"trailer\r\n<< /Size 2 /Root 1 0 R >>\r\n"
    out += b"startxref\r\n" + str(xref_off).encode("ascii") + b"\r\n%%EOF"
    doc = _parse(bytes(out))
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSString) and body.get_bytes() == b"crlf"


def test_xref_table_three_subsections_with_free_gaps() -> None:
    """Three subsections with a free entry interleaved — exercises the
    subsection loop's reset between blocks and the per-section free-
    list bookkeeping."""
    out = bytearray(_HEADER)
    obj1_off = len(out)
    out += b"1 0 obj\n(a)\nendobj\n"
    obj4_off = len(out)
    out += b"4 0 obj\n(d)\nendobj\n"
    obj7_off = len(out)
    out += b"7 0 obj\n(g)\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    # Subsection #2: object 4 in-use, object 5 free.
    out += b"4 2\n"
    out += f"{obj4_off:010d} 00000 n \n".encode("ascii")
    out += b"0000000000 00001 f \n"
    # Subsection #3: object 7 in-use.
    out += b"7 1\n"
    out += f"{obj7_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 8 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = _parse(bytes(out))
    for n in (1, 4, 7):
        assert doc.has_object(COSObjectKey(n, 0))
    # Gaps + free entries must not be loadable.
    for n in (2, 3, 5, 6):
        assert not doc.has_object(COSObjectKey(n, 0))
