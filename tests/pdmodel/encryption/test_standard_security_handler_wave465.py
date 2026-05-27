from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    InvalidPasswordException,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


def _legacy_encryption(
    *,
    revision: int,
    version: int,
    user_password: bytes = b"user",
    owner_password: bytes = b"owner",
    permissions: int = -3904,
    document_id: bytes = b"\0" * 16,
) -> PDEncryption:
    key_len_bytes = 5 if revision == 2 else 16
    owner = StandardSecurityHandler.compute_owner_password(
        owner_password, user_password, revision, key_len_bytes
    )
    user = StandardSecurityHandler.compute_user_password(
        user_password, owner, permissions, document_id, revision, key_len_bytes
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(version)
    encryption.set_revision(revision)
    encryption.set_length(key_len_bytes * 8)
    encryption.set_p(permissions)
    encryption.set_o(owner)
    encryption.set_u(user)
    return encryption


def test_wave465_prepare_for_decryption_rejects_wrong_material_type() -> None:
    handler = StandardSecurityHandler()

    with pytest.raises(TypeError, match="StandardDecryptionMaterial"):
        handler.prepare_for_decryption(PDEncryption(), b"", object())


def test_wave465_prepare_for_decryption_requires_r6_key_entries() -> None:
    encryption = PDEncryption()
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(-3904)
    encryption.set_o(b"o" * 48)
    encryption.set_u(b"u" * 48)
    encryption.set_oe(b"k" * 32)
    # /UE and /Perms are intentionally absent.

    with pytest.raises(InvalidPasswordException):
        StandardSecurityHandler().prepare_for_decryption(
            encryption, b"", StandardDecryptionMaterial("user")
        )


def test_wave465_r2_user_password_authenticates_and_sets_limited_access() -> None:
    encryption = _legacy_encryption(revision=2, version=1)
    handler = StandardSecurityHandler()

    handler.prepare_for_decryption(
        encryption, b"\0" * 16, StandardDecryptionMaterial("user")
    )

    assert handler.get_revision() == 2
    assert handler.get_version() == 1
    assert handler.get_key_length() == 40
    current = handler.get_current_access_permission()
    assert current is not None
    assert not current.is_owner_permission()
    assert current.is_read_only()


def test_wave465_is_password_helpers_return_false_for_short_r6_hashes() -> None:
    encryption = PDEncryption()
    encryption.set_revision(6)
    encryption.set_u(b"short")
    encryption.set_o(b"short")

    assert StandardSecurityHandler.is_user_password("pw", encryption, b"") is False
    assert StandardSecurityHandler.is_owner_password("pw", encryption, b"") is False


def test_wave465_v4_routing_resolves_cf_entries_and_eff_defaults_to_stream() -> None:
    encryption = _legacy_encryption(revision=4, version=4)
    aes = PDCryptFilterDictionary()
    aes.set_cfm("AESV2")
    rc4 = PDCryptFilterDictionary()
    rc4.set_cfm("V2")
    encryption.set_crypt_filter_dictionary("StreamCF", aes)
    encryption.set_crypt_filter_dictionary("StringCF", rc4)
    encryption.set_stm_f("StreamCF")
    encryption.set_str_f("StringCF")

    handler = StandardSecurityHandler()
    handler.prepare_for_decryption(
        encryption, b"\0" * 16, StandardDecryptionMaterial("user")
    )

    assert handler.is_aes() is True
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "V2"
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_wave465_identity_and_unknown_filters_are_passthrough() -> None:
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"\x01" * 16)

    assert handler._dispatch_encrypt("Identity", b"plain", 1, 0) == b"plain"  # noqa: SLF001
    assert handler._dispatch_decrypt("None", b"plain", 1, 0) == b"plain"  # noqa: SLF001
    assert handler._dispatch_encrypt("BogusCFM", b"plain", 1, 0) == b"plain"  # noqa: SLF001
    assert handler._dispatch_decrypt("BogusCFM", b"plain", 1, 0) == b"plain"  # noqa: SLF001


def test_wave465_prepare_document_requires_policy() -> None:
    with pytest.raises(ValueError, match="protection_policy"):
        StandardSecurityHandler().prepare_document(object())


def test_wave465_prepare_document_uses_owner_default_and_attaches_encryption() -> None:
    class DocStub:
        def __init__(self) -> None:
            self.encryption: PDEncryption | None = None

        def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
            self.encryption = encryption

    policy = StandardProtectionPolicy("", "shared", AccessPermission())
    policy.set_encryption_key_length(40)
    handler = StandardSecurityHandler(policy)
    doc = DocStub()

    handler.prepare_document(doc)

    assert doc.encryption is not None
    # /V 1 (40-bit RC4) with the default AccessPermission() — whose revision-3
    # bits are all set — is written at R3, matching PDFBox's
    # computeRevisionNumber (wave 1434). R2 requires clearing the rev-3 bits.
    assert doc.encryption.get_revision() == 3
    assert doc.encryption.get_v() == 1
    assert StandardSecurityHandler.is_user_password(
        "shared", doc.encryption, b"\0" * 16
    )
    assert StandardSecurityHandler.is_owner_password(
        "shared", doc.encryption, b"\0" * 16
    )
