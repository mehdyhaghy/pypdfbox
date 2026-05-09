from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSString
from pypdfbox.cos.cos_document import COSDocument
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    DEFAULT_PERMISSIONS,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


def _r2_encryption(user_password: bytes, document_id: bytes) -> PDEncryption:
    owner = b"owner"
    o_value = StandardSecurityHandler.compute_owner_password(owner, user_password, 2, 5)
    u_value = StandardSecurityHandler.compute_user_password(
        user_password,
        o_value,
        DEFAULT_PERMISSIONS,
        document_id,
        2,
        5,
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(1)
    encryption.set_revision(2)
    encryption.set_length(40)
    encryption.set_p(DEFAULT_PERMISSIONS)
    encryption.set_o(o_value)
    encryption.set_u(u_value)
    return encryption


def test_prepare_for_decryption_rejects_non_standard_material() -> None:
    handler = StandardSecurityHandler()

    with pytest.raises(TypeError, match="StandardDecryptionMaterial"):
        handler.prepare_for_decryption(PDEncryption(), b"", object())


def test_prepare_for_decryption_revision2_uses_40_bit_rc4_user_path() -> None:
    document_id = b"revision-two-id!"
    encryption = _r2_encryption(b"user", document_id)

    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption,
        document_id,
        StandardDecryptionMaterial("user"),
    )

    assert handler.get_revision() == 2
    assert handler.get_version() == 1
    assert handler.get_key_length() == 40
    assert handler.is_aes() is False
    assert handler.get_stream_cfm() is None
    assert len(handler.get_encryption_key() or b"") == 5
    current = handler.get_current_access_permission()
    assert current is not None
    assert current.is_read_only()
    assert not current.is_owner_permission()


def test_prepare_document_without_policy_raises_value_error() -> None:
    with pytest.raises(ValueError, match="protection_policy"):
        StandardSecurityHandler().prepare_document(object())


def test_prepare_document_40_bit_policy_writes_revision2_dictionary() -> None:
    captured: dict[str, PDEncryption] = {}
    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    policy.set_encryption_key_length(40)

    class _Document:
        def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
            captured["encryption"] = encryption

    handler = StandardSecurityHandler(policy)
    handler.prepare_document(_Document())

    encryption = captured["encryption"]
    assert encryption.get_filter() == "Standard"
    assert encryption.get_v() == 1
    assert encryption.get_revision() == 2
    assert encryption.get_length() == 40
    assert encryption.get_o() is not None
    assert encryption.get_u() is not None
    assert encryption.has_cf() is False
    assert handler.get_stream_cfm() is None
    assert handler.get_string_cfm() is None


def test_extract_document_id_reads_cos_document_first_id() -> None:
    cos_doc = COSDocument()
    try:
        ids = COSArray()
        ids.add(COSString(b"first-id"))
        ids.add(COSString(b"second-id"))
        cos_doc.set_document_id(ids)

        assert (
            StandardSecurityHandler._extract_document_id(cos_doc, b"default")  # noqa: SLF001
            == b"first-id"
        )
    finally:
        cos_doc.close()


def test_extract_document_id_reads_wrapped_document() -> None:
    cos_doc = COSDocument()
    try:
        ids = COSArray()
        ids.add(COSString(b"wrapped-id"))
        cos_doc.set_document_id(ids)

        class _PDDocumentLike:
            def get_document(self) -> COSDocument:
                return cos_doc

        assert (
            StandardSecurityHandler._extract_document_id(  # noqa: SLF001
                _PDDocumentLike(),
                b"default",
            )
            == b"wrapped-id"
        )
    finally:
        cos_doc.close()


def test_extract_document_id_falls_back_for_missing_or_non_string_id() -> None:
    assert (
        StandardSecurityHandler._extract_document_id(object(), b"default")  # noqa: SLF001
        == b"default"
    )

    cos_doc = COSDocument()
    try:
        ids = COSArray()
        ids.add(COSArray())
        cos_doc.set_document_id(ids)
        assert (
            StandardSecurityHandler._extract_document_id(cos_doc, b"default")  # noqa: SLF001
            == b"default"
        )
    finally:
        cos_doc.close()


def test_standard_decryption_material_get_password_str_variants() -> None:
    assert StandardDecryptionMaterial(None).get_password_str() is None
    assert StandardDecryptionMaterial("plain").get_password_str() == "plain"
    assert StandardDecryptionMaterial(b"caf\xe9").get_password_str() == "café"
