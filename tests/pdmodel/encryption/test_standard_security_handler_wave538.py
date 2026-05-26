from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDocument, COSString
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    DEFAULT_PERMISSIONS,
    InvalidPasswordException,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


class _Document:
    def __init__(self) -> None:
        self.encryption: PDEncryption | None = None

    def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
        self.encryption = encryption


class _PDDocumentLike(_Document):
    def __init__(self, document_id: bytes) -> None:
        super().__init__()
        self._cos_document = COSDocument()
        self._cos_document.set_document_id(COSArray([COSString(document_id)]))

    def get_document(self) -> COSDocument:
        return self._cos_document


def _legacy_encryption(password: bytes = b"", revision: int = 3) -> tuple[bytes, PDEncryption]:
    document_id = b"wave538-doc-id!"
    key_len = 5 if revision == 2 else 16
    permissions = DEFAULT_PERMISSIONS
    o = StandardSecurityHandler.compute_owner_password(password, password, revision, key_len)
    u = StandardSecurityHandler.compute_user_password(
        password,
        o,
        permissions,
        document_id,
        revision,
        key_len,
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(1 if revision == 2 else 2)
    encryption.set_revision(revision)
    encryption.set_length(key_len * 8)
    encryption.set_p(permissions)
    encryption.set_o(o)
    encryption.set_u(u)
    return document_id, encryption


def test_wave538_prepare_for_decryption_rejects_non_standard_material() -> None:
    document_id, encryption = _legacy_encryption()

    with pytest.raises(TypeError, match="StandardDecryptionMaterial"):
        StandardSecurityHandler().prepare_for_decryption(encryption, document_id, object())


def test_wave538_prepare_for_decryption_requires_password_entries() -> None:
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(DEFAULT_PERMISSIONS)

    with pytest.raises(InvalidPasswordException):
        StandardSecurityHandler().prepare_for_decryption(
            encryption,
            b"",
            StandardDecryptionMaterial("user"),
        )


def test_wave538_revision5_short_user_and_owner_entries_do_not_validate() -> None:
    encryption = PDEncryption()
    encryption.set_revision(5)
    encryption.set_length(256)
    encryption.set_o(b"short")
    encryption.set_u(b"short")

    assert not StandardSecurityHandler.is_user_password("pw", encryption, b"")
    assert not StandardSecurityHandler.is_owner_password("pw", encryption, b"")


def test_wave538_prepare_document_requires_policy() -> None:
    with pytest.raises(ValueError, match="protection_policy"):
        StandardSecurityHandler().prepare_document(_Document())


def test_wave538_prepare_document_uses_document_id_for_legacy_key() -> None:
    document_id = b"custom-file-id!!"
    policy = StandardProtectionPolicy(
        owner_password="",
        user_password="user",
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(128)
    handler = StandardSecurityHandler(policy)
    document = _PDDocumentLike(document_id)

    handler.prepare_document(document)

    assert document.encryption is not None
    expected = StandardSecurityHandler.compute_encrypted_key(
        b"user",
        document.encryption.get_o() or b"",
        document.encryption.get_p(),
        document_id,
        document.encryption.get_revision(),
        16,
    )
    assert handler.get_encryption_key() == expected
    decoder = StandardSecurityHandler()
    decoder.prepare_for_decryption(
        document.encryption,
        document_id,
        StandardDecryptionMaterial("user"),
    )
    assert decoder.get_encryption_key() == expected


def test_wave538_prepare_document_installs_aes128_crypt_filter() -> None:
    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(True)
    handler = StandardSecurityHandler(policy)
    document = _Document()

    handler.prepare_document_for_encryption(document)

    assert document.encryption is not None
    assert document.encryption.get_revision() == 4
    assert document.encryption.get_v() == 4
    assert document.encryption.get_stm_f() == "StdCF"
    assert document.encryption.get_str_f() == "StdCF"
    std_cf = document.encryption.get_std_crypt_filter_dictionary()
    assert std_cf is not None
    assert std_cf.get_cfm() == "AESV2"
    assert std_cf.get_length() == 16
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_wave538_identity_and_unknown_filters_leave_bytes_unchanged() -> None:
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"k" * 16)
    payload = b"plain payload"

    assert handler._dispatch_encrypt("Identity", payload, 7, 0) is payload  # noqa: SLF001
    assert handler._dispatch_decrypt("None", payload, 7, 0) is payload  # noqa: SLF001
    assert handler._dispatch_encrypt("UnknownCFM", payload, 7, 0) is payload  # noqa: SLF001
    assert handler._dispatch_decrypt("UnknownCFM", payload, 7, 0) is payload  # noqa: SLF001


def test_wave538_revision_number_from_version_uses_policy_permissions() -> None:
    class _Permissions:
        def has_any_revision3_permission_set(self) -> bool:
            return True

    class _Policy:
        def get_permissions(self) -> _Permissions:
            return _Permissions()

    handler = StandardSecurityHandler(_Policy())

    assert handler.compute_revision_number_from_version(1) == 3
    assert handler.compute_revision_number_from_version(5) == 6
    assert StandardSecurityHandler().compute_revision_number_from_version(1) == 2
