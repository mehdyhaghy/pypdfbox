"""Parser-side regression tests for encrypted PDFs whose cross-reference
table is itself an xref stream (PDF 1.5+).

ISO 32000-2 §7.6.2 reserves cross-reference streams from encryption
("All cross-reference streams in the file shall not be encrypted") so
the parser can read /Encrypt's byte offset out of them before any
security handler exists. The bootstrap is therefore:

  1. parser walks ``/Prev`` and parses the xref-stream object
  2. xref-stream body is FlateDecoded plaintext → entries register
  3. /Encrypt's offset is now known; parser builds the security handler
  4. subsequent /Prev sections, indirect streams, and the document-level
     ``PDDocument.decrypt`` walk all use that handler

Before the fix that introduces these tests, step 2 failed because the
writer enciphered the xref-stream body alongside every other indirect
stream, so FlateDecode saw ciphertext and bailed with "incorrect header
check". The exhaustive end-to-end coverage lives in
``tests/integration/test_end_to_end.py::test_encrypt_and_xref_stream_combined_roundtrip``;
this file isolates the parser surface and the writer's
spec-compliance shape.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser
from pypdfbox.pdfwriter import COSWriter

# Encryption sub-package may be absent in early checkouts — keep the
# whole file friendly to that case.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")


def _build_encrypted_xref_stream_pdf(
    *,
    owner_password: str = "owner",
    user_password: str = "user",
    page_text: str = "encrypted xref stream payload",
) -> bytes:
    """Build the smallest possible ``/Type /XRef`` + ``/Encrypt`` PDF.

    Returns the raw bytes — callers can either re-parse or inspect them.
    Goes through the public writer surface (``COSWriter(xref_stream=
    True)``) so the test reflects exactly what real callers produce."""
    from pypdfbox import PDDocument
    from pypdfbox.cos import COSName as _COSName
    from pypdfbox.pdmodel import PDPage
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    pd = PDDocument()
    page = PDPage(PDRectangle.LETTER)
    pd.add_page(page)
    # Standard-14 Helvetica wrapper — same minimal recipe the integration
    # suite uses; sufficient for the lite text-stripper round-trip.
    font = PDType1Font()
    font.get_cos_object().set_name(_COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(pd, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(72, 720)
        cs.show_text(page_text)
        cs.end_text()
    pd.protect(
        StandardProtectionPolicy(
            owner_password=owner_password, user_password=user_password
        )
    )
    sink = io.BytesIO()
    with COSWriter(sink, xref_stream=True) as writer:
        writer.write(pd)
    pd.close()
    return sink.getvalue()


# ----------------------------------------------------------- writer shape


def test_writer_emits_plaintext_flate_xref_stream() -> None:
    """The xref-stream body must start with the zlib magic 0x78 — proof
    that the writer's encryption pass skipped the spec-exempt object."""
    pdf = _build_encrypted_xref_stream_pdf()
    assert b"/Type /XRef" in pdf
    # Locate the xref stream's body. ``startxref`` points at its
    # offset (since hybrid mode is off and the xref stream IS the
    # trailer).
    startxref_idx = pdf.rindex(b"startxref\n")
    line_start = startxref_idx + len(b"startxref\n")
    line_end = pdf.index(b"\n", line_start)
    xref_offset = int(pdf[line_start:line_end].strip())
    body_window = pdf[xref_offset:startxref_idx]
    stream_marker = body_window.index(b"stream")
    body_start = stream_marker + len(b"stream")
    if body_window[body_start:body_start + 2] == b"\r\n":
        body_start += 2
    elif body_window[body_start:body_start + 1] in (b"\n", b"\r"):
        body_start += 1
    assert body_window[body_start:body_start + 1] == b"\x78", (
        "xref-stream body should begin with the zlib magic 0x78 — "
        "encryption must skip /Type /XRef per ISO 32000-2 §7.6.2"
    )


# ----------------------------------------------------------- parser path


def test_parse_succeeds_with_set_password() -> None:
    """Eager-decrypt path: ``set_password`` BEFORE ``parse()`` lets the
    parser stand up the security handler from /Encrypt's xref-stream
    entry without falling back to ``PDDocument.decrypt`` later."""
    pdf = _build_encrypted_xref_stream_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.set_password("user")
    cos_doc = parser.parse()
    assert cos_doc.is_encrypted()
    handler = parser.get_security_handler()
    assert handler is not None
    assert handler.get_encryption_key() is not None
    assert parser.has_encrypted_xref_streams() is True


def test_xref_stream_decode_after_full_load_yields_plaintext_records() -> None:
    """After ``PDDocument.load`` (which runs the document-level decrypt
    walk), every indirect object recorded by the xref stream must still
    resolve — proof that the xref stream was read as PLAINTEXT during the
    parser bootstrap (ISO 32000-2 §7.6.2: cross-reference streams are never
    encrypted). A double-decipher would have garbled the fixed-width records
    (byte offsets), so resolution would fail and the page text would not
    decode. Regression guard for the wave-13 double-decipher bug.

    Note (wave 1501): the xref stream itself is no longer an enumerable pool
    object — pypdfbox now matches PDFBox's ``COSWriter.doWriteXRefInc``, which
    serialises the xref body via ``getStream()`` before the stream's own
    ``doWriteObject``, so it carries no self-entry and is located via
    ``startxref`` rather than via the object pool. The plaintext-records
    guarantee is therefore asserted through clean resolution + text decode
    instead of by re-reading the (no-longer-pooled) xref stream body."""
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    payload = "wave1373-payload-XYZ"
    pdf = _build_encrypted_xref_stream_pdf(page_text=payload)
    with PDDocument.load(pdf, password="user") as doc:
        cos_doc = doc.get_document()
        # Every pooled object resolves (garbled xref offsets would yield None).
        for cos_obj in cos_doc.get_objects():
            assert cos_obj.get_object() is not None
        # End-to-end: the page text decodes — the xref offsets pointed at the
        # right objects, i.e. the xref stream body was plaintext, not double-
        # deciphered.
        assert payload in PDFTextStripper().get_text(doc)


def test_full_load_pdf_round_trip_extracts_text() -> None:
    """Top-level ``PDDocument.load`` should hand back a fully decrypted
    document whose page content extracts cleanly. End-to-end gate for
    the fix — covers the loader's password-staging hook, the parser's
    eager bootstrap, and the page content's decrypt-then-FlateDecode
    pipeline."""
    from pypdfbox.pdmodel import PDDocument
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    payload = "encrypted xref stream payload"
    pdf = _build_encrypted_xref_stream_pdf(page_text=payload)
    # Pre-condition: cleartext payload is NOT visible on disk.
    assert payload.encode("ascii") not in pdf

    with PDDocument.load(pdf, password="user") as doc:
        assert doc.is_encrypted() is True
        assert doc.get_number_of_pages() == 1
        text = PDFTextStripper().get_text(doc)
        assert payload in text


def test_parse_without_password_still_succeeds() -> None:
    """Lazy path: omitting ``set_password`` should still let the parser
    walk the xref-stream chain (the body is plaintext) — the document
    just stays encrypted until the caller drives ``PDDocument.decrypt``
    later. Regression guard for the legacy flow used by every existing
    test suite."""
    pdf = _build_encrypted_xref_stream_pdf()
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    cos_doc = parser.parse()
    assert cos_doc.is_encrypted()
    assert parser.get_security_handler() is None
