from __future__ import annotations

from typing import cast

from cryptography.x509 import Certificate

from pypdfbox.pdmodel.encryption import PublicKeyProtectionPolicy, PublicKeyRecipient


def test_wave320_public_key_policy_pdfbox_recipient_aliases_delegate() -> None:
    policy = PublicKeyProtectionPolicy()
    first = PublicKeyRecipient()
    second = PublicKeyRecipient()

    policy.addRecipient(first)
    policy.addRecipient(second)

    assert policy.getNumberOfRecipients() == 2
    assert policy.getRecipientsNumber() == 2
    assert policy.get_recipients_number() == 2
    iterator = policy.getRecipientsIterator()
    assert iter(iterator) is iterator
    assert list(iterator) == [first, second]
    assert policy.removeRecipient(first) is True
    assert policy.removeRecipient(first) is False
    assert policy.getNumberOfRecipients() == 1


def test_wave320_public_key_policy_pdfbox_decryption_certificate_aliases() -> None:
    policy = PublicKeyProtectionPolicy()
    certificate = cast(Certificate, object())

    policy.setDecryptionCertificate(certificate)

    assert policy.getDecryptionCertificate() is certificate
    assert policy.get_decryption_certificate() is certificate
    policy.setDecryptionCertificate(None)
    assert policy.getDecryptionCertificate() is None
