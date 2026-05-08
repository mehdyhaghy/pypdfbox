from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption import (
    ProtectionPolicy,
    PublicKeyProtectionPolicy,
    StandardProtectionPolicy,
)


def test_set_prefer_aes_rejects_non_bool_without_changing_existing_value() -> None:
    policy = ProtectionPolicy()
    policy.set_prefer_aes(True)

    with pytest.raises(TypeError, match="prefer_aes must be a bool"):
        policy.set_prefer_aes("false")  # type: ignore[arg-type]

    assert policy.is_prefer_aes() is True


def test_set_prefer_aes_type_guard_is_inherited_by_policy_subclasses() -> None:
    for policy in (StandardProtectionPolicy(), PublicKeyProtectionPolicy()):
        with pytest.raises(TypeError, match="prefer_aes must be a bool"):
            policy.set_prefer_aes(1)  # type: ignore[arg-type]

        assert policy.is_prefer_aes() is False


def test_set_encryption_key_length_rejects_non_int_without_changing_existing_value() -> None:
    policy = ProtectionPolicy()
    policy.set_encryption_key_length(128)

    with pytest.raises(TypeError, match="encryption key length must be an int"):
        policy.set_encryption_key_length(256.0)  # type: ignore[arg-type]

    assert policy.get_encryption_key_length() == 128


def test_set_encryption_key_length_rejects_bool_despite_int_subclassing() -> None:
    policy = ProtectionPolicy()

    with pytest.raises(TypeError, match="encryption key length must be an int"):
        policy.set_encryption_key_length(True)

    assert policy.get_encryption_key_length() == ProtectionPolicy.DEFAULT_KEY_LENGTH
