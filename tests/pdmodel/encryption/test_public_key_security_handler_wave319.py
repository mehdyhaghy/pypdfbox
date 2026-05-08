from __future__ import annotations

import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)


def _build_wave319_self_signed_rsa() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-wave319")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(private_key, hashes.SHA256())
    )
    return cert, private_key


class _Wave319Document:
    def __init__(self) -> None:
        self.encryption: PDEncryption | None = None

    def set_encryption_dictionary(self, encryption: PDEncryption) -> None:
        self.encryption = encryption


def test_wave319_prepare_document_marks_recipients_array_direct() -> None:
    cert, _private_key = _build_wave319_self_signed_rsa()

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(
            certificate=cert,
            permissions=AccessPermission(),
        )
    )

    document = _Wave319Document()
    PublicKeySecurityHandler(protection_policy=policy).prepare_document(document)

    assert document.encryption is not None
    recipients = document.encryption.get_recipients()
    assert recipients is not None
    assert recipients.size() == 1
    assert recipients.is_direct() is True
