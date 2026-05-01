"""Hand-written coverage for :class:`PublicKeyProtectionPolicy`.

Exercises the recipient list, the optional decryption-certificate slot,
and the inherited ``ProtectionPolicy`` behaviour (key length / prefer
AES). No actual envelope encryption is exercised here — that lives in
``test_public_key_security_handler*``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption import (
    PublicKeyProtectionPolicy,
    PublicKeyRecipient,
)
from pypdfbox.pdmodel.encryption.protection_policy import (
    DEFAULT_KEY_LENGTH,
    ProtectionPolicy,
)


def test_inherits_protection_policy() -> None:
    assert issubclass(PublicKeyProtectionPolicy, ProtectionPolicy)


def test_default_state() -> None:
    policy = PublicKeyProtectionPolicy()
    assert policy.get_number_of_recipients() == 0
    assert policy.get_recipients() == []
    assert policy.get_decryption_certificate() is None
    # Inherited defaults from ProtectionPolicy.
    assert policy.get_encryption_key_length() == DEFAULT_KEY_LENGTH
    assert policy.is_prefer_aes() is False


def test_add_recipient_grows_list_in_order() -> None:
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    r2 = PublicKeyRecipient()
    r3 = PublicKeyRecipient()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.add_recipient(r3)
    assert policy.get_number_of_recipients() == 3
    assert policy.get_recipients() == [r1, r2, r3]


def test_get_recipients_returns_live_list() -> None:
    # Upstream ``getRecipientsIterator`` walks the live collection — the
    # accessor must not return a defensive copy or downstream callers that
    # mutate it (e.g. ``PublicKeySecurityHandler.add_recipient``) would
    # silently no-op.
    policy = PublicKeyProtectionPolicy()
    recipients = policy.get_recipients()
    recipients.append(PublicKeyRecipient())
    assert policy.get_number_of_recipients() == 1


def test_remove_recipient_returns_true_when_present() -> None:
    policy = PublicKeyProtectionPolicy()
    r = PublicKeyRecipient()
    policy.add_recipient(r)
    assert policy.remove_recipient(r) is True
    assert policy.get_number_of_recipients() == 0


def test_remove_recipient_returns_false_when_absent() -> None:
    policy = PublicKeyProtectionPolicy()
    assert policy.remove_recipient(PublicKeyRecipient()) is False


def test_decryption_certificate_round_trip() -> None:
    policy = PublicKeyProtectionPolicy()
    sentinel = object()  # opaque cert stand-in — accessor is type-erased.
    policy.set_decryption_certificate(sentinel)  # type: ignore[arg-type]
    assert policy.get_decryption_certificate() is sentinel
    policy.set_decryption_certificate(None)
    assert policy.get_decryption_certificate() is None


def test_inherited_key_length_validation() -> None:
    policy = PublicKeyProtectionPolicy()
    policy.set_encryption_key_length(128)
    assert policy.get_encryption_key_length() == 128
    policy.set_encryption_key_length(256)
    assert policy.get_encryption_key_length() == 256
    with pytest.raises(ValueError):
        policy.set_encryption_key_length(64)


def test_prefer_aes_round_trip() -> None:
    policy = PublicKeyProtectionPolicy()
    policy.set_prefer_aes(True)
    assert policy.is_prefer_aes() is True
    policy.set_prefer_aes(False)
    assert policy.is_prefer_aes() is False


def test_get_recipients_iterator_empty() -> None:
    policy = PublicKeyProtectionPolicy()
    it = policy.get_recipients_iterator()
    # Behaves like Java's ``Iterator`` — exhausted iterator on empty list.
    assert list(it) == []


def test_get_recipients_iterator_walks_in_insertion_order() -> None:
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    r2 = PublicKeyRecipient()
    r3 = PublicKeyRecipient()
    policy.add_recipient(r1)
    policy.add_recipient(r2)
    policy.add_recipient(r3)
    walked = list(policy.get_recipients_iterator())
    assert walked == [r1, r2, r3]


def test_get_recipients_iterator_returns_iterator_protocol() -> None:
    # Must be a single-pass iterator (matches Java ``Iterator``), not the
    # underlying list — calling next() on it should pull elements one by one
    # and a fresh call to the method gives a fresh iterator.
    policy = PublicKeyProtectionPolicy()
    r1 = PublicKeyRecipient()
    policy.add_recipient(r1)
    it = policy.get_recipients_iterator()
    assert iter(it) is it  # iterator protocol
    assert next(it) is r1
    with pytest.raises(StopIteration):
        next(it)
    # A second call returns a fresh iterator from the start of the list.
    again = policy.get_recipients_iterator()
    assert next(again) is r1
