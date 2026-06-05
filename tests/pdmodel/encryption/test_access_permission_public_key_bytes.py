"""Parity for ``AccessPermission.get_permission_bytes_for_public_key`` and the
public-key handler write path that consumes it.

Upstream ``PublicKeySecurityHandler#computeRecipientInfo`` (Java line 449) packs
``getPermissionBytesForPublicKey()`` — NOT the raw ``getPermissionBytes()`` —
into each recipient's 24-byte PKCS#7 plaintext. That helper deliberately
*differs* from ``/P``: it forces bit 1 ON, bits 7 and 8 OFF, and bits 13-32 OFF.
A typical owner/default permission set (raw ``/P == -4`` / ``0xFFFFFFFC``) is
therefore written to the public-key envelope as ``3901`` (``0x0F3D``), not as
``0xFFFFFFFC``.

The hard-coded expectations below were captured from live Apache PDFBox 3.0.7
(``new AccessPermission(p).getPermissionBytesForPublicKey()``) so the suite pins
the values WITHOUT requiring the oracle; an optional ``@requires_oracle``
differential re-verifies them against the running jar.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# (/P input, expected getPermissionBytesForPublicKey) — captured from Apache
# PDFBox 3.0.7 via `java PermProbe pubkey <p>`.
_PUBKEY_CASES = [
    (-44, 3861),
    (0, 1),
    (-3, 3901),
    (-3904, 1),
    (-1052, 2853),
    (4, 5),
    (2048, 2049),
    (-2, 3903),
    (-4, 3901),
    (0xFFFC, 3901),
    (2052, 2053),
    (-1900, 2069),
]


@pytest.mark.parametrize(
    ("p_value", "expected"), _PUBKEY_CASES, ids=[str(p) for p, _ in _PUBKEY_CASES]
)
def test_get_permission_bytes_for_public_key_matches_pdfbox(
    p_value: int, expected: int
) -> None:
    """Pinned against PDFBox 3.0.7 ``getPermissionBytesForPublicKey``."""
    assert AccessPermission(p_value).get_permission_bytes_for_public_key() == expected


def test_default_permission_public_key_bytes_is_3901() -> None:
    """The no-arg / owner permission set (raw /P == -4) is written to the
    public-key envelope as 3901 — bit 1 forced on, bits 7/8 + 13-32 cleared."""
    assert AccessPermission().get_permission_bytes_for_public_key() == 3901
    assert (
        AccessPermission.get_owner_access_permission()
        .get_permission_bytes_for_public_key()
        == 3901
    )


def test_get_permission_bytes_for_public_key_mutates_in_place() -> None:
    """Upstream's helper mutates ``bytes`` in place (it goes through
    ``setPermissionBit``); a subsequent ``get_permission_bytes`` returns the
    same value."""
    ap = AccessPermission(-44)
    pk = ap.get_permission_bytes_for_public_key()
    assert ap.get_permission_bytes() == pk == 3861


def test_get_permission_bytes_for_public_key_clears_bits_7_and_8() -> None:
    """Bits 7 and 8 (1-based) must be cleared; bit 1 must be set; bits 13+
    must be cleared — independent of input."""
    ap = AccessPermission(-1)  # every defined bit set on the wrapped value
    ap._bytes = -1  # force literal all-ones to exercise the masking directly
    pk = ap.get_permission_bytes_for_public_key()
    assert pk & (1 << 0)  # bit 1 (1-based) ON
    assert not pk & (1 << 6)  # bit 7 OFF
    assert not pk & (1 << 7)  # bit 8 OFF
    assert pk & ~0xFFF == 0  # bits 13-32 (and above) cleared
    assert pk == 3903


def _build_recipient_perm(p_value: int) -> AccessPermission:
    ap = AccessPermission()
    # Reset to an exact /P value via the private wrapped int.
    ap._bytes = p_value
    return ap


def test_public_key_write_path_packs_public_key_bytes() -> None:
    """The public-key handler must embed ``getPermissionBytesForPublicKey`` in
    each recipient envelope, not the raw ``/P`` — regression for the wave-1485
    fix. Mirrors upstream ``computeRecipientInfo`` line 449.
    """
    captured: list[bytes] = []

    class _FakeBuilder:
        def set_data(self, data: bytes) -> _FakeBuilder:
            captured.append(data)
            return self

        def add_recipient(self, _cert: object) -> _FakeBuilder:
            return self

        def set_content_encryption_algorithm(self, _alg: object) -> _FakeBuilder:
            return self

        def encrypt(self, *_a: object, **_k: object) -> bytes:
            return b"der"

    perms = _build_recipient_perm(-44)
    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(certificate=object(), permissions=perms)  # type: ignore[arg-type]
    )
    policy.set_encryption_key_length(128)

    import pypdfbox.pdmodel.encryption.public_key_security_handler as mod

    seed = b"s" * 20
    orig_builder = mod.pkcs7.PKCS7EnvelopeBuilder
    orig_urandom = mod.os.urandom
    mod.pkcs7.PKCS7EnvelopeBuilder = _FakeBuilder  # type: ignore[assignment]
    mod.os.urandom = lambda _n: seed  # type: ignore[assignment]
    try:
        handler = PublicKeySecurityHandler(policy)
        handler.prepare_document(_StubDoc())
    finally:
        mod.pkcs7.PKCS7EnvelopeBuilder = orig_builder  # type: ignore[assignment]
        mod.os.urandom = orig_urandom  # type: ignore[assignment]

    assert captured, "no recipient envelope was built"
    # /P == -44 → getPermissionBytesForPublicKey() == 3861.
    expected_tail = (3861).to_bytes(4, "big")
    assert captured[0] == seed + expected_tail


class _StubDoc:
    encryption = None

    def set_encryption_dictionary(self, e: object) -> None:
        self.encryption = e


# --------------------------------------------------------------- differential


@requires_oracle
@pytest.mark.parametrize(
    ("p_value", "expected"), _PUBKEY_CASES, ids=[str(p) for p, _ in _PUBKEY_CASES]
)
def test_public_key_bytes_differential(p_value: int, expected: int) -> None:
    """Live re-verification of the pinned constants against PDFBox 3.0.7."""
    raw = run_probe_text("PermProbe", "pubkey", str(p_value)).strip()
    _, _, value = raw.partition("=")
    java = int(value)
    assert java == expected
    assert AccessPermission(p_value).get_permission_bytes_for_public_key() == java
