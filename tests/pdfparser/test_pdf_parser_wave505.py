from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _build_pdf(
    objects: list[bytes],
    trailer: bytes = b"<< /Size 2 /Root 1 0 R >>",
    *,
    startxref_delta: int = 0,
) -> bytes:
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
    out += b"startxref\n" + str(xref_offset + startxref_delta).encode("ascii")
    out += b"\n%%EOF"
    return bytes(out)


def test_wave505_linearization_probe_ignores_malformed_first_object() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n[1 2\nendobj",
            b"2 0 obj\n<< /Type /Catalog >>\nendobj",
        ],
        b"<< /Size 3 /Root 2 0 R >>",
    )
    parser = _parser(pdf)
    doc = parser.parse()

    try:
        assert parser.is_linearized() is False
        assert doc.has_object(COSObjectKey(1, 0))
        assert doc.has_object(COSObjectKey(2, 0))
    finally:
        doc.close()


def test_wave505_stream_body_can_start_after_stream_keyword_without_eol() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n"
            b"<< /Length 5 >>\n"
            b"stream/abcd\n"
            b"endstream\n"
            b"endobj",
        ],
    )
    parser = _parser(pdf)
    doc = parser.parse()

    try:
        body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert isinstance(body, COSStream)
        assert body.get_raw_data() == b"/abcd"
    finally:
        doc.close()


def test_wave505_strict_parse_rejects_shifted_startxref_without_recovery() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        startxref_delta=1,
    )
    parser = _parser(pdf)
    parser.set_lenient(False)

    with pytest.raises(PDFParseError, match="does not point to xref"):
        parser.parse()


def test_wave505_lazy_load_nulls_header_object_number_mismatch() -> None:
    # Wave 1503: upstream ``COSParser.parseFileObject`` throws on a header /
    # xref object-number mismatch (Java line 729-734), so lazily resolving an
    # object whose xref offset points at a differently-numbered ``n g obj``
    # header is rejected internally rather than returning the wrong object.
    # COSObject.getObject catches that parser I/O failure and resolves to null.
    out = bytearray(b"%PDF-1.4\n")
    target_offset = len(out)
    out += b"2 0 obj\n42\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n1 1\n"
    out += f"{target_offset:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    parser = _parser(bytes(out))
    doc = parser.parse()

    try:
        target = doc.get_object_from_pool(COSObjectKey(1, 0))
        assert target.get_object() is None
        assert target.is_dereferenced()
    finally:
        doc.close()
