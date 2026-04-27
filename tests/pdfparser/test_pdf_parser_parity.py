from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser
from pypdfbox.pdmodel.pd_document import PDDocument

# ---------- helpers ----------


def _build_pdf(objects: list[bytes], trailer: bytes, version: bytes = b"1.4") -> bytes:
    """Assemble a tiny but spec-compliant PDF (mirrors the helper in
    ``test_pdf_parser.py``)."""
    out = bytearray()
    out += b"%PDF-" + version + b"\n"
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
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += trailer + b"\n"
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def _parser(pdf_bytes: bytes) -> PDFParser:
    return PDFParser(RandomAccessReadBuffer(pdf_bytes))


def _minimal_pdf_bytes() -> bytes:
    return _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj",
        ],
        b"<< /Size 4 /Root 1 0 R >>",
    )


# ---------- get_document ----------


def test_get_document_returns_none_before_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_document() is None


def test_get_document_returns_cos_document_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    doc = p.get_document()
    assert doc is not None
    assert isinstance(doc, COSDocument)


def test_get_document_returns_same_instance_returned_by_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    parsed = p.parse()
    assert p.get_document() is parsed


# ---------- set_lenient / is_lenient ----------


def test_is_lenient_default_true() -> None:
    # The pypdfbox parser is permissive by default.
    p = _parser(_minimal_pdf_bytes())
    assert p.is_lenient() is True


def test_set_lenient_round_trip() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_lenient(False)
    assert p.is_lenient() is False
    p.set_lenient(True)
    assert p.is_lenient() is True


def test_set_lenient_coerces_truthy_values() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_lenient(0)  # type: ignore[arg-type]
    assert p.is_lenient() is False
    p.set_lenient(1)  # type: ignore[arg-type]
    assert p.is_lenient() is True


# ---------- get_password / set_password ----------


def test_get_password_default_is_none() -> None:
    p = _parser(_minimal_pdf_bytes())
    assert p.get_password() is None


def test_set_password_round_trip_str() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_password("hunter2")
    assert p.get_password() == "hunter2"


def test_set_password_round_trip_bytes() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_password(b"\x00\x01secret")
    assert p.get_password() == b"\x00\x01secret"


def test_set_password_can_clear_to_none() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.set_password("first")
    p.set_password(None)
    assert p.get_password() is None


# ---------- get_pd_document ----------


def test_get_pd_document_returns_pd_document_after_parse() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    pd = p.get_pd_document()
    assert isinstance(pd, PDDocument)


def test_get_pd_document_is_cached() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    first = p.get_pd_document()
    second = p.get_pd_document()
    assert first is second


def test_get_pd_document_wraps_parsed_cos_document() -> None:
    p = _parser(_minimal_pdf_bytes())
    p.parse()
    pd = p.get_pd_document()
    # The wrapper must expose the same COSDocument returned by get_document().
    assert pd.get_document() is p.get_document()


def test_get_pd_document_before_parse_raises() -> None:
    p = _parser(_minimal_pdf_bytes())
    with pytest.raises(PDFParseError):
        p.get_pd_document()
