from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject, COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError, PDFParser

# ---------- helpers for synthesizing minimal PDFs ----------


def _build_pdf(objects: list[bytes], trailer: bytes, version: bytes = b"1.4") -> bytes:
    """Assemble a tiny but spec-compliant PDF.

    ``objects`` is a list of fully-formed indirect-object bodies (each
    must end with ``endobj`` but may include ``stream``/``endstream`` in
    between). Object 0 is implicit (the free root).
    """
    out = bytearray()
    out += b"%PDF-" + version + b"\n"
    offsets: list[int] = [0]  # object 0 is the free root
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


# ---------- header ----------


def test_parse_header_basic() -> None:
    pdf = b"%PDF-1.7\n... rest"
    p = _parser(pdf)
    assert p.parse_header() == 1.7


def test_parse_header_tolerates_leading_garbage() -> None:
    pdf = b"X-Header: junk\n%PDF-2.0\nrest"
    assert _parser(pdf).parse_header() == 2.0


def test_parse_header_missing_raises() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"not a pdf at all").parse_header()


def test_parse_header_malformed_version_raises() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"%PDF-bad\nrest").parse_header()


# ---------- startxref ----------


def test_find_startxref_returns_offset() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n42\nendobj"],
        b"<< /Size 2 /Root 1 0 R >>",
    )
    p = _parser(pdf)
    p.parse()
    # parse() ran startxref internally; check via re-construction
    assert p.find_startxref_offset() == pdf.find(b"xref\n")


def test_find_startxref_missing_raises() -> None:
    with pytest.raises(PDFParseError):
        _parser(b"%PDF-1.4\n nothing useful\n").find_startxref_offset()


def test_find_startxref_out_of_bounds_raises() -> None:
    pdf = b"%PDF-1.4\nstartxref\n9999999\n%%EOF"
    with pytest.raises(PDFParseError):
        _parser(pdf).find_startxref_offset()


def test_parse_leniently_recovers_shifted_startxref_offset() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        b"<< /Size 2 /Root 1 0 R >>",
    )
    xref_offset = pdf.find(b"xref\n")
    bad_pdf = pdf.replace(
        b"startxref\n" + str(xref_offset).encode("ascii") + b"\n",
        b"startxref\n" + str(xref_offset + 2).encode("ascii") + b"\n",
    )

    p = _parser(bad_pdf)
    doc = p.parse()

    try:
        assert p.get_xref_offset() == xref_offset
        assert doc.get_start_xref() == xref_offset
        assert isinstance(doc.get_catalog(), COSDictionary)
    finally:
        doc.close()


def test_parse_strict_mode_rejects_shifted_startxref_offset() -> None:
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        b"<< /Size 2 /Root 1 0 R >>",
    )
    xref_offset = pdf.find(b"xref\n")
    bad_pdf = pdf.replace(
        b"startxref\n" + str(xref_offset).encode("ascii") + b"\n",
        b"startxref\n" + str(xref_offset + 2).encode("ascii") + b"\n",
    )
    p = _parser(bad_pdf)
    p.set_lenient(False)

    with pytest.raises(PDFParseError):
        p.parse()


# ---------- end-to-end ----------


def test_parse_minimal_pdf_populates_pool_and_trailer() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj",
        ],
        b"<< /Size 4 /Root 1 0 R >>",
    )
    doc = _parser(pdf).parse()
    assert doc.get_version() == 1.4
    assert doc.has_object(COSObjectKey(1, 0))
    assert doc.has_object(COSObjectKey(2, 0))
    assert doc.has_object(COSObjectKey(3, 0))
    catalog = doc.get_catalog()
    assert isinstance(catalog, COSDictionary)
    assert catalog.get_name("Type") == "Catalog"


def test_lazy_loader_resolves_indirect_objects_on_demand() -> None:
    pdf = _build_pdf(
        [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj",
        ],
        b"<< /Size 3 /Root 1 0 R >>",
    )
    doc = _parser(pdf).parse()
    catalog = doc.get_catalog()
    assert catalog is not None
    pages_ref = catalog.get_item("Pages")
    assert isinstance(pages_ref, COSObject)
    assert not pages_ref.is_object_loaded()
    pages = pages_ref.get_object()
    assert isinstance(pages, COSDictionary)
    assert pages.get_name("Type") == "Pages"
    assert pages.get_int("Count") == 0


def test_parse_pdf_with_stream_object() -> None:
    payload = b"q 100 100 m 200 200 l S Q"
    body = (
        b"1 0 obj\n"
        b"<< /Length " + str(len(payload)).encode("ascii") + b" >>\n"
        b"stream\n"
        + payload + b"\n"
        b"endstream\n"
        b"endobj"
    )
    pdf = _build_pdf([body], b"<< /Size 2 /Root 1 0 R >>")
    doc = _parser(pdf).parse()
    obj = doc.get_object_from_pool(COSObjectKey(1, 0))
    body_obj = obj.get_object()
    assert isinstance(body_obj, COSStream)
    assert body_obj.get_raw_data() == payload
    assert body_obj.get_length() == len(payload)


def test_parse_pdf_with_two_subsection_xref() -> None:
    """A traditional xref table can have multiple subsections (different
    object-number ranges). Build one by hand to exercise that loop."""
    obj1 = b"1 0 obj\n42\nendobj\n"
    obj5 = b"5 0 obj\n(hello)\nendobj\n"
    out = bytearray(b"%PDF-1.4\n")
    out += obj1
    off5 = len(out)
    out += obj5
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{len(b'%PDF-1.4\n'):010d} 00000 n \n".encode("ascii")
    out += b"5 1\n"
    out += f"{off5:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert doc.has_object(COSObjectKey(1, 0))
    assert doc.has_object(COSObjectKey(5, 0))
    obj5_loaded = doc.get_object_from_pool(COSObjectKey(5, 0)).get_object()
    assert isinstance(obj5_loaded, COSInteger) is False  # it's a string body
    # Should be a COSString with bytes b"hello"
    from pypdfbox.cos import COSString
    assert isinstance(obj5_loaded, COSString)
    assert obj5_loaded.get_bytes() == b"hello"


def test_parse_pdf_with_prev_chain() -> None:
    """Build a PDF with two xref sections chained via /Prev. The newer
    section overrides the older for a shared key."""
    out = bytearray(b"%PDF-1.4\n")
    obj_v1 = b"1 0 obj\n(old version)\nendobj\n"
    out += obj_v1
    xref1_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{len(b'%PDF-1.4\n'):010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref1_off).encode("ascii") + b"\n%%EOF\n"
    # Now an incremental update: newer obj 1 + new xref pointing back.
    obj_v2_off = len(out)
    obj_v2 = b"1 0 obj\n(new version)\nendobj\n"
    out += obj_v2
    xref2_off = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n1 1\n"
    out += f"{obj_v2_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 2 /Root 1 0 R /Prev "
        + str(xref1_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(xref2_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    assert doc.has_object(COSObjectKey(1, 0))
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    from pypdfbox.cos import COSString
    assert isinstance(body, COSString)
    assert body.get_bytes() == b"new version"


def test_xref_entry_with_unknown_flag_raises() -> None:
    out = bytearray(b"%PDF-1.4\n1 0 obj\n42\nendobj\n")
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += b"0000000009 00000 z \n"  # 'z' isn't a valid flag
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    with pytest.raises(PDFParseError):
        PDFParser(RandomAccessReadBuffer(bytes(out))).parse()


def test_xref_stream_malformed_dict_raises() -> None:
    """If the byte at the xref offset isn't 'x' (i.e. isn't 'xref'), we
    treat it as an xref stream. A malformed body (missing /Length, /W,
    etc.) must surface as ``PDFParseError``; the cluster-#4 decoder
    refuses to silently accept a truncated record."""
    pdf = b"%PDF-1.5\n1 0 obj\n<< /Type /XRef >>\nstream\nendstream\nendobj\nstartxref\n9\n%%EOF"
    with pytest.raises(PDFParseError):
        PDFParser(RandomAccessReadBuffer(pdf)).parse()


def test_stream_with_indirect_length_resolves_via_loader() -> None:
    """The /Length value can be an indirect reference. The stream-body
    reader must follow it through the COSObject loader."""
    payload = b"STREAM-CONTENT"
    out = bytearray(b"%PDF-1.4\n")
    # Object 1: the stream itself with /Length 2 0 R
    obj1_off = len(out)
    obj1 = (
        b"1 0 obj\n"
        b"<< /Length 2 0 R >>\n"
        b"stream\n"
        + payload + b"\n"
        b"endstream\n"
        b"endobj\n"
    )
    out += obj1
    # Object 2: the integer length
    obj2_off = len(out)
    out += b"2 0 obj\n" + str(len(payload)).encode("ascii") + b"\nendobj\n"
    xref_off = len(out)
    out += b"xref\n0 3\n0000000000 65535 f \n"
    out += f"{obj1_off:010d} 00000 n \n".encode("ascii")
    out += f"{obj2_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 3 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSStream)
    assert body.get_raw_data() == payload


def test_free_xref_entry_is_not_registered_in_pool() -> None:
    """Free entries (the 'f' flag) must not produce loadable COSObjects."""
    out = bytearray(b"%PDF-1.4\n1 0 obj\n42\nendobj\n")
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{len(b'%PDF-1.4\n'):010d} 00000 n \n".encode("ascii")
    out += b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    # Object 0 is free — should not appear in the pool.
    assert not doc.has_object(COSObjectKey(0, 65535))
    # Object 1 is in-use — should appear.
    assert doc.has_object(COSObjectKey(1, 0))


def test_parse_returns_document_with_pdf_name_lookups() -> None:
    """COSName.TYPE etc. round-trip correctly through the loader path."""
    pdf = _build_pdf(
        [b"1 0 obj\n<< /Type /Catalog >>\nendobj"],
        b"<< /Size 2 /Root 1 0 R >>",
    )
    doc = _parser(pdf).parse()
    catalog = doc.get_catalog()
    assert catalog is not None
    type_val = catalog.get_item(COSName.TYPE)  # type: ignore[attr-defined]
    assert type_val is COSName.get_pdf_name("Catalog")
