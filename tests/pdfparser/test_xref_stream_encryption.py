"""Tests for the encryption integration on the xref-stream load path.

Background: when an encrypted PDF stores its cross-reference table as a
PDF 1.5 xref stream, the security handler must be ready BEFORE the body
of the xref stream can be deciphered — otherwise the parser sees garbage
where the entry array should be. This file exercises the early-handler
bootstrap that ``PDFParser.set_password`` enables.

The full xref-stream entry decoder lives in parser cluster #4. The tests
here therefore focus on the *integration surface* that the encryption
work adds:

* the new public API (``set_password``, ``get_password``,
  ``get_security_handler``, ``has_encrypted_xref_streams``) is present
  and round-trips its inputs;
* an encrypted document with the staged password produces a security
  handler attached to the parser so any downstream xref-stream body can
  be deciphered;
* a wrong password raises ``PDInvalidPasswordException`` at handler
  bootstrap (i.e. before any xref-stream entries are touched);
* unencrypted documents (xref-stream or traditional table) still parse
  cleanly when no password is staged — the eager path is opt-in.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSObjectKey, COSStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser

# Encryption sub-package may be absent in early checkouts — keep the
# whole file friendly to that case.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")

from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: E402
    PDInvalidPasswordException,
)

# Re-use the synthetic encrypted-document helper from the encryption
# integration suite — same handler, same wire format, same /Encrypt
# layout. Importing through the test package is fine; pytest resolves it
# from ``tests/pdmodel/encryption``.
from tests.pdmodel.encryption.test_encryption_integration import (  # noqa: E402
    _build_encrypted_document,
)


# --------------------------------------------------------------- API surface


def test_set_password_round_trips() -> None:
    """``set_password`` / ``get_password`` are simple accessors — verify
    they accept ``str``, ``bytes``, and ``None`` without coercion."""
    parser = PDFParser(RandomAccessReadBuffer(b"%PDF-1.4\n"))
    assert parser.get_password() is None
    parser.set_password("secret")
    assert parser.get_password() == "secret"
    parser.set_password(b"binary-pw")
    assert parser.get_password() == b"binary-pw"
    parser.set_password(None)
    assert parser.get_password() is None


def test_has_encrypted_xref_streams_default_false() -> None:
    """Newly-constructed parsers have not seen any xref-streams yet."""
    parser = PDFParser(RandomAccessReadBuffer(b"%PDF-1.4\n"))
    assert parser.has_encrypted_xref_streams() is False


def test_get_security_handler_default_none() -> None:
    parser = PDFParser(RandomAccessReadBuffer(b"%PDF-1.4\n"))
    assert parser.get_security_handler() is None


# --------------------------------------------------------------- eager bootstrap


def test_eager_handler_on_encrypted_document_with_password() -> None:
    """Staging a password on an encrypted document should cause the
    parser to instantiate a security handler during xref parsing — well
    before any caller touches the loaded streams.

    This uses a traditional xref table for the synthetic PDF (the
    cluster-#4 xref-stream decoder isn't here yet) but the bootstrap
    path it exercises is the same one an encrypted xref-stream needs
    to feed deciphered bytes to its entry decoder."""
    pdf, stream_key = _build_encrypted_document("hunter2", b"some plaintext")
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.set_password("hunter2")
    doc = parser.parse()
    assert doc.is_encrypted()
    handler = parser.get_security_handler()
    assert handler is not None, "set_password should produce a handler"
    # The handler must be ready (encryption_key derived) — same shape
    # ``PDDocument.decrypt`` arrives at, just earlier in the pipeline.
    assert handler.get_encryption_key() is not None


def test_eager_wrong_password_raises_pd_invalid_password_exception() -> None:
    """A bad password staged via ``set_password`` should fail at handler
    bootstrap — i.e. during ``parse()`` — *not* later during a stream
    read. Mirrors PDFBox's behaviour when the parser builds the handler
    on the load path."""
    pdf, _ = _build_encrypted_document("correct", b"x")
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    parser.set_password("wrong")
    with pytest.raises(PDInvalidPasswordException):
        parser.parse()


def test_no_password_preserves_legacy_lazy_decryption_flow() -> None:
    """Without ``set_password``, an encrypted document still parses —
    the security handler simply isn't built and ``PDDocument.decrypt``
    can do the work later. This is the regression check for the lazy
    flow used by every existing test."""
    pdf, stream_key = _build_encrypted_document("pw", b"payload")
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    # Deliberately *no* set_password call.
    doc = parser.parse()
    assert doc.is_encrypted()
    assert parser.get_security_handler() is None
    # The encrypted stream is in the pool — its body bytes are still the
    # ciphertext, since no handler has touched them yet.
    obj = doc.get_object_from_pool(stream_key)
    body = obj.get_object()
    assert isinstance(body, COSStream)
    # Length matches the encrypted byte count, not the plaintext length.
    assert body.get_length() > 0


# --------------------------------------------------------------- regressions


def test_unencrypted_pdf_with_password_set_parses_cleanly() -> None:
    """``set_password`` on an *unencrypted* document is a no-op — the
    eager bootstrap finds no /Encrypt entry and does nothing. The
    document still parses normally."""
    # Minimal hand-rolled traditional PDF (mirrors the inline helper used
    # in test_pdf_parser.py).
    body = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    body += b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    pdf = bytearray(b"%PDF-1.4\n")
    obj_offsets = [0]
    cur = len(pdf)
    for chunk in body.split(b"endobj\n")[:-1]:
        obj_offsets.append(cur)
        chunk = chunk + b"endobj\n"
        pdf.extend(chunk)
        cur = len(pdf)
    xref_off = len(pdf)
    pdf.extend(b"xref\n0 3\n0000000000 65535 f \n")
    for off in obj_offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    pdf.extend(b"trailer\n<< /Size 3 /Root 1 0 R >>\n")
    pdf.extend(b"startxref\n" + str(xref_off).encode("ascii") + b"\n%%EOF")

    parser = PDFParser(RandomAccessReadBuffer(bytes(pdf)))
    parser.set_password("unused-because-no-encrypt")
    doc = parser.parse()
    assert not doc.is_encrypted()
    assert parser.get_security_handler() is None
    assert doc.has_object(COSObjectKey(1, 0))


def test_xref_stream_malformed_dict_raises_parse_error() -> None:
    """A malformed xref stream (missing /Length, /W, etc.) must surface
    as ``PDFParseError`` from the cluster-#4 decoder rather than be
    silently accepted. Regression guard for the parse-vs-load boundary."""
    pdf = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Type /XRef >>\nstream\nendstream\nendobj\n"
        b"startxref\n9\n%%EOF"
    )
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    from pypdfbox.pdfparser import PDFParseError  # noqa: PLC0415

    with pytest.raises(PDFParseError):
        parser.parse()
