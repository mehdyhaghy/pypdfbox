from __future__ import annotations

from collections.abc import Iterator

import pytest

from pypdfbox.cos import COSArray, COSDocument, COSName
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.security_provider import (
    get_security_handler,
    register_security_handler,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    DEFAULT_PERMISSIONS,
    InvalidPasswordException,
    StandardDecryptionMaterial,
    StandardSecurityHandler,
)


class _BareHandler(SecurityHandler):
    def prepare_for_decryption(
        self,
        encryption: object,
        document_id: bytes,
        decryption_material: object,
    ) -> None:
        pass

    def prepare_document(self, document: object) -> None:
        pass


def test_standard_encrypt_stream_uses_v4_routing_table() -> None:
    handler = StandardSecurityHandler()
    handler._stream_cfm = "Identity"  # noqa: SLF001

    assert handler.encrypt_stream(b"plain", 7, 0) == b"plain"


def test_standard_prepare_for_decryption_rejects_invalid_r6_key_material() -> None:
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(5)
    encryption.set_revision(6)
    encryption.set_length(256)
    encryption.set_p(DEFAULT_PERMISSIONS)
    encryption.set_o(b"o" * 48)
    encryption.set_u(b"u" * 48)
    encryption.set_oe(b"e" * 32)
    encryption.set_ue(b"k" * 32)
    encryption.set_perms(b"p" * 16)

    with pytest.raises(InvalidPasswordException):
        StandardSecurityHandler().prepare_for_decryption(
            encryption,
            b"",
            StandardDecryptionMaterial("wrong"),
        )


def test_standard_prepare_for_decryption_requires_legacy_o_and_u_entries() -> None:
    encryption = PDEncryption()
    encryption.set_filter("Standard")
    encryption.set_v(2)
    encryption.set_revision(3)
    encryption.set_length(128)
    encryption.set_p(DEFAULT_PERMISSIONS)

    with pytest.raises(InvalidPasswordException):
        StandardSecurityHandler().prepare_for_decryption(
            encryption,
            b"doc-id",
            StandardDecryptionMaterial("user"),
        )


def test_standard_extract_document_id_defaults_for_empty_id_array() -> None:
    document = COSDocument()
    document.set_document_id(COSArray())

    assert (
        StandardSecurityHandler._extract_document_id(document, b"default")  # noqa: SLF001
        == b"default"
    )


def test_standard_compute_key_includes_metadata_suppression_marker() -> None:
    args = (b"password", b"o" * 32, DEFAULT_PERMISSIONS, b"doc-id", 4, 16)

    encrypted_metadata_key = StandardSecurityHandler._compute_encryption_key(  # noqa: SLF001
        *args,
        encrypt_metadata=True,
    )
    clear_metadata_key = StandardSecurityHandler._compute_encryption_key(  # noqa: SLF001
        *args,
        encrypt_metadata=False,
    )

    assert clear_metadata_key != encrypted_metadata_key


def test_standard_r6_key_helpers_report_mismatches_and_short_owner_entries() -> None:
    assert (
        StandardSecurityHandler._compute_encryption_key_r5_r6(  # noqa: SLF001
            b"password",
            b"o" * 48,
            b"u" * 48,
            b"e" * 32,
            b"k" * 32,
            b"p" * 16,
            6,
        )
        is None
    )
    assert (
        StandardSecurityHandler._is_owner_password_r5_r6(  # noqa: SLF001
            b"password",
            b"short",
            b"u" * 48,
            6,
        )
        is False
    )


def test_standard_r6_dictionary_creates_missing_file_key(monkeypatch) -> None:
    chunks: Iterator[bytes] = iter(
        [
            b"f" * 32,
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

    _o, _oe, _u, _ue, _perms = handler._build_r6_dictionary(  # noqa: SLF001
        b"owner",
        b"user",
        DEFAULT_PERMISSIONS,
    )

    assert handler.get_encryption_key() == b"f" * 32


def test_security_handler_compute_object_key_requires_file_key() -> None:
    with pytest.raises(ValueError, match="encryption_key not set"):
        _BareHandler().compute_object_key(1, 0)


def test_security_handler_aes_round_trip_uses_aes_decrypt_branch() -> None:
    handler = _BareHandler()
    handler.set_revision(4)
    handler.set_aes(True)
    handler.set_encryption_key(b"k" * 16)

    ciphertext = handler.encrypt_data(b"secret", 12, 0)

    assert handler.decrypt_data(ciphertext, 12, 0) == b"secret"


def test_security_handler_aes_decrypt_matches_upstream_iv_and_padding() -> None:
    """Retargeted in wave 1532 to the oracle-proven ``SecurityHandler``
    decrypt-data contract (was a pre-1532 stub asserting the old over-tolerant
    behaviour). Upstream ``prepareAESInitializationVector`` raises on a partial
    IV (``0 < n < 16``); the AES-256 ``CipherInputStream`` path silently drops a
    bad final block. See ``oracle/test_decrypt_data_fuzz_wave1532.py``."""
    import pytest

    from pypdfbox.pdmodel.encryption.security_handler import _aes_cbc_decrypt

    key = b"\x00" * 16

    # Partial IV (5 of 16 bytes) → IOException upstream → OSError here.
    with pytest.raises(OSError):
        _aes_cbc_decrypt(key, b"short")  # noqa: SLF001
    # Empty input → silent zero-length skip (IV read returns 0).
    assert _aes_cbc_decrypt(key, b"") == b""  # noqa: SLF001
    # IV only (no ciphertext) → empty output.
    assert _aes_cbc_decrypt(key, b"\xaa" * 16) == b""  # noqa: SLF001
    # IV + one bad-padding block, tolerant (AES-256) → final block dropped → empty.
    assert _aes_cbc_decrypt(key, b"\xaa" * 32) == b""  # noqa: SLF001
    # Same input, strict (AES-128 per-object) → raises.
    with pytest.raises(OSError):
        _aes_cbc_decrypt(key, b"\xaa" * 32, tolerant_padding=False)  # noqa: SLF001


def test_pd_encryption_preserves_owner_key_length_for_unknown_revision() -> None:
    encryption = PDEncryption()
    encryption.set_revision(7)
    encryption.set_owner_key(b"raw")

    assert encryption.get_owner_key() == b"raw"


def test_pd_encryption_recipient_string_at_returns_none_for_non_string() -> None:
    encryption = PDEncryption()
    encryption.get_cos_object().set_item(
        "Recipients",
        COSArray([COSName.get_pdf_name("NotAString")]),
    )

    assert encryption.get_recipient_string_at(0) is None


def test_security_provider_registers_custom_handler_class() -> None:
    register_security_handler("Wave755Custom", _BareHandler)

    assert isinstance(get_security_handler("Wave755Custom"), _BareHandler)
