"""Wave 1399 — close residual partial branches on ``public_key_security_handler``.

Targets the 3 partial arrows surviving after wave 1396:

* 130->123 — the recipient-envelope decrypt loop sees ``pkcs7_decrypt_der``
  return ``None`` (decrypt "succeeded" but produced no plaintext) and
  loops to the next blob.
* 149->160 — a decrypted envelope of *exactly* 20 bytes (seed only, no
  per-recipient permissions tail) is rejected (wave 1501: upstream requires
  exactly 24 bytes — a seed-only envelope is "does not contain 24 bytes").
* 683->686 — ``compute_version_number`` with a policy whose
  ``get_encryption_key_length()`` returns a falsy value (e.g. 0) keeps
  the handler's default key length.
"""
from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.public_key_decryption_material import (
    PublicKeyDecryptionMaterial,
)
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)

# ---------- shared self-signed cert helper (mirrors wave 1318 pattern) -------


def _self_signed_rsa() -> tuple[object, object]:
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wave1399-recipient")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


# ---------- 130->123 — pkcs7_decrypt_der returns None mid-loop --------------


def test_prepare_for_decryption_pkcs7_returns_none_continues_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``pkcs7_decrypt_der`` returns ``None`` for the first recipient
    blob (decrypt completed without raising but produced no plaintext),
    the loop continues to the next blob. Closes the False arm of the
    ``envelope_plaintext is not None`` guard at line 130."""
    cert, key = _self_signed_rsa()
    material = PublicKeyDecryptionMaterial()
    material._certificate = cert  # type: ignore[assignment]
    material._private_key_raw = key  # type: ignore[assignment]

    # Build a two-blob /Recipients array. The pkcs7 patch returns None on
    # the first blob, a synthetic 24-byte envelope (20-byte seed + 4-byte
    # perms) on the second so the call ultimately succeeds.
    encryption = PDEncryption()
    encryption.set_recipients([b"first-blob-bytes", b"second-blob-bytes"])
    # Pre-set V/R/length so the V=5/V=4 dispatch downstream can run.
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)

    sequence: list[bytes | None] = [None, b"\xAA" * 20 + b"\x00\x00\x00\x10"]

    def _patched_pkcs7_decrypt_der(blob, _cert, _key, options=None):  # noqa: ARG001
        return sequence.pop(0)

    monkeypatch.setattr(
        "pypdfbox.pdmodel.encryption.public_key_security_handler.pkcs7.pkcs7_decrypt_der",
        _patched_pkcs7_decrypt_der,
    )

    handler = PublicKeySecurityHandler()
    # Must not raise — second blob's plaintext drives the rest of the call.
    handler.prepare_for_decryption(encryption, b"\x00" * 16, material)
    # Sanity: the loop made it through both blobs.
    assert sequence == []


# ---------- 149->160 — envelope is exactly 20 bytes (seed only) -------------


def test_prepare_for_decryption_envelope_seed_only_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A decrypted envelope of exactly 20 bytes (just the seed, no 4-byte
    permission tail) is REJECTED — upstream
    PublicKeySecurityHandler#prepareForDecryption requires exactly 24 bytes
    ("the enveloped data does not contain 24 bytes") and never tolerates a
    seed-only envelope."""
    cert, key = _self_signed_rsa()
    material = PublicKeyDecryptionMaterial()
    material._certificate = cert  # type: ignore[assignment]
    material._private_key_raw = key  # type: ignore[assignment]

    encryption = PDEncryption()
    encryption.set_recipients([b"single-blob"])
    encryption.set_v(4)
    encryption.set_revision(4)
    encryption.set_length(128)

    # Exactly 20 bytes — upstream rejects (not 24).
    monkeypatch.setattr(
        "pypdfbox.pdmodel.encryption.public_key_security_handler.pkcs7.pkcs7_decrypt_der",
        lambda *_args, **_kwargs: b"\xBB" * 20,
    )

    handler = PublicKeySecurityHandler()
    with pytest.raises(ValueError, match="does not contain 24 bytes"):
        handler.prepare_for_decryption(encryption, b"\x00" * 16, material)


# ---------- 683->686 — compute_version_number with policy length = 0 --------


def test_compute_version_number_policy_length_zero_keeps_handler_default() -> None:
    """A policy whose ``get_encryption_key_length`` returns 0 (falsy)
    leaves the handler's previously-set ``_key_length`` untouched.
    Closes the False arm of the ``if policy_length:`` guard at L683."""

    class _ZeroLengthPolicy(PublicKeyProtectionPolicy):
        def get_encryption_key_length(self) -> int:
            return 0

    policy = _ZeroLengthPolicy()
    handler = PublicKeySecurityHandler(policy)
    handler.set_key_length(40)  # handler default kept since policy is falsy.
    # Default-fall-through: 40-bit key → /V=1 (RC4-40).
    assert handler.compute_version_number() == 1
