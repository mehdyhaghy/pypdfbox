from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from pypdfbox.pdmodel.encryption import PublicKeyDecryptionMaterial


def test_wave328_private_key_bytearray_is_snapshotted_for_lazy_decode() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = bytearray(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    material = PublicKeyDecryptionMaterial(private_key=pem)
    pem[:] = b"mutated after material construction"

    assert material.get_private_key() is not None
