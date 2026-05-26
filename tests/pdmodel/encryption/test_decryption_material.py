"""Tests for the abstract base ``DecryptionMaterial``.

Upstream (``DecryptionMaterial.java``) is an empty abstract base shared by
``StandardDecryptionMaterial`` (password) and ``PublicKeyDecryptionMaterial``
(certificate + private key). These tests verify the hierarchy is wired and that
re-parenting did not change subclass behavior.
"""

from __future__ import annotations

from pypdfbox.pdmodel.encryption.decryption_material import DecryptionMaterial
from pypdfbox.pdmodel.encryption.public_key_decryption_material import (
    PublicKeyDecryptionMaterial,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardDecryptionMaterial,
)


def test_standard_extends_decryption_material():
    assert issubclass(StandardDecryptionMaterial, DecryptionMaterial)


def test_public_key_extends_decryption_material():
    assert issubclass(PublicKeyDecryptionMaterial, DecryptionMaterial)


def test_base_has_no_own_members():
    # Upstream declares no members; the Python port adds none either.
    own = {n for n in vars(DecryptionMaterial) if not n.startswith("__")}
    assert own == set()


def test_standard_instance_is_decryption_material():
    material = StandardDecryptionMaterial("secret")
    assert isinstance(material, DecryptionMaterial)
    # Re-parenting must not change the password surface.
    assert material.get_password() == b"secret"
    assert material.get_password_str() == "secret"


def test_standard_none_password_round_trip():
    material = StandardDecryptionMaterial()
    assert isinstance(material, DecryptionMaterial)
    assert material.get_password() is None


def test_public_key_instance_is_decryption_material():
    material = PublicKeyDecryptionMaterial()
    assert isinstance(material, DecryptionMaterial)
    # Empty material: no certificate / private key set.
    assert material.get_certificate() is None
    assert material.get_private_key() is None
