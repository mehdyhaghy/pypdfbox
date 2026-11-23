"""Bulk (column-wise) xref-stream decoding must match a record-by-record walk:
same entries, same insertion order, same keep/replace rules, same errors."""

import random

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser
from pypdfbox.pdfparser.xref_trailer_resolver import (
    XrefEntry,
    XrefTrailerResolver,
    XrefType,
)


def _stream(
    widths: list[int], raw: bytes, index: list[int] | None, size: int | None = None
) -> COSStream:
    stream = COSStream()
    w = COSArray()
    for width in widths:
        w.add(COSInteger.get(width))
    stream.set_item("W", w)
    if index is not None:
        arr = COSArray()
        for value in index:
            arr.add(COSInteger.get(value))
        stream.set_item("Index", arr)
    if size is not None:
        stream.set_item("Size", COSInteger.get(size))
    stream.set_raw_data(raw)
    return stream


def _reference_decode(
    resolver: XrefTrailerResolver,
    widths: list[int],
    body: bytes,
    pairs: list[tuple[int, int]],
) -> bool:
    """The record-by-record decode; returns True when it hit truncation."""
    w1, w2, w3 = widths
    rs = w1 + w2 + w3
    cursor = 0
    for first, count in pairs:
        for i in range(count):
            if cursor + rs > len(body):
                return True
            rec = body[cursor : cursor + rs]
            cursor += rs
            f1 = 1 if w1 == 0 else int.from_bytes(rec[0:w1], "big")
            f2 = int.from_bytes(rec[w1 : w1 + w2], "big")
            f3 = 0 if w3 == 0 else int.from_bytes(rec[w1 + w2 : rs], "big")
            num = first + i
            if f1 == 0:
                resolver.set_stream_entry(
                    COSObjectKey(num, f3), XrefEntry(XrefType.STREAM, f2, -1)
                )
            elif f1 == 1:
                resolver.set_stream_entry(
                    COSObjectKey(num, f3), XrefEntry(XrefType.STREAM, f2)
                )
            elif f1 == 2:
                resolver.set_stream_entry(
                    COSObjectKey(num, 0), XrefEntry(XrefType.COMPRESSED, f2, f3)
                )
            else:
                resolver.set_stream_entry(
                    COSObjectKey(num, 0), XrefEntry(XrefType.STREAM, 0, -1)
                )
    return False


def _table(resolver: XrefTrailerResolver) -> list[tuple[int, int, XrefEntry]]:
    return [
        (k.get_number(), k.get_generation(), v)
        for k, v in resolver.get_xref_table().items()
    ]


def _seed(resolver: XrefTrailerResolver) -> None:
    # Pre-existing entries, as in a hybrid file's table section.
    resolver.set_entry(COSObjectKey(1, 0), XrefEntry(XrefType.TABLE, 111))
    resolver.set_entry(COSObjectKey(3, 0), XrefEntry(XrefType.TABLE, 333, -1))


def _check(
    widths: list[int],
    body: bytes,
    index: list[int] | None,
    size: int | None = None,
    seed: bool = False,
) -> None:
    pairs = (
        [(index[i], index[i + 1]) for i in range(0, len(index), 2)]
        if index is not None
        else [(0, size or 0)]
    )
    ref = XrefTrailerResolver()
    ref.begin_section(0)
    if seed:
        _seed(ref)
    ref_truncated = _reference_decode(ref, widths, body, pairs)

    parser = PDFParser(RandomAccessReadBuffer(b""))
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    if seed:
        _seed(resolver)
    stream = _stream(widths, body, index, size)
    if ref_truncated:
        with pytest.raises(PDFParseError, match="truncated"):
            parser._decode_xref_stream_entries(stream)
    else:
        parser._decode_xref_stream_entries(stream)
    assert _table(resolver) == _table(ref)


WIDTHS = [
    [1, 2, 1],
    [1, 3, 2],
    [1, 4, 2],
    [0, 3, 0],
    [0, 2, 1],
    [1, 0, 1],
    [2, 2, 0],
    [1, 5, 1],
    [1, 8, 2],
    [1, 9, 3],
    [3, 7, 3],
    [1, 1, 0],
]


@pytest.mark.parametrize("widths", WIDTHS, ids=["-".join(map(str, w)) for w in WIDTHS])
@pytest.mark.parametrize("seed", [False, True], ids=["fresh", "hybrid"])
def test_bulk_decode_matches_record_walk(widths: list[int], seed: bool) -> None:
    rng = random.Random(sum(widths) * 31 + len(widths) + seed)
    rs = sum(widths)
    for _ in range(20):
        layout = rng.choice(["size", "one", "many", "overlap"])
        if layout == "size":
            index, size = None, rng.randrange(0, 12)
            total = size
        elif layout == "one":
            index, size = [rng.randrange(0, 5), rng.randrange(0, 12)], None
            total = index[1]
        elif layout == "many":
            index = [0, 3, 10, 0, 20, 4, 7, 2]
            size, total = None, 9
        else:
            # Overlapping subsections produce duplicate keys.
            index, size = [0, 5, 2, 5, 4, 3], None
            total = 13
        n = total - rng.randrange(0, 3) if rng.random() < 0.3 else total
        raw = bytearray()
        for _rec in range(max(n, 0)):
            rec = bytearray(rng.randrange(256) for _b in range(rs))
            if widths[0]:
                kind = rng.choice([0, 1, 1, 2, 2, 3, 255])
                rec[0 : widths[0]] = kind.to_bytes(widths[0], "big")
            raw += rec
        if rng.random() < 0.2 and raw:
            raw = raw[: -rng.randrange(1, rs + 1)]  # ragged tail
        _check(widths, bytes(raw), index, size, seed)


def test_zero_width_fields_default_type_one_and_generation_zero() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b""))
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    parser._decode_xref_stream_entries(
        _stream([0, 2, 0], b"\x00\x10\x01\x00", [5, 2])
    )
    assert _table(resolver) == [
        (5, 0, XrefEntry(XrefType.STREAM, 0x10)),
        (6, 0, XrefEntry(XrefType.STREAM, 0x100)),
    ]


def test_multiple_index_subsections_number_objects_in_order() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b""))
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    body = b"\x01\x00\x0a\x00" b"\x02\x00\x07\x03" b"\x00\x00\x00\x01"
    parser._decode_xref_stream_entries(_stream([1, 2, 1], body, [4, 1, 9, 2]))
    assert _table(resolver) == [
        (4, 0, XrefEntry(XrefType.STREAM, 10)),
        (9, 0, XrefEntry(XrefType.COMPRESSED, 7, 3)),
        (10, 1, XrefEntry(XrefType.STREAM, 0, -1)),
    ]


def test_truncated_body_keeps_complete_records_then_raises() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b""))
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    body = b"\x01\x00\x0a\x00" b"\x01\x00\x0b"  # second record is short
    with pytest.raises(PDFParseError, match="truncated"):
        parser._decode_xref_stream_entries(_stream([1, 2, 1], body, [0, 3]))
    assert _table(resolver) == [(0, 0, XrefEntry(XrefType.STREAM, 10))]


def test_duplicate_rows_first_in_use_wins_over_later_rows() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b""))
    resolver = parser.get_xref_trailer_resolver()
    resolver.begin_section(0)
    # obj 0 listed three times: free, in-use (replaces free), in-use (ignored).
    body = b"\x00\x00\x00\x00" b"\x01\x00\x20\x00" b"\x01\x00\x30\x00"
    parser._decode_xref_stream_entries(_stream([1, 2, 1], body, [0, 1, 0, 1, 0, 1]))
    assert _table(resolver) == [(0, 0, XrefEntry(XrefType.STREAM, 0x20))]


def test_set_stream_entries_matches_per_entry_calls() -> None:
    keys = [COSObjectKey(1, 0), COSObjectKey(2, 0), COSObjectKey(1, 0)]
    entries = [
        XrefEntry(XrefType.STREAM, 5, -1),
        XrefEntry(XrefType.STREAM, 6),
        XrefEntry(XrefType.STREAM, 7),
    ]
    bulk = XrefTrailerResolver()
    bulk.begin_section(0)
    bulk.set_stream_entries(keys, entries)
    single = XrefTrailerResolver()
    single.begin_section(0)
    for key, entry in zip(keys, entries, strict=True):
        single.set_stream_entry(key, entry)
    assert list(bulk.get_xref_table().items()) == list(single.get_xref_table().items())
    with pytest.raises(RuntimeError):
        XrefTrailerResolver().set_stream_entries([], [])
