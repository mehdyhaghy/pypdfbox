from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _build_pdf(objects: list[bytes], trailer: bytes = b"<< /Size 2 /Root 1 0 R >>") -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for body in objects:
        offsets.append(len(out))
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    xref_offset = len(out)
    out += b"xref\n"
    out += f"0 {len(offsets)}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n" + trailer + b"\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def _xref_stream_pdf(
    *,
    dict_entries: bytes,
    body: bytes,
    version: bytes = b"1.5",
) -> bytes:
    out = bytearray(b"%PDF-" + version + b"\n")
    startxref = len(out)
    out += (
        b"1 0 obj\n"
        b"<< /Type /XRef "
        + dict_entries
        + b" /Length "
        + str(len(body)).encode("ascii")
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
        b"startxref\n"
        + str(startxref).encode("ascii")
        + b"\n%%EOF"
    )
    return bytes(out)


def test_wave380_parse_header_rejects_empty_version() -> None:
    with pytest.raises(PDFParseError, match="malformed %PDF version"):
        _parser(b"%PDF-\nrest").parse_header()


def test_wave380_find_startxref_honors_small_lookup_window() -> None:
    pdf = _build_pdf([b"1 0 obj\n<< /Type /Catalog >>\nendobj"]) + b"\n" + (b"x" * 64)
    parser = _parser(pdf)
    parser.set_eof_lookup_range(16)

    with pytest.raises(PDFParseError, match="missing 'startxref'"):
        parser.find_startxref_offset()


def test_wave380_parse_xref_chain_stops_on_prev_cycle() -> None:
    out = bytearray(b"%PDF-1.4\n")
    obj_offset = len(out)
    out += b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj_offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 2 /Root 1 0 R /Prev "
        + str(xref_offset).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"

    doc = _parser(bytes(out)).parse()
    try:
        assert doc.has_object(COSObjectKey(1, 0))
        assert doc.get_start_xref() == xref_offset
    finally:
        doc.close()


def test_wave380_xref_stream_rejects_non_integer_w_entry() -> None:
    pdf = _xref_stream_pdf(
        dict_entries=b"/Size 1 /Index [ 0 1 ] /W [ 1 /Bad 1 ]",
        body=b"\x00\x00\x00",
    )

    with pytest.raises(PDFParseError, match=r"/W\[1\] is not an integer"):
        _parser(pdf).parse()


def test_wave380_xref_stream_rejects_zero_width_record() -> None:
    pdf = _xref_stream_pdf(
        dict_entries=b"/Size 1 /Index [ 0 1 ] /W [ 0 0 0 ]",
        body=b"",
    )

    with pytest.raises(PDFParseError, match="field widths sum to zero"):
        _parser(pdf).parse()


def test_wave380_xref_stream_rejects_oversized_record_width() -> None:
    pdf = _xref_stream_pdf(
        dict_entries=b"/Size 1 /Index [ 0 1 ] /W [ 7 7 7 ]",
        body=b"\x00" * 21,
    )

    with pytest.raises(PDFParseError, match="wider than 20 bytes"):
        _parser(pdf).parse()


def test_wave380_xref_stream_rejects_truncated_body_for_index() -> None:
    pdf = _xref_stream_pdf(
        dict_entries=b"/Size 2 /Index [ 0 2 ] /W [ 1 1 1 ]",
        body=b"\x00\x00\x00",
    )

    with pytest.raises(PDFParseError, match="body truncated relative to /Index"):
        _parser(pdf).parse()


def test_wave380_xref_stream_unknown_entry_type_is_treated_as_free() -> None:
    pdf = _xref_stream_pdf(
        dict_entries=b"/Size 6 /Index [ 5 1 ] /W [ 1 1 1 ]",
        body=b"\x09\x00\x00",
    )
    parser = _parser(pdf)
    doc = parser.parse()

    try:
        assert not doc.has_object(COSObjectKey(5, 0))
        entry = parser.get_xref_trailer_resolver().get_xref_table()[COSObjectKey(5, 0)]
        assert entry.compressed_index == -1
    finally:
        doc.close()


def test_wave380_xref_stream_missing_stream_keyword_raises() -> None:
    out = bytearray(b"%PDF-1.5\n")
    startxref = len(out)
    out += b"1 0 obj\n<< /Type /XRef /Size 1 /W [ 1 1 1 ] /Length 0 >>\nendobj\n"
    out += b"startxref\n" + str(startxref).encode("ascii") + b"\n%%EOF"

    with pytest.raises(PDFParseError, match="missing 'stream' keyword"):
        _parser(bytes(out)).parse()


def test_wave380_xref_stream_without_size_or_index_raises() -> None:
    pdf = _xref_stream_pdf(
        dict_entries=b"/W [ 1 1 1 ]",
        body=b"",
    )

    with pytest.raises(PDFParseError, match="missing /Size and /Index"):
        _parser(pdf).parse()
