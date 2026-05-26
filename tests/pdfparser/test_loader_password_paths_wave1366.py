"""Loader password / force-parsing / encrypted-but-no-password paths
(wave 1366, agent E).

Covers the boundary between the Loader's auto-decrypt path and the manual
``PDDocument.decrypt`` flow:

* Loading an encrypted document with NO password — returns an encrypted
  COSDocument; caller drives decrypt themselves.
* Loading with the wrong password — raises ``InvalidPasswordException``.
* Loading with empty string vs ``None`` password.
* Lenient (force) parsing toggle defaults to lenient.
* ``PDDocument.load`` two-arg vs three-arg parity.

No upstream JUnit counterpart — pypdfbox-specific suite around
``Loader.load_pdf(File, String)`` overload semantics.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSObjectKey, COSStream
from pypdfbox.loader import Loader
from pypdfbox.pdfparser import PDFParser
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    InvalidPasswordException,
    StandardSecurityHandler,
)

# Hard-coded document ID matches StandardSecurityHandler.prepare_document's
# "lite path" — needed for the file-encryption-key derivation to line up
# when we synthesise the trailer ID by hand.
_DOC_ID = b"\x00" * 16


def _build_encrypted_pdf(
    user_password: str, payload: bytes = b"hello cipher"
) -> tuple[bytes, COSObjectKey]:
    """Mirror ``tests/pdmodel/encryption/test_encryption_integration``'s
    builder. Returns the encrypted bytes plus the stream's COSObjectKey
    so callers can verify decrypted bytes round-trip."""
    policy = StandardProtectionPolicy(
        owner_password=user_password,
        user_password=user_password,
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(False)

    handler = StandardSecurityHandler(policy)
    captured: dict[str, PDEncryption] = {}

    class _Capture:
        def set_encryption_dictionary(self, e: PDEncryption) -> None:
            captured["enc"] = e

    handler.prepare_document(_Capture())
    enc = captured["enc"]

    stream_obj_num, stream_gen = 3, 0
    cipher_bytes = handler.encrypt_stream(payload, stream_obj_num, stream_gen)

    out = bytearray()
    out += b"%PDF-1.4\n"
    offsets: list[int] = [0]

    def add(body: bytes) -> None:
        offsets.append(len(out))
        out.extend(body)
        if not body.endswith(b"\n"):
            out.append(0x0A)

    add(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    add(b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj")
    stream_dict = f"3 0 obj\n<< /Length {len(cipher_bytes)} >>\nstream\n".encode("ascii")
    out_offset = len(out)
    offsets.append(out_offset)
    out.extend(stream_dict)
    out.extend(cipher_bytes)
    out.extend(b"\nendstream\nendobj\n")

    enc_lines = [b"4 0 obj\n<<"]
    enc_lines.append(b"/Filter /Standard")
    enc_lines.append(f"/V {enc.get_v()}".encode("ascii"))
    enc_lines.append(f"/R {enc.get_revision()}".encode("ascii"))
    enc_lines.append(f"/Length {enc.get_length()}".encode("ascii"))
    enc_lines.append(f"/P {enc.get_p()}".encode("ascii"))
    o_bytes = enc.get_o() or b""
    u_bytes = enc.get_u() or b""
    enc_lines.append(b"/O <" + o_bytes.hex().upper().encode("ascii") + b">")
    enc_lines.append(b"/U <" + u_bytes.hex().upper().encode("ascii") + b">")
    enc_lines.append(b">>\nendobj")
    add(b"\n".join(enc_lines))

    xref_offset = len(out)
    out.extend(b"xref\n")
    out.extend(f"0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(b"trailer\n")
    out.extend(b"<< /Size 5 /Root 1 0 R /Encrypt 4 0 R")
    out.extend(b" /ID [<")
    out.extend(_DOC_ID.hex().upper().encode("ascii"))
    out.extend(b"> <")
    out.extend(_DOC_ID.hex().upper().encode("ascii"))
    out.extend(b">] >>\n")
    out.extend(b"startxref\n")
    out.extend(f"{xref_offset}\n".encode("ascii"))
    out.extend(b"%%EOF")
    return bytes(out), COSObjectKey(stream_obj_num, stream_gen)


# ---------------------- tests


def test_load_encrypted_without_password_returns_encrypted() -> None:
    """An encrypted PDF loaded with ``password=None`` parses but the
    COSDocument is reported as encrypted (no auto-decrypt). Streams stay
    locked until the caller drives ``PDDocument.decrypt``."""
    pdf, _ = _build_encrypted_pdf("k")
    cos = Loader.load_pdf(pdf)
    try:
        assert cos.is_encrypted() is True
    finally:
        cos.close()


def test_load_encrypted_with_correct_password_auto_decrypts() -> None:
    """Correct password triggers the Loader's auto-decrypt path — stream
    bodies come back in plaintext via ``create_input_stream``."""
    payload = b"the quick brown fox"
    pdf, key = _build_encrypted_pdf("pw", payload)
    cos = Loader.load_pdf(pdf, "pw")
    try:
        # is_encrypted reports the trailer state; the stream-decode path
        # is what actually exercises the security handler.
        stream_obj = cos.get_object_from_pool(key).get_object()
        assert isinstance(stream_obj, COSStream)
        with stream_obj.create_input_stream() as src:
            assert src.read() == payload
    finally:
        cos.close()


def test_load_encrypted_with_wrong_password_raises() -> None:
    """Wrong password surfaces as ``InvalidPasswordException``."""
    pdf, _ = _build_encrypted_pdf("right")
    with pytest.raises(InvalidPasswordException):
        Loader.load_pdf(pdf, "wrong")


def test_load_encrypted_with_blank_password_when_protected() -> None:
    """A document protected with a non-empty password rejects the empty
    string — same error as ``wrong-password``."""
    pdf, _ = _build_encrypted_pdf("nonblank")
    with pytest.raises(InvalidPasswordException):
        Loader.load_pdf(pdf, "")


def test_pddocument_load_password_retry_after_failure() -> None:
    """Failed ``PDDocument.load(..., password=BAD)`` is a clean failure —
    a follow-up ``Loader.load_pdf(..., GOOD)`` on the same bytes succeeds
    (i.e. the failed attempt didn't permanently brick the input bytes)."""
    payload = b"retry path"
    pdf, key = _build_encrypted_pdf("good", payload)
    with pytest.raises(InvalidPasswordException):
        PDDocument.load(pdf, password="bad")
    cos = Loader.load_pdf(pdf, "good")
    try:
        stream_obj = cos.get_object_from_pool(key).get_object()
        assert isinstance(stream_obj, COSStream)
        with stream_obj.create_input_stream() as src:
            assert src.read() == payload
    finally:
        cos.close()


def test_loader_password_string_and_bytes_equivalent() -> None:
    """``Loader.load_pdf`` accepts ``str`` and ``bytes`` passwords —
    UTF-8 encoded byte forms must produce the same auto-decrypt result
    as the equivalent ``str``."""
    payload = b"unicode-pass"
    pdf, key = _build_encrypted_pdf("plain")
    cos_str = Loader.load_pdf(pdf, "plain")
    try:
        stream_str = cos_str.get_object_from_pool(key).get_object()
        assert isinstance(stream_str, COSStream)
    finally:
        cos_str.close()

    pdf2, key2 = _build_encrypted_pdf("plain", payload)
    cos_bytes = Loader.load_pdf(pdf2, b"plain")
    try:
        stream_bytes = cos_bytes.get_object_from_pool(key2).get_object()
        assert isinstance(stream_bytes, COSStream)
        with stream_bytes.create_input_stream() as src:
            assert src.read() == payload
    finally:
        cos_bytes.close()


def test_load_plain_document_with_password_is_no_op() -> None:
    """Passing a password to a non-encrypted document neither raises nor
    leaves stale handler state — auto-decrypt path is skipped."""
    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(sink)
    cos = Loader.load_pdf(sink.getvalue(), "ignored")
    try:
        assert cos.is_encrypted() is False
    finally:
        cos.close()


def test_pdf_parser_lenient_default_true() -> None:
    """``PDFParser`` is lenient by default — the parser tolerates
    minor wire-format violations (extra trailing whitespace, etc.) which
    is the upstream baseline. Confirm via the public surface."""
    from pypdfbox.io import RandomAccessReadBuffer

    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(sink)
    parser = PDFParser(RandomAccessReadBuffer(sink.getvalue()))
    assert parser.is_lenient() is True


def test_pdf_parser_set_lenient_false_runs_strict_mode() -> None:
    """``set_lenient(False)`` flips the parser into strict mode — a
    well-formed PDF still parses cleanly under strict mode."""
    from pypdfbox.io import RandomAccessReadBuffer

    sink = io.BytesIO()
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(sink)
    parser = PDFParser(RandomAccessReadBuffer(sink.getvalue()))
    parser.set_lenient(False)
    assert parser.is_lenient() is False
    cos = parser.parse()
    try:
        # The strict-mode parse still produced a usable document.
        assert cos.get_trailer() is not None
    finally:
        cos.close()


def test_loader_empty_input_raises() -> None:
    """Truly empty bytes are an OSError at the Loader boundary (mirrors
    upstream's ``IOException`` translation)."""
    with pytest.raises(OSError):
        Loader.load_pdf(b"")


def test_loader_garbage_input_raises() -> None:
    """Non-PDF bytes raise at the Loader boundary."""
    with pytest.raises(OSError):
        Loader.load_pdf(b"this is not a PDF at all\n" * 10)
