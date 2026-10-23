"""Lenient xref offset check: upstream ``COSParser.checkXrefOffsets`` /
``findObjectKey`` / brute-force replacement semantics (PDFBox 3.0.8).

* One entry whose offset does not lead to its ``n g obj`` header (or is below
  6, or past EOF) replaces the WHOLE table with the brute-force object scan.
* Headers naming another object number or a higher generation re-key the
  entry instead.
* A valid table is left untouched.

Every case PDF is also compared with the live oracle
(``XrefOffsetCheckProbe``) in ``test_check_xref_offsets_oracle.py``.
"""
import pytest

from pypdfbox.cos import COSName, COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import pdf_parser as pdf_parser_module
from pypdfbox.pdfparser.cos_parser import (
    COSParser,
    _bf_search_for_objects_in,
    _ByteWindow,
    _find_object_key_in,
)
from pypdfbox.pdfparser.pdf_parser import PDFParser

_CATALOG = b"<< /Type /Catalog /Pages 2 0 R >>"
_PAGES = b"<< /Type /Pages /Kids [] /Count 0 >>"


def _body(objects: list[tuple[bytes, bytes]]) -> tuple[bytes, list[int]]:
    """``objects`` are ``(header, body)``; returns the file prefix and the
    offset of each header."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for header, body in objects:
        offsets.append(len(out))
        out += header + b"\n" + body + b"\nendobj\n"
    return bytes(out), offsets


def _with_table(
    prefix: bytes, rows: list[tuple[int, int, int]], extra_trailer: bytes = b""
) -> bytes:
    """Append a classic xref with one subsection per ``(num, offset, gen)``
    row, plus trailer and ``startxref``."""
    xref_at = len(prefix)
    table = bytearray(b"xref\n0 1\n0000000000 65535 f \n")
    for num, offset, gen in rows:
        table += f"{num} 1\n{offset:010d} {gen:05d} n \n".encode("ascii")
    size = max(num for num, _, _ in rows) + 1
    table += (
        f"trailer\n<< /Size {size} /Root 1 0 R ".encode("ascii")
        + extra_trailer
        + f">>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    return prefix + bytes(table)


def _table(data: bytes) -> dict[tuple[int, int], int]:
    doc = PDFParser(RandomAccessReadBuffer(bytearray(data))).parse()
    return {
        (k.object_number, k.generation_number): v
        for k, v in doc.get_xref_table().items()
    }


def _three_objects() -> tuple[bytes, list[int]]:
    return _body(
        [
            (b"1 0 obj", _CATALOG),
            (b"2 0 obj", _PAGES),
            (b"3 0 obj", b"(three)"),
            # In the body but not in the xref: only a brute-force scan sees it.
            (b"9 0 obj", b"(nine)"),
        ]
    )


def case_valid() -> bytes:
    prefix, off = _three_objects()
    return _with_table(prefix, [(1, off[0], 0), (2, off[1], 0), (3, off[2], 0)])


def case_one_shifted() -> bytes:
    prefix, off = _three_objects()
    return _with_table(
        prefix, [(1, off[0], 0), (2, off[1] + 3, 0), (3, off[2], 0)]
    )


def case_below_minimum() -> bytes:
    prefix, off = _three_objects()
    return _with_table(prefix, [(1, off[0], 0), (2, off[1], 0), (3, 5, 0)])


def case_past_eof() -> bytes:
    prefix, off = _three_objects()
    return _with_table(
        prefix, [(1, off[0], 0), (2, off[1], 0), (3, len(prefix) + 999, 0)]
    )


def case_points_at_preceding_newline() -> bytes:
    prefix, off = _three_objects()
    return _with_table(
        prefix, [(1, off[0], 0), (2, off[1] - 1, 0), (3, off[2], 0)]
    )


def case_inside_object_number() -> bytes:
    # Offset lands on the "2" of "12 0 obj": the digits before it belong to
    # an entry at a nearby offset, which upstream rejects.
    prefix, off = _body(
        [(b"1 0 obj", _CATALOG), (b"2 0 obj", _PAGES), (b"12 0 obj", b"(12)")]
    )
    return _with_table(
        prefix, [(1, off[0], 0), (2, off[1], 0), (12, off[2] + 1, 0)]
    )


def case_higher_generation() -> bytes:
    prefix, off = _body(
        [(b"1 0 obj", _CATALOG), (b"2 0 obj", _PAGES), (b"3 2 obj", b"(gen2)")]
    )
    return _with_table(prefix, [(1, off[0], 0), (2, off[1], 0), (3, off[2], 0)])


def case_other_object_number() -> bytes:
    prefix, off = _body(
        [(b"1 0 obj", _CATALOG), (b"2 0 obj", _PAGES), (b"4 0 obj", b"(four)")]
    )
    return _with_table(prefix, [(1, off[0], 0), (2, off[1], 0), (3, off[2], 0)])


def case_two_digit_generation_not_brute_forced() -> bytes:
    prefix, off = _body(
        [
            (b"1 0 obj", _CATALOG),
            (b"2 0 obj", _PAGES),
            (b"3 10 obj", b"(gen10)"),
            (b"4 0 obj", b"(four)"),
        ]
    )
    return _with_table(
        prefix,
        [(1, off[0], 0), (2, off[1], 0), (3, off[2], 10), (4, off[3] + 2, 0)],
    )


def case_objects_after_garbage_eof() -> bytes:
    prefix, off = _three_objects()
    data = _with_table(
        prefix, [(1, off[0], 0), (2, off[1] + 1, 0), (3, off[2], 0)]
    )
    # Garbage after the final %%EOF makes it the last EOF marker; the scan
    # stops there, so object 8 is not recovered.
    return data + b"garbage\n8 0 obj\n(eight)\nendobj\n"


def case_hybrid_table_wins_over_xrefstm() -> bytes:
    """A hybrid file whose /XRefStm re-lists object 3 at a different offset:
    the table entry must win (PDFBOX-3506), so the bad table offset triggers
    the brute-force replacement."""
    prefix, off = _three_objects()
    # xref stream: W [1 4 2], Index [3 1]: object 3 at its true offset.
    rec = b"\x01" + off[2].to_bytes(4, "big") + b"\x00\x00"
    stm_at = len(prefix)
    stm = (
        b"20 0 obj\n<< /Type /XRef /Size 21 /W [1 4 2] /Index [3 1] /Length "
        + str(len(rec)).encode("ascii")
        + b" >>\nstream\n"
        + rec
        + b"\nendstream\nendobj\n"
    )
    return _with_table(
        prefix + stm,
        [(1, off[0], 0), (2, off[1], 0), (3, off[2] + 4, 0)],
        extra_trailer=f"/XRefStm {stm_at} ".encode("ascii"),
    )


CASES = {
    name[5:]: fn
    for name, fn in sorted(globals().items())
    if name.startswith("case_") and callable(fn)
}


def test_valid_table_is_untouched() -> None:
    prefix, off = _three_objects()
    assert _table(case_valid()) == {(1, 0): off[0], (2, 0): off[1], (3, 0): off[2]}


@pytest.mark.parametrize(
    "case", ["one_shifted", "below_minimum", "past_eof", "inside_object_number"]
)
def test_one_bad_entry_replaces_whole_table_with_brute_force(case: str) -> None:
    prefix, off = _three_objects()
    table = _table(CASES[case]())
    # Object 9 is only reachable through the brute-force scan, so its
    # presence proves the whole table was replaced.
    if case == "inside_object_number":
        assert (12, 0) in table and (2, 0) in table
    else:
        assert table == {
            (1, 0): off[0],
            (2, 0): off[1],
            (3, 0): off[2],
            (9, 0): off[3],
        }


def test_offset_below_six_is_rejected() -> None:
    parser = COSParser(RandomAccessReadBuffer(b"1 0 obj 1 endobj"))
    key = COSObjectKey(1, 0)
    assert parser.find_object_key(key, 0, {key: 0}) is None
    assert parser.find_object_key(key, 5, {key: 5}) is None


def test_whitespace_before_header_is_accepted() -> None:
    prefix, off = _three_objects()
    table = _table(case_points_at_preceding_newline())
    assert table == {(1, 0): off[0], (2, 0): off[1] - 1, (3, 0): off[2]}


def test_higher_generation_rekeys_entry() -> None:
    table = _table(case_higher_generation())
    assert (3, 2) in table and (3, 0) not in table


def test_other_object_number_rekeys_entry() -> None:
    table = _table(case_other_object_number())
    assert (4, 0) in table and (3, 0) not in table


def test_brute_force_skips_multi_digit_generations() -> None:
    table = _table(case_two_digit_generation_not_brute_forced())
    assert (3, 10) not in table
    assert set(table) == {(1, 0), (2, 0), (4, 0)}


def test_brute_force_stops_at_last_garbage_eof() -> None:
    table = _table(case_objects_after_garbage_eof())
    assert (8, 0) not in table
    assert (9, 0) in table


def test_hybrid_xrefstm_does_not_override_table_entry() -> None:
    prefix, off = _three_objects()
    table = _table(case_hybrid_table_wins_over_xrefstm())
    assert table[(3, 0)] == off[2]
    assert (9, 0) in table  # replaced by the brute-force scan


def test_replaced_table_resolves_object_stream_members_lazily() -> None:
    """After a replacement the object-stream members are found by
    ``bfSearchForObjStreams``; a resolved member is added to the xref table
    (upstream ``getObjectOffset``)."""
    import zlib

    payload = b"5 0 (packed)"
    packed = zlib.compress(payload)
    prefix, off = _body(
        [
            (b"1 0 obj", b"<< /Type /Catalog /Pages 2 0 R /X 5 0 R >>"),
            (b"2 0 obj", _PAGES),
            (
                b"4 0 obj",
                b"<< /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode /Length "
                + str(len(packed)).encode("ascii")
                + b" >>\nstream\n"
                + packed
                + b"\nendstream",
            ),
        ]
    )
    data = _with_table(prefix, [(1, off[0], 0), (2, off[1] + 1, 0), (4, off[2], 0)])
    doc = PDFParser(RandomAccessReadBuffer(bytearray(data))).parse()
    key = COSObjectKey(5, 0)
    assert key not in doc.get_xref_table()
    root = doc.get_trailer().get_dictionary_object(COSName.ROOT)
    assert root.get_dictionary_object(COSName.get_pdf_name("X")).get_string() == (
        "packed"
    )
    assert doc.get_xref_table()[key] == -4
    doc.close()


# (bytes, object number, expected) for the byte-exact findObjectKey port; the
# fast regex path in PDFParser must agree with it for every shape.
HEADERS = [
    (b"\n12 0 obj\n", 12, (12, 0)),
    (b"\n12  0  obj ", 12, (12, 0)),
    (b"\n12\t0\robj ", 12, (12, 0)),
    (b"\n12 0obj ", 12, (12, 0)),
    (b"\n12 0 objfoo ", 12, (12, 0)),
    (b"\n12 3 obj ", 12, (12, 3)),
    (b"\n13 0 obj ", 12, (13, 0)),
    (b"\n12 0 xyz ", 12, None),
    (b"\n120obj ", 12, None),
    (b"\n%c\n12 0 obj ", 12, (12, 0)),
    (b"\n12 %c\n0 obj ", 12, (12, 0)),
    (b"\n+12 0 obj ", 12, None),
    (b"\n12 70000 obj ", 12, None),
    (b"\n12345678901 0 obj ", 12, None),
    (b"\n\t12 0 obj ", 12, (12, 0)),
    (b"\n12 0 ob", 12, None),
    (b"\n12 0", 12, None),
]


@pytest.mark.parametrize(
    "header,onum,expected",
    HEADERS,
    ids=[repr(h[0])[2:-1][:24] for h in HEADERS],
)
@pytest.mark.parametrize("block", [1 << 20, 72])
def test_fast_header_path_matches_reader_port(
    header: bytes, onum: int, expected: tuple[int, int] | None, block: int,
    monkeypatch,
) -> None:
    data = b"%PDF-1.4" + b"x" * 90 + header
    offset = 99  # first byte after the leading newline
    key = COSObjectKey(onum, 0)
    values = {key: offset}
    port = _find_object_key_in(_ByteWindow(data, 0, len(data)), key, offset, values, True)
    monkeypatch.setattr(pdf_parser_module, "_BULK_READ_BLOCK", block)
    parser = PDFParser(RandomAccessReadBuffer(bytearray(data)))
    parser._cos_parser = COSParser(parser._src)
    result = parser._find_object_keys(values)
    if expected is None:
        assert port is None
        assert result is None
        return
    assert (port.object_number, port.generation_number) == expected
    corrected, valid = result
    if expected == (onum, 0):
        assert port is key and valid == {key} and not corrected
    else:
        found = corrected[key]
        assert (found.object_number, found.generation_number) == expected


def test_brute_force_scan_rules() -> None:
    data = (
        b"%PDF-1.4\n"
        b"1 0 obj\n(a)\nendobj\n"
        b"2 10 obj\n(two-digit gen)\nendobj\n"
        b"3 0  obj\n(two spaces)\nendobj\n"
        b"4 0\nobj\n(newline)\nendobj\n"
        b"1 0 obj\n(redefined)\nendobj\n"
        b"5 0 obj\n(last, no terminator)"
    )
    offsets = _bf_search_for_objects_in(data)
    keys = {(k.object_number, k.generation_number): v for k, v in offsets.items()}
    # Later definition wins; multi-digit generation and double space are not
    # objects; the final object has neither endobj nor %%EOF, so it is dropped.
    assert set(keys) == {(1, 0), (4, 0)}
    assert keys[(1, 0)] == data.rindex(b"1 0 obj")
