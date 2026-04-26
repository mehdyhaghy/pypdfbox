"""Integration tests for the encryption wiring across ``Loader``,
``COSStream``, ``PDDocument``, and ``PDFParser``.

Focus is the *plumbing*, not the cryptographic primitives — those are
covered by ``tests/pdmodel/encryption/test_pd_encryption.py`` and the
``StandardSecurityHandler`` upstream tests. Here we verify:

* parsing a document with a ``/Encrypt`` trailer entry sets
  ``PDDocument.is_encrypted()``;
* ``PDDocument.decrypt`` propagates a ``StandardSecurityHandler`` to every
  ``COSStream`` in the pool, after which ``create_input_stream`` recovers
  the plaintext;
* a wrong password raises :class:`PDInvalidPasswordException`;
* ``set_all_security_to_be_removed`` strips ``/Encrypt`` from the saved
  document so it round-trips unencrypted.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox import Loader, PDDocument
from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSObjectKey,
    COSStream,
)

# All sibling encryption modules required for these tests. ``importorskip``
# keeps the file friendly to checkouts where the security cluster has not
# yet landed.
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
pytest.importorskip("pypdfbox.pdmodel.encryption.standard_protection_policy")

from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: E402
    AccessPermission,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption  # noqa: E402
from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: E402
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: E402
    PDInvalidPasswordException,
    StandardSecurityHandler,
)

# ``StandardSecurityHandler.prepare_document`` hard-codes a 16-zero document
# ID for the lite path (see standard_security_handler.py); we reuse the same
# value when manually building the trailer so the file-encryption-key
# derivation matches.
_DOC_ID = b"\x00" * 16


def _build_encrypted_document(
    user_password: str,
    stream_payload: bytes,
) -> tuple[bytes, COSObjectKey]:
    """Synthesise a tiny encrypted PDF and return ``(bytes, stream_key)``.

    Hand-rolls just enough of the wire format to drive ``Loader.load_pdf``
    end-to-end with /Encrypt populated. The single content stream's bytes
    are pre-encrypted with the per-object key derived from the standard
    handler so that ``decrypt`` round-trips them back to ``stream_payload``.
    """
    # 1. Build the standard handler from a protection policy.
    policy = StandardProtectionPolicy(
        owner_password=user_password,
        user_password=user_password,
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(False)  # r3 RC4-128 — simplest path

    handler = StandardSecurityHandler(policy)
    # ``prepare_document`` synthesises a fresh ``PDEncryption`` and hands it
    # to ``set_encryption_dictionary``; we capture the wrapper so we can
    # read the populated /V /R /Length /P /O /U back out for the trailer.
    captured: dict[str, PDEncryption] = {}

    class _Capture:
        def set_encryption_dictionary(self, e: PDEncryption) -> None:
            captured["enc"] = e

    handler.prepare_document(_Capture())
    enc = captured["enc"]

    # 2. Encrypt the stream payload with the per-object key for (3, 0).
    stream_obj_num, stream_gen = 3, 0
    cipher_bytes = handler.encrypt_stream(
        stream_payload, stream_obj_num, stream_gen
    )

    # 3. Hand-assemble the PDF bytes. Layout:
    #    1: Catalog -> 2: Pages
    #    2: Pages
    #    3: Stream (encrypted, /Length matching the cipher payload)
    #    4: /Encrypt dict
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
    # Pre-encrypted stream body. /Length is the *encrypted* byte count.
    stream_dict = f"3 0 obj\n<< /Length {len(cipher_bytes)} >>\nstream\n".encode(
        "ascii"
    )
    out_offset = len(out)
    offsets.append(out_offset)
    out.extend(stream_dict)
    out.extend(cipher_bytes)
    out.extend(b"\nendstream\nendobj\n")
    # /Encrypt dict (object 4). Serialised by hand so the trailer reference
    # resolves cleanly. We mirror only the keys the handler reads back.
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

    # 4. xref + trailer with /Encrypt + /ID (file id used by the handler).
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


# ---------------------------------------------------------------- tests


def test_is_encrypted_after_parsing_encrypted_pdf() -> None:
    pdf, _ = _build_encrypted_document("hunter2", b"hello cipher")
    cos_doc = Loader.load_pdf(pdf)
    try:
        assert cos_doc.is_encrypted() is True
        with PDDocument(cos_doc) as pd:
            pd._owns_document = False  # noqa: SLF001 — keep cos alive
            assert pd.is_encrypted() is True
    finally:
        cos_doc.close()


def test_decrypt_with_correct_password_recovers_stream_bytes() -> None:
    payload = b"the quick brown fox jumps over the lazy dog"
    pdf, stream_key = _build_encrypted_document("s3cret", payload)
    cos_doc = Loader.load_pdf(pdf, "s3cret")
    try:
        # Auto-decrypt path attached the handler; resolve and read the stream.
        stream_obj = cos_doc.get_object_from_pool(stream_key).get_object()
        assert isinstance(stream_obj, COSStream)
        with stream_obj.create_input_stream() as src:
            recovered = src.read()
        assert recovered == payload
    finally:
        cos_doc.close()


def test_decrypt_via_pddocument_round_trip() -> None:
    payload = b"manual decrypt path"
    pdf, stream_key = _build_encrypted_document("pw", payload)
    # Load encrypted, then decrypt via PDDocument.
    with PDDocument.load(pdf) as pd:
        assert pd.is_encrypted() is True
        pd.decrypt("pw")
        stream_obj = pd.get_document().get_object_from_pool(stream_key).get_object()
        assert isinstance(stream_obj, COSStream)
        with stream_obj.create_input_stream() as src:
            assert src.read() == payload


def test_decrypt_with_wrong_password_raises() -> None:
    pdf, _ = _build_encrypted_document("correct", b"x")
    with pytest.raises(PDInvalidPasswordException):
        Loader.load_pdf(pdf, "WRONG")


def test_decrypt_no_op_on_unencrypted_document() -> None:
    """Calling ``decrypt`` on a non-encrypted document is a quiet no-op
    (matches PDFBox: skips key derivation, no exception)."""
    with PDDocument() as pd:
        pd.decrypt("anything")  # must not raise
        assert pd.is_encrypted() is False


def test_set_all_security_to_be_removed_strips_encryption_on_save() -> None:
    payload = b"plaintext after stripping"
    pdf, _stream_key = _build_encrypted_document("rm", payload)
    sink = io.BytesIO()
    with PDDocument.load(pdf, password="rm") as pd:
        assert pd.is_encrypted() is True
        pd.set_all_security_to_be_removed(True)
        pd.save(sink)
        assert pd.is_all_security_to_be_removed() is True

    # Re-load the saved bytes — /Encrypt must be gone from the trailer
    # (the synthetic stream itself is not reachable from /Root in this
    # toy fixture, so the writer prunes it; the encryption-stripping
    # contract is the trailer-level guarantee verified here).
    with PDDocument.load(sink.getvalue()) as reloaded:
        assert reloaded.is_encrypted() is False
        assert reloaded.get_document().get_encryption_dictionary() is None


def test_get_encryption_returns_pd_encryption_for_encrypted_doc() -> None:
    pdf, _ = _build_encrypted_document("k", b"x")
    with PDDocument.load(pdf) as pd:
        enc = pd.get_encryption()
        assert isinstance(enc, PDEncryption)
        assert enc.get_filter() == "Standard"


def test_get_encryption_returns_none_for_unencrypted_doc() -> None:
    with PDDocument() as pd:
        assert pd.get_encryption() is None


def test_protect_accepts_standard_protection_policy() -> None:
    policy = StandardProtectionPolicy(
        owner_password="o", user_password="u", permissions=AccessPermission()
    )
    with PDDocument() as pd:
        pd.protect(policy)
        assert pd._protection_policy is policy  # noqa: SLF001


def test_protect_rejects_non_standard_policy() -> None:
    with PDDocument() as pd, pytest.raises(NotImplementedError):
        pd.protect(object())


def test_pdf_parser_get_encryption_dictionary_exposed() -> None:
    """Round-trip: parser-level introspection mirrors the COSDocument
    accessor and resolves the indirect-object reference."""
    from pypdfbox.io import RandomAccessReadBuffer
    from pypdfbox.pdfparser import PDFParser

    pdf, _ = _build_encrypted_document("p", b"y")
    parser = PDFParser(RandomAccessReadBuffer(pdf))
    doc = parser.parse()
    try:
        enc_dict = parser.get_encryption_dictionary()
        assert isinstance(enc_dict, COSDictionary)
        assert enc_dict.get_name(COSName.get_pdf_name("Filter")) == "Standard"
        # /ID first element matches the bytes we baked in.
        doc_id = parser.get_document_id()
        assert doc_id == _DOC_ID
    finally:
        doc.close()
