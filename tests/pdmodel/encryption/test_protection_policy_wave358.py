from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption import (
    ProtectionPolicy,
    PublicKeyProtectionPolicy,
    StandardProtectionPolicy,
)


@pytest.mark.parametrize(
    "policy",
    [ProtectionPolicy(), StandardProtectionPolicy(), PublicKeyProtectionPolicy()],
)
def test_pdfbox_key_length_aliases_delegate(policy: ProtectionPolicy) -> None:
    assert policy.getEncryptionKeyLength() == policy.get_encryption_key_length()

    policy.setEncryptionKeyLength(128)

    assert policy.getEncryptionKeyLength() == 128
    assert policy.get_encryption_key_length() == 128


@pytest.mark.parametrize(
    "policy",
    [ProtectionPolicy(), StandardProtectionPolicy(), PublicKeyProtectionPolicy()],
)
def test_pdfbox_prefer_aes_aliases_delegate(policy: ProtectionPolicy) -> None:
    assert policy.isPreferAES() is False

    policy.setPreferAES(True)

    assert policy.isPreferAES() is True
    assert policy.is_prefer_aes() is True


def test_pdfbox_aliases_keep_base_validation_and_existing_values() -> None:
    policy = ProtectionPolicy()
    policy.setEncryptionKeyLength(256)
    policy.setPreferAES(True)

    with pytest.raises(TypeError, match="encryption key length must be an int"):
        policy.setEncryptionKeyLength(False)
    with pytest.raises(TypeError, match="prefer_aes must be a bool"):
        policy.setPreferAES("true")  # type: ignore[arg-type]

    assert policy.getEncryptionKeyLength() == 256
    assert policy.isPreferAES() is True
