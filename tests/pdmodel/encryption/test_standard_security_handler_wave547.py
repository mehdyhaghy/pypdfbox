from __future__ import annotations

from collections.abc import Iterator

from pypdfbox.cos import COSArray, COSDocument, COSName, COSString
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    DEFAULT_PERMISSIONS,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


def test_wave547_real_r6_dictionary_validates_user_and_owner_passwords() -> None:
    file_key = bytes(range(32))
    handler = StandardSecurityHandler()
    handler.set_encryption_key(file_key)
    handler._encrypt_metadata = False  # noqa: SLF001

    o, oe, u, ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner",
        b"user",
        DEFAULT_PERMISSIONS,
    )
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(DEFAULT_PERMISSIONS)
    encryption.set_encrypt_meta_data(False)
    encryption.set_o(o)
    encryption.set_oe(oe)
    encryption.set_u(u)
    encryption.set_ue(ue)
    encryption.set_perms(perms)

    user_handler = StandardSecurityHandler()
    user_handler.prepare_for_decryption(
        encryption,
        b"",
        StandardDecryptionMaterial("user"),
    )
    owner_handler = StandardSecurityHandler()
    owner_handler.prepare_for_decryption(
        encryption,
        b"",
        StandardDecryptionMaterial("owner"),
    )

    assert len(o) == 48
    assert len(u) == 48
    assert user_handler.get_encryption_key() == file_key
    assert owner_handler.get_encryption_key() == file_key
    assert user_handler.get_current_access_permission() is not None
    assert owner_handler.get_current_access_permission() is not None
    assert user_handler.get_current_access_permission().is_owner_permission() is False
    assert owner_handler.get_current_access_permission().is_owner_permission() is True


def test_wave547_extract_document_id_handles_direct_cos_document_and_bad_entries() -> None:
    direct = COSDocument()
    direct.set_document_id(COSArray([COSString(b"direct-id")]))
    bad = COSDocument()
    bad.set_document_id(COSArray([COSName.get_pdf_name("NotString")]))

    assert StandardSecurityHandler._extract_document_id(direct, b"default") == b"direct-id"  # noqa: SLF001
    assert StandardSecurityHandler._extract_document_id(bad, b"default") == b"default"  # noqa: SLF001
    assert StandardSecurityHandler._extract_document_id(object(), b"default") == b"default"  # noqa: SLF001


def test_wave547_populate_routing_table_clears_state_for_legacy_versions() -> None:
    handler = StandardSecurityHandler()
    handler._stream_cfm = "AESV2"  # noqa: SLF001
    handler._string_cfm = "V2"  # noqa: SLF001
    handler._embedded_file_cfm = "Identity"  # noqa: SLF001
    encryption = PDEncryption()
    encryption.set_v(2)

    handler._populate_routing_table(encryption)  # noqa: SLF001

    assert handler.get_stream_cfm() is None
    assert handler.get_string_cfm() is None
    assert handler.get_embedded_file_cfm() is None


def test_wave547_is_aes_v4_uses_crypt_filter_cfm_over_filter_name() -> None:
    encryption = PDEncryption()
    encryption.set_v(4)
    encryption.set_stm_f("StdCF")
    std_cf = PDCryptFilterDictionary()
    std_cf.set_cfm("V2")
    encryption.set_std_crypt_filter_dictionary(std_cf)

    assert StandardSecurityHandler._is_aes_v4(encryption) is False  # noqa: SLF001

    std_cf.set_cfm("AESV2")
    assert StandardSecurityHandler._is_aes_v4(encryption) is True  # noqa: SLF001


def test_wave547_aes_decrypt_helpers_match_upstream_iv_and_padding() -> None:
    # Retargeted in wave 1532 to the oracle-proven SecurityHandler decrypt
    # contract (was a pre-1532 stub asserting over-tolerant short/bad-padding
    # behaviour). AESV2 (16-byte key) routes through the strict
    # Cipher.update+doFinal path: a partial IV and bad padding both raise; an
    # AESV3 (32-byte key) payload uses the tolerant CipherInputStream path. See
    # oracle/test_decrypt_data_fuzz_wave1532.py.
    import pytest

    from pypdfbox.pdmodel.encryption import standard_security_handler as ssh_module

    key16 = b"k" * 16
    key32 = b"k" * 32
    iv = b"i" * 16
    bad_block = ssh_module._aes_cbc_no_padding_encrypt(  # noqa: SLF001
        key16, iv, b"not-pkcs7-paddin"  # exactly one 16-byte block
    )

    # Empty / IV-only → empty in both modes.
    assert ssh_module._aes128_cbc_decrypt(key16, b"") == b""  # noqa: SLF001
    assert ssh_module._aes128_cbc_decrypt(key16, iv) == b""  # noqa: SLF001
    # Partial IV (5 of 16) → raises (project-wide I/O mapping).
    with pytest.raises(OSError):
        ssh_module._aes128_cbc_decrypt(key16, b"short")  # noqa: SLF001
    # AESV2 (strict) bad padding → raises.
    with pytest.raises(OSError):
        ssh_module._aes128_cbc_decrypt(key16, iv + bad_block)  # noqa: SLF001
    # AESV3 (tolerant) single bad block → final block dropped → empty.
    bad_block32 = ssh_module._aes_cbc_no_padding_encrypt(  # noqa: SLF001
        key32, iv, b"not-pkcs7-paddin"
    )
    assert (
        ssh_module._aes128_cbc_decrypt(key32, iv + bad_block32) == b""  # noqa: SLF001
    )


def test_wave547_r6_dictionary_uses_existing_key_and_random_salts(
    monkeypatch,
) -> None:
    chunks: Iterator[bytes] = iter(
        [
            b"user-vs!",
            b"user-ks!",
            b"ownr-vs!",
            b"ownr-ks!",
            b"tail",
        ]
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.encryption.standard_security_handler.os.urandom",
        lambda size: next(chunks).ljust(size, b"!")[:size],
    )
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"f" * 32)

    o, _oe, u, _ue, perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner",
        b"user",
        DEFAULT_PERMISSIONS,
    )

    assert u[32:40] == b"user-vs!"
    assert u[40:48] == b"user-ks!"
    assert o[32:40] == b"ownr-vs!"
    assert o[40:48] == b"ownr-ks!"
    assert StandardSecurityHandler._validate_perms_r5_r6(  # noqa: SLF001
        b"f" * 32,
        perms,
        DEFAULT_PERMISSIONS,
        encrypt_metadata=True,
    )
