"""Wave 1368 — parser tolerance for real-world PDF wart edges.

Real-world PDFs frequently deviate from the strict grammar. The
permissive (lenient) parser must absorb these without flagging the
file as unreadable:

* Comment lines (``%`` ... EOL) anywhere outside string/stream bodies.
* Excessive whitespace between tokens (tabs, multiple linebreaks).
* Missing whitespace between the indirect-object header and ``<<``.
* Binary-marker comment after the header (``%%¤¤¤`` style).
* Trailing garbage past ``%%EOF`` (some pipelines append signatures).
* Trailer dict prefixed with extra space and trailing whitespace.
"""

from __future__ import annotations

from pypdfbox.cos import COSObjectKey, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser


def _build_with_obj(body: bytes, trailer_pad: bytes = b"") -> bytes:
    """Wrap ``body`` (a complete indirect object) in a minimal PDF with
    a trailer optionally prefixed with ``trailer_pad`` bytes."""
    out = bytearray(b"%PDF-1.4\n")
    obj_off = len(out)
    out += body
    if not body.endswith(b"\n"):
        out += b"\n"
    xref_off = len(out)
    out += b"xref\n0 2\n0000000000 65535 f \n"
    out += f"{obj_off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n" + trailer_pad + b"<< /Size 2 /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF"
    return bytes(out)


def test_comment_line_before_object_does_not_break_parser() -> None:
    """A ``%`` comment line preceding an indirect object must be
    skipped, not consumed as part of the body."""
    body = (
        b"% This is a comment line introducing the object\n"
        b"1 0 obj\n(hello)\nendobj"
    )
    pdf = _build_with_obj(body)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    body1 = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body1, COSString) and body1.get_bytes() == b"hello"


def test_binary_marker_comment_after_header_tolerated() -> None:
    """PDFs commonly carry a "binary marker" comment with 4 high-bit
    bytes right after the header to signal "this file contains binary
    streams" to legacy tooling. The parser must accept it."""
    pdf = (
        b"%PDF-1.4\n"
        b"%\xE2\xE3\xCF\xD3\n"  # PDF binary-marker convention
        b"1 0 obj\n(works)\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000015 00000 n \n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
        b"startxref\n38\n%%EOF"
    )
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(1, 0))


def test_extra_whitespace_between_tokens_tolerated() -> None:
    """Multiple linebreaks / tabs between an indirect-object header
    and its body must not corrupt parsing."""
    body = b"1   0   obj\n\n\n\t<< /Type /Catalog >>\n\nendobj"
    pdf = _build_with_obj(body)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(1, 0))


def test_missing_whitespace_between_header_and_dict_tolerated() -> None:
    """``1 0 obj<< ... >>`` (no whitespace between ``obj`` and the
    dictionary opener) is unusual but legal — ``<<`` is its own token."""
    body = b"1 0 obj<< /Type /Catalog >>endobj"
    pdf = _build_with_obj(body)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(1, 0))


def test_trailing_garbage_after_eof_tolerated() -> None:
    """Some signing / packaging pipelines append a detached signature
    after ``%%EOF``. The parser's tail-scan finds the real ``startxref``
    and ignores the trailing bytes."""
    pdf = _build_with_obj(b"1 0 obj\n(payload)\nendobj")
    pdf_with_garbage = pdf + b"\n--SIG-START--\n\x00\x01\x02noise\n"
    doc = PDFParser(RandomAccessReadBuffer(pdf_with_garbage)).parse()
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSString) and body.get_bytes() == b"payload"


def test_comments_inside_dictionary_skipped() -> None:
    """A ``%`` comment can appear inside a dictionary between
    name/value pairs."""
    body = (
        b"1 0 obj\n"
        b"<< /Type /Catalog\n"
        b"   % a comment between entries\n"
        b"   /Pages 2 0 R >>\n"
        b"endobj"
    )
    pdf = _build_with_obj(body)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    catalog = doc.get_catalog()
    assert catalog is not None
    assert catalog.get_name("Type") == "Catalog"


def test_trailer_with_leading_whitespace_padding_parses() -> None:
    """The traditional ``trailer`` keyword may be padded with extra
    whitespace before its ``<<``. The parser must skip the padding
    before parsing the dict."""
    pdf = _build_with_obj(b"1 0 obj\n(ok)\nendobj", trailer_pad=b"\n\n\n  \t")
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSString) and body.get_bytes() == b"ok"


def test_multiple_consecutive_comments_skipped() -> None:
    """A run of comment lines (e.g. a copyright header) before the
    first real object must not derail header detection or object
    parsing."""
    body = (
        b"% Comment 1\n"
        b"% Comment 2 -- copyright notice\n"
        b"% Comment 3\n"
        b"1 0 obj\n42\nendobj"
    )
    pdf = _build_with_obj(body)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    from pypdfbox.cos import COSInteger  # noqa: PLC0415

    body_obj = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body_obj, COSInteger) and body_obj.value == 42
