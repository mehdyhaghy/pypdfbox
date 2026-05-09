from __future__ import annotations

import hashlib
import logging
from types import SimpleNamespace

import pytest

from pypdfbox.pdmodel.encryption import standard_security_handler as ssh_module
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    DEFAULT_PERMISSIONS,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


def test_wave518_material_accessors_and_revision_helpers() -> None:
    assert StandardDecryptionMaterial().get_password() is None
    assert StandardDecryptionMaterial().get_password_bytes(6) is None
    assert StandardDecryptionMaterial().get_password_str() is None
    assert StandardDecryptionMaterial(b"raw").get_password() == b"raw"
    assert StandardDecryptionMaterial(b"raw").get_password_str() == "raw"

    handler = StandardSecurityHandler()
    assert handler.get_permissions() == DEFAULT_PERMISSIONS
    assert handler.is_encrypt_metadata() is True
    assert handler.is_encrypt_meta_data() is True
    assert handler.PROTECTION_POLICY_CLASS is StandardProtectionPolicy
    assert StandardSecurityHandler.compute_revision_number(256) == 6
    assert StandardSecurityHandler.compute_revision_number(128, prefer_aes=True) == 4
    assert StandardSecurityHandler.compute_revision_number(128) == 3
    assert StandardSecurityHandler.compute_revision_number(40) == 2


def test_wave518_owner_password_recovery_and_public_key_aliases() -> None:
    owner_password = b"owner"
    user_password = b"user"
    document_id = b"wave518-doc-id!!"
    owner_r2 = StandardSecurityHandler.compute_owner_password(
        owner_password, user_password, 2, 5
    )
    recovered_r2 = StandardSecurityHandler.get_user_password(
        owner_password, owner_r2, 2, 5
    )

    assert recovered_r2 == StandardSecurityHandler._pad_password(user_password)  # noqa: SLF001

    owner_r3 = StandardSecurityHandler.compute_owner_password(
        owner_password, user_password, 3, 16
    )
    recovered_r3 = StandardSecurityHandler.get_user_password(
        owner_password, owner_r3, 3, 16
    )
    encrypted_key = StandardSecurityHandler.compute_encrypted_key(
        user_password,
        owner_r3,
        DEFAULT_PERMISSIONS,
        document_id,
        3,
        16,
    )

    assert recovered_r3 == StandardSecurityHandler._pad_password(user_password)  # noqa: SLF001
    assert len(encrypted_key) == 16
    assert StandardSecurityHandler.get_user_password(owner_password, owner_r3, 6, 32) == b""


def _revision5_encryption_for_password(
    password: bytes,
    file_key: bytes,
    *,
    owner_password: bytes | None = None,
    perms: bytes = b"invalid-perms!!!!",
) -> PDEncryption:
    user_validation_salt = b"uvsalt!!"
    user_key_salt = b"uksalt!!"
    u_hash = hashlib.sha256(password + user_validation_salt).digest()
    u_value = u_hash + user_validation_salt + user_key_salt
    ue_key = hashlib.sha256(password + user_key_salt).digest()
    ue = ssh_module._aes_cbc_no_padding_encrypt(ue_key, b"\x00" * 16, file_key)  # noqa: SLF001

    if owner_password is None:
        o_value = b"o" * 48
        oe = b"e" * 32
    else:
        owner_validation_salt = b"ovsalt!!"
        owner_key_salt = b"oksalt!!"
        o_hash = hashlib.sha256(owner_password + owner_validation_salt + u_value).digest()
        o_value = o_hash + owner_validation_salt + owner_key_salt
        oe_key = hashlib.sha256(owner_password + owner_key_salt + u_value).digest()
        oe = ssh_module._aes_cbc_no_padding_encrypt(oe_key, b"\x00" * 16, file_key)  # noqa: SLF001

    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(5)
    encryption.set_length(256)
    encryption.set_p(DEFAULT_PERMISSIONS)
    encryption.set_o(o_value)
    encryption.set_u(u_value)
    encryption.set_oe(oe)
    encryption.set_ue(ue)
    encryption.set_perms(perms)
    return encryption


def test_wave518_prepare_for_decryption_revision5_user_warns_on_bad_perms(
    caplog: pytest.LogCaptureFixture,
) -> None:
    file_key = b"k" * 32
    encryption = _revision5_encryption_for_password(b"user", file_key)
    handler = StandardSecurityHandler()

    with caplog.at_level(logging.WARNING):
        handler.prepare_for_decryption(
            encryption,
            b"",
            StandardDecryptionMaterial("user"),
        )

    assert handler.get_encryption_key() == file_key
    assert "Verification of /Perms failed" in caplog.text
    current = handler.get_current_access_permission()
    assert current is not None
    assert current.is_read_only() is True
    assert current.is_owner_permission() is False


def test_wave518_prepare_for_decryption_revision5_owner_gets_owner_access() -> None:
    file_key = b"z" * 32
    encryption = _revision5_encryption_for_password(
        b"user",
        file_key,
        owner_password=b"owner",
        perms=b"short",
    )
    handler = StandardSecurityHandler()

    handler.prepare_for_decryption(
        encryption,
        b"",
        StandardDecryptionMaterial("owner"),
    )

    current = handler.get_current_access_permission()
    assert handler.get_encryption_key() == file_key
    assert current is not None
    assert current.is_owner_permission() is True


def test_wave518_routing_helpers_handle_explicit_eff_and_aes_fallbacks() -> None:
    encryption = PDEncryption()
    encryption.set_v(4)
    encryption.set_stm_f("Identity")
    encryption.set_str_f("AESV2")
    encryption.set_eff("FileCF")
    file_cf = PDCryptFilterDictionary()
    file_cf.set_cfm("V2")
    encryption.set_crypt_filter_dictionary("FileCF", file_cf)

    handler = StandardSecurityHandler()
    handler._populate_routing_table(encryption)  # noqa: SLF001

    assert StandardSecurityHandler.get_stream_filter_name(encryption) == "Identity"
    assert StandardSecurityHandler.get_string_filter_name(encryption) == "AESV2"
    assert StandardSecurityHandler._is_aes_v4(encryption) is False  # noqa: SLF001
    encryption.set_stm_f("AESV3")
    assert StandardSecurityHandler._is_aes_v4(encryption) is True  # noqa: SLF001
    assert handler.get_stream_cfm() == "Identity"
    assert handler.get_string_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "V2"


def test_wave518_dispatch_encrypt_decrypt_round_trips_rc4_aesv2_and_aesv3() -> None:
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"\x01" * 32)
    payload = b"wave518 payload"

    rc4 = handler._dispatch_encrypt("V2", payload, 7, 0)  # noqa: SLF001
    assert rc4 != payload
    assert handler._dispatch_decrypt("V2", rc4, 7, 0) == payload  # noqa: SLF001

    aesv2 = handler._dispatch_encrypt("AESV2", payload, 7, 0)  # noqa: SLF001
    assert aesv2 != payload
    assert handler._dispatch_decrypt("AESV2", aesv2, 7, 0) == payload  # noqa: SLF001

    aesv3 = handler._dispatch_encrypt("AESV3", payload, 7, 0)  # noqa: SLF001
    assert aesv3 != payload
    assert handler._dispatch_decrypt("AESV3", aesv3, 7, 0) == payload  # noqa: SLF001


def test_wave518_prepare_document_for_encryption_alias_installs_aes256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Document:
        def __init__(self) -> None:
            self.encryption: PDEncryption | None = None

        def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
            self.encryption = encryption

    policy = StandardProtectionPolicy("owner", "user", AccessPermission())
    policy.set_encryption_key_length(256)
    handler = StandardSecurityHandler(policy)
    monkeypatch.setattr(
        handler,
        "_build_r6_dictionary",
        lambda _owner, _user, _permissions: (
            b"o" * 48,
            b"oe" * 16,
            b"u" * 48,
            b"ue" * 16,
            b"p" * 16,
        ),
    )
    document = Document()

    handler.prepare_document_for_encryption(document)

    assert document.encryption is not None
    assert document.encryption.get_revision() == 6
    assert document.encryption.get_v() == 5
    assert document.encryption.get_stm_f() == "StdCF"
    assert document.encryption.get_str_f() == "StdCF"
    assert handler.get_stream_cfm() == "AESV3"
    assert handler.is_aes() is True


def test_wave518_perms_validation_and_no_padding_helpers() -> None:
    file_key = b"\x02" * 32
    plain = bytearray(16)
    p = ssh_module._signed32(DEFAULT_PERMISSIONS)  # noqa: SLF001
    plain[0] = p & 0xFF
    plain[1] = (p >> 8) & 0xFF
    plain[2] = (p >> 16) & 0xFF
    plain[3] = (p >> 24) & 0xFF
    plain[8] = ord("F")
    plain[9:12] = b"adb"
    encrypted = ssh_module._aes_cbc_no_padding_encrypt(  # noqa: SLF001
        file_key,
        b"\x00" * 16,
        bytes(plain),
    )

    assert StandardSecurityHandler._decrypt_perms_r5_r6(file_key, encrypted) == bytes(plain)  # noqa: SLF001
    assert StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        file_key,
        encrypted,
        DEFAULT_PERMISSIONS,
        encrypt_metadata=False,
    )
    assert not StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        file_key,
        encrypted,
        DEFAULT_PERMISSIONS,
        encrypt_metadata=True,
    )
    assert ssh_module._aes_cbc_no_padding_decrypt(  # noqa: SLF001
        file_key,
        b"\x00" * 16,
        b"short",
    ) == b""


def test_wave518_prepare_document_default_policy_surface() -> None:
    class Document:
        def __init__(self) -> None:
            self.encryption: PDEncryption | None = None

        def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
            self.encryption = encryption

    policy = SimpleNamespace(
        get_owner_password=lambda: None,
        get_user_password=lambda: "user",
        get_permissions=lambda: None,
    )
    handler = StandardSecurityHandler(policy)
    document = Document()

    handler.prepare_document(document)

    assert document.encryption is not None
    assert document.encryption.get_revision() == 3
    assert document.encryption.get_length() == 128
    assert handler.get_permissions() == DEFAULT_PERMISSIONS
