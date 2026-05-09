from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler
from pypdfbox.pdmodel.encryption.security_provider import (
    get_security_handler,
    is_registered,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)


class _TailHandler(SecurityHandler):
    def prepare_for_decryption(
        self,
        encryption: object,
        document_id: bytes,
        decryption_material: object,
    ) -> None:
        pass

    def prepare_document(self, document: object) -> None:
        pass


def test_security_handler_reads_file_like_input_and_uses_r5_file_key_directly() -> None:
    handler = _TailHandler()
    handler.set_revision(5)
    handler.set_encryption_key(b"k" * 32)

    ciphertext = handler.encrypt_data(io.BytesIO(b"stream bytes"), 99, 0)

    assert handler.compute_object_key(99, 0) == b"k" * 32
    assert handler.decrypt_data(io.BytesIO(ciphertext), 99, 0) == b"stream bytes"


def test_security_handler_base_algorithm_placeholders_raise() -> None:
    handler = _TailHandler()

    with pytest.raises(NotImplementedError, match="compute_encrypted_key"):
        handler.compute_encrypted_key(b"password")
    with pytest.raises(NotImplementedError, match="compute_user_password"):
        handler.compute_user_password(b"password")
    with pytest.raises(NotImplementedError, match="compute_owner_password"):
        handler.compute_owner_password(b"owner", b"user")


def test_pd_encryption_crypt_filter_helpers_and_v45_cleanup() -> None:
    encryption = PDEncryption()
    std_cf = PDCryptFilterDictionary()
    std_cf.set_cfm("AESV2")

    encryption.set_crypt_filter_dictionary(COSName.get_pdf_name("StdCF"), std_cf)
    encryption.set_stream_filter_name("StdCF")
    encryption.set_string_filter_name("StdCF")
    encryption.set_eff("StdCF")

    resolved = encryption.get_std_crypt_filter_dictionary()
    assert resolved is not None
    assert resolved.get_cfm() == "AESV2"
    assert resolved.get_cos_object().is_direct() is True
    assert encryption.get_stream_filter_name() == "StdCF"
    assert encryption.get_string_filter_name() == "StdCF"
    assert encryption.has_eff() is True

    encryption.remove_v45_filters()

    assert encryption.get_cf() is None
    assert encryption.get_stream_filter_name() == "Identity"
    assert encryption.get_string_filter_name() == "Identity"
    assert encryption.has_eff() is False


def test_pd_encryption_recipients_and_revision_key_padding_tails() -> None:
    encryption = PDEncryption()

    encryption.set_recipients([b"one", b"two"])
    recipients = encryption.get_recipients()
    assert recipients is not None
    assert recipients.is_direct() is True
    assert encryption.get_recipients_length() == 2
    assert encryption.get_recipient_string_at(1).get_bytes() == b"two"

    encryption.get_cos_object().set_item(
        "Recipients",
        COSArray([COSString(b"ok"), COSName.get_pdf_name("NotAString")]),
    )
    assert encryption.get_recipient_string_at(1) is None

    encryption.set_revision(6)
    encryption.set_owner_key(b"owner")
    encryption.set_user_key(b"user")

    assert encryption.get_owner_key() == b"owner" + (b"\x00" * 43)
    assert encryption.get_user_key() == b"user" + (b"\x00" * 44)


def test_standard_security_handler_embedded_filter_uses_stream_default() -> None:
    handler = StandardSecurityHandler()
    handler.set_encryption_key(b"k" * 16)
    handler.set_revision(4)
    handler.set_aes(True)
    encryption = PDEncryption()
    encryption.set_v(4)
    encryption.set_stm_f("Identity")

    handler._populate_routing_table(encryption)  # noqa: SLF001

    assert handler.get_embedded_file_cfm() == "Identity"
    assert handler.encrypt_stream(b"embedded", 7, 0, is_embedded_file=True) == b"embedded"
    assert handler.decrypt_stream(b"embedded", 7, 0, is_embedded_file=True) == b"embedded"


def test_security_provider_reports_registered_and_unknown_filters() -> None:
    assert is_registered("Standard") is True
    assert is_registered("Wave791Missing") is False

    with pytest.raises(ValueError, match="Unsupported security handler"):
        get_security_handler("Wave791Missing")
