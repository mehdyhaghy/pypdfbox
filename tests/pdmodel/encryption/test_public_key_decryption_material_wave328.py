from cryptography.hazmat.primitives import serialization

from pypdfbox.pdmodel.encryption import PublicKeyDecryptionMaterial
from tests._rsa_key_pool import pooled_rsa_key


def test_wave328_private_key_bytearray_is_snapshotted_for_lazy_decode() -> None:
    key = pooled_rsa_key()
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
