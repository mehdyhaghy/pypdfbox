from __future__ import annotations

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


def test_wave509_decryption_material_uses_revision_specific_string_encoding() -> None:
    material = StandardDecryptionMaterial("café")

    assert material.get_password() == b"caf\xe9"
    assert material.get_password_bytes(4) == b"caf\xe9"
    assert material.get_password_bytes(6) == "café".encode("utf-8")
    assert StandardDecryptionMaterial(b"raw\xff").get_password_bytes(6) == b"raw\xff"


def test_wave509_policy_accessors_and_filter_are_instance_state() -> None:
    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    handler = StandardSecurityHandler()

    assert handler.get_filter() == "Standard"
    assert handler.has_protection_policy() is False
    assert handler.get_protection_policy() is None

    handler.set_protection_policy(policy)

    assert handler.has_protection_policy() is True
    assert handler.get_protection_policy() is policy

    handler.set_protection_policy(None)
    assert handler.has_protection_policy() is False


def test_wave509_compute_revision_number_from_version_uses_policy_permissions() -> None:
    permissions = AccessPermission()
    permissions.set_can_fill_in_form(True)
    policy = StandardProtectionPolicy("owner", "user", permissions)
    handler = StandardSecurityHandler(policy)

    assert handler.compute_revision_number_from_version(1) == 3
    assert handler.compute_revision_number_from_version(2) == 3
    assert handler.compute_revision_number_from_version(3) == 3
    assert handler.compute_revision_number_from_version(4) == 4
    assert handler.compute_revision_number_from_version(5) == 6
    assert handler.compute_revision_number_from_version(99) == 3
    assert StandardSecurityHandler().compute_revision_number_from_version(1) == 2
    assert StandardSecurityHandler().compute_revision_number_from_version(99) == 4


def test_wave509_prepare_document_aes128_installs_std_crypt_filter() -> None:
    class DocumentStub:
        def __init__(self) -> None:
            self.encryption: PDEncryption | None = None

        def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
            self.encryption = encryption

    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(True)
    handler = StandardSecurityHandler(policy)
    doc = DocumentStub()

    handler.prepare_document(doc)

    assert doc.encryption is not None
    assert doc.encryption.get_v() == 4
    assert doc.encryption.get_revision() == 4
    assert doc.encryption.get_length() == 128
    assert doc.encryption.get_stm_f() == "StdCF"
    assert doc.encryption.get_str_f() == "StdCF"
    assert doc.encryption.get_eff() is None
    assert handler.is_aes() is True
    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_wave509_prepare_for_decryption_owner_password_sets_owner_access() -> None:
    document_id = b"wave509-doc-id!!"
    owner_password = b"owner"
    user_password = b"user"
    owner = StandardSecurityHandler.compute_owner_password(
        owner_password,
        user_password,
        3,
        16,
    )
    user = StandardSecurityHandler.compute_user_password(
        user_password,
        owner,
        DEFAULT_PERMISSIONS,
        document_id,
        3,
        16,
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(2)
    encryption.set_revision(3)
    encryption.set_length(128)
    encryption.set_p(DEFAULT_PERMISSIONS)
    encryption.set_o(owner)
    encryption.set_u(user)
    handler = StandardSecurityHandler()

    handler.prepare_for_decryption(
        encryption,
        document_id,
        StandardDecryptionMaterial(owner_password),
    )

    current = handler.get_current_access_permission()
    assert current is not None
    assert current.is_owner_permission() is True
    assert current.is_read_only() is False


def test_wave509_resolve_cfm_handles_identity_direct_algorithms_and_unknowns() -> None:
    encryption = PDEncryption()

    assert StandardSecurityHandler._resolve_cfm(encryption, None) is None  # noqa: SLF001
    assert StandardSecurityHandler._resolve_cfm(encryption, "Identity") == "Identity"  # noqa: SLF001
    assert StandardSecurityHandler._resolve_cfm(encryption, "V2") == "V2"  # noqa: SLF001
    assert StandardSecurityHandler._resolve_cfm(encryption, "AESV3") == "AESV3"  # noqa: SLF001
    assert StandardSecurityHandler._resolve_cfm(encryption, "UnknownCF") is None  # noqa: SLF001
