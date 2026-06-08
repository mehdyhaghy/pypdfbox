from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser


def _parser(data: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(data))


def _build_pdf(
    objects: list[bytes],
    trailer: bytes = b"<< /Size 2 /Root 1 0 R >>",
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
    out += b"startxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_wave484_get_encryption_dictionary_resolves_indirect_trailer_entry() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog >>\nendobj",
            b"2 0 obj\n<< /Filter /Standard /V 1 >>\nendobj",
        ],
        b"<< /Size 3 /Root 1 0 R /Encrypt 2 0 R >>",
    )
    parser = _parser(pdf)
    doc = parser.parse()

    try:
        encrypt = parser.get_encryption_dictionary()
        assert isinstance(encrypt, COSDictionary)
        assert encrypt.get_name("Filter") == "Standard"
    finally:
        doc.close()


def test_wave484_stream_body_can_follow_bare_cr_after_stream_keyword() -> None:
    payload = b"abcde"
    pdf = _build_pdf(
        [
            b"1 0 obj\n"
            b"<< /Length 5 >>\n"
            b"stream\r"
            + payload
            + b"\nendstream\n"
            b"endobj",
        ],
    )
    parser = _parser(pdf)
    doc = parser.parse()

    try:
        body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert isinstance(body, COSStream)
        assert body.get_raw_data() == payload
    finally:
        doc.close()


def test_wave484_stream_negative_length_recovers_when_object_is_loaded() -> None:
    """A negative /Length fails ``validate_stream_length`` and triggers the
    endstream recovery scan in lenient mode, mirroring upstream PDFBox
    ``parseCOSStream`` (a negative ``longValue()`` simply fails
    ``validateStreamLength``). (Wave 1517 alignment.)"""
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Length -1 >>\nstream\nabc\nendstream\nendobj"],
    )
    parser = _parser(pdf)
    doc = parser.parse()

    try:
        stream = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
        assert isinstance(stream, COSStream)
        assert stream.get_raw_data() == b"abc"
    finally:
        doc.close()
