from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser


def _build_pdf(objects: list[bytes], trailer: bytes = b"<< /Size 2 /Root 1 0 R >>") -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
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
    out += b"trailer\n"
    out += trailer + b"\n"
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def test_wave322_pdf_parser_recovers_direct_negative_stream_length() -> None:
    """A negative direct /Length fails ``validate_stream_length`` and triggers
    the endstream recovery scan in lenient mode — exactly as upstream PDFBox
    ``parseCOSStream`` does (a negative ``longValue()`` simply fails
    ``validateStreamLength``). The recovered body is the bytes up to
    ``endstream`` and /Length is rewritten. (Wave 1517 alignment — formerly
    pypdfbox raised a fail-fast ``PDFParseError``.)"""
    pdf = _build_pdf(
        [
            b"1 0 obj\n"
            b"<< /Length -1 >>\n"
            b"stream\n"
            b"ABCDE\n"
            b"endstream\n"
            b"endobj",
        ]
    )
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    try:
        stream_obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        stream = stream_obj.get_object()
        assert stream.get_raw_data() == b"ABCDE"
        assert stream.get_length() == 5
    finally:
        doc.close()


def test_wave322_pdf_parser_recovers_indirect_negative_stream_length() -> None:
    """As above, but /Length is an indirect ref resolving to ``-1``."""
    pdf = _build_pdf(
        [
            b"1 0 obj\n"
            b"<< /Length 2 0 R >>\n"
            b"stream\n"
            b"ABCDE\n"
            b"endstream\n"
            b"endobj",
            b"2 0 obj\n-1\nendobj",
        ],
        trailer=b"<< /Size 3 /Root 1 0 R >>",
    )
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    try:
        stream_obj = doc.get_object_from_pool(COSObjectKey(1, 0))
        stream = stream_obj.get_object()
        assert stream.get_raw_data() == b"ABCDE"
        assert stream.get_length() == 5
    finally:
        doc.close()
