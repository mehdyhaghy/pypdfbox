"""Hand-written coverage for :class:`PublicKeyRecipient`.

Plain POPO holder — one X.509 certificate paired with one
:class:`AccessPermission`. Tests cover constructor variants and the
get/set accessors only; the encryption envelope is built elsewhere.
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption import (
    AccessPermission,
    PublicKeyRecipient,
)


def test_default_state() -> None:
    recipient = PublicKeyRecipient()
    assert recipient.get_x509() is None
    assert recipient.get_permission() is None


def test_constructor_assigns_fields() -> None:
    sentinel_cert = object()  # opaque cert stand-in
    permission = AccessPermission()
    recipient = PublicKeyRecipient(
        certificate=sentinel_cert,  # type: ignore[arg-type]
        permissions=permission,
    )
    assert recipient.get_x509() is sentinel_cert
    assert recipient.get_permission() is permission


def test_x509_setter_round_trip() -> None:
    recipient = PublicKeyRecipient()
    sentinel = object()
    recipient.set_x509(sentinel)  # type: ignore[arg-type]
    assert recipient.get_x509() is sentinel
    recipient.set_x509(None)
    assert recipient.get_x509() is None


def test_permission_setter_round_trip() -> None:
    recipient = PublicKeyRecipient()
    permission = AccessPermission()
    recipient.set_permission(permission)
    assert recipient.get_permission() is permission
    recipient.set_permission(None)
    assert recipient.get_permission() is None


def test_permission_bits_preserved_through_recipient() -> None:
    permission = AccessPermission()
    permission.set_can_print(False)
    permission.set_can_modify(False)
    recipient = PublicKeyRecipient(permissions=permission)
    held = recipient.get_permission()
    assert held is not None
    assert held.can_print() is False
    assert held.can_modify() is False
