"""Ported upstream tests for ``PublicKeyEncryption``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/encryption/TestPublicKeyEncryption.java``
(PDFBox 3.0.x).

Upstream's test exercises the full PDF round-trip
(``PublicKeyProtectionPolicy.protect`` → ``Loader.loadPDF(file,
keyStore, password)`` decrypt → text-strip parity) across three key
lengths (40 / 128 / 256) using ``.der`` + ``.pfx`` certificate fixtures
plus ``AES{128,256}ExposedMeta.pdf`` / ``AESkeylength{128,256}.pdf``
sample documents.

The pypdfbox port's ``Loader.load_pdf`` API does not (yet) accept a
keystore argument — the structural / handler-level slice of the
upstream coverage already lives in
``tests/pdmodel/encryption/upstream/test_public_key_security_handler.py``
(mints a fresh self-signed cert via the ``cryptography`` library and
exercises ``prepare_document`` / ``prepare_for_decryption`` directly).
The Java-fixture-driven scenarios below are therefore skipped with a
one-line reason each.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="upstream parameterises 'testProtectionError' across "
    "keyLengths={40,128,256} and decrypts via a .pfx keystore + password — "
    "pypdfbox's Loader.load_pdf signature does not expose a keystore "
    "parameter, and the cross-recipient mismatch error contract "
    "('serial-#: rid 2 vs. cert 3') is bouncycastle-specific. The "
    "handler-level slice lives in test_public_key_security_handler.py."
)
def test_protection_error() -> None: ...


@pytest.mark.skip(
    reason="upstream parameterises 'testProtection' across "
    "keyLengths={40,128,256} and round-trips via .pfx keystore reload — "
    "pypdfbox's Loader.load_pdf does not accept a keystore. Direct "
    "handler-level prepare_document / prepare_for_decryption parity is "
    "covered in test_public_key_security_handler.py."
)
def test_protection() -> None: ...


@pytest.mark.skip(
    reason="upstream parameterises 'testMultipleRecipients' across "
    "keyLengths={40,128,256}, exercising a two-recipient policy via a "
    "live PDF round-trip with .pfx keystores — pypdfbox's Loader.load_pdf "
    "does not accept a keystore. The recipient-count assertion is "
    "covered by test_protection_policy_tracks_recipients in "
    "test_public_key_security_handler.py."
)
def test_multiple_recipients() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-4421: requires AESkeylength128.pdf + PDFBOX-4421-keystore.pfx "
    "fixtures plus a keystore-aware Loader.load_pdf signature; "
    "pypdfbox's Loader.load_pdf accepts only the password parameter."
)
def test_read_pubkey_encrypted_aes128() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-4421: requires AESkeylength256.pdf + PDFBOX-4421-keystore.pfx "
    "fixtures plus a keystore-aware Loader.load_pdf signature; "
    "pypdfbox's Loader.load_pdf accepts only the password parameter."
)
def test_read_pubkey_encrypted_aes256() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-5249: requires AES128ExposedMeta.pdf + PDFBOX-5249.p12 "
    "fixtures plus a keystore-aware Loader.load_pdf signature."
)
def test_read_pubkey_encrypted_aes128_with_metadata_exposed() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-5249: requires AES256ExposedMeta.pdf + PDFBOX-5249.p12 "
    "fixtures plus a keystore-aware Loader.load_pdf signature."
)
def test_read_pubkey_encrypted_aes256_with_metadata_exposed() -> None: ...


# --------------------------------------------------------------------- #
# Translated structural assertions — these do NOT depend on the .pfx /
# .der fixtures and can run today. The first asserts the parameterised
# key-length list upstream's ``keyLengths()`` factory exposes; the
# second is the JCE policy-files gate (Python has no equivalent — the
# ``cryptography`` library does not impose Java's import-restriction
# policy).
# --------------------------------------------------------------------- #


def test_supported_key_lengths_match_upstream_factory() -> None:
    """Upstream's ``keyLengths()`` returns ``Arrays.asList(40, 128, 256)``;
    the pypdfbox PublicKeySecurityHandler accepts the same set."""
    from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
        PublicKeyProtectionPolicy,
    )

    policy = PublicKeyProtectionPolicy()
    for kl in (40, 128, 256):
        policy.set_encryption_key_length(kl)
        assert policy.get_encryption_key_length() == kl


def test_jce_unlimited_strength_policy_gate_skipped() -> None:
    """Upstream's ``@BeforeAll init()`` calls
    ``Cipher.getMaxAllowedKeyLength("AES") != Integer.MAX_VALUE`` and
    fails the suite when JCE jurisdiction policy files are missing. The
    Python ``cryptography`` library has no equivalent — pyca/cryptography
    is built without the JCE jurisdiction restrictions. This stub
    documents the upstream gate's absence; nothing to assert."""
    # Nothing to assert — the upstream gate is a JVM-only concern.
