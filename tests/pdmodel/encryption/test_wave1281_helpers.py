"""Wave 1281 — parity ports for encryption helpers.

Covers ``MessageDigests``, ``RC4Cipher``, ``SaslPrep``,
``SecurityHandlerFactory``, ``SecurityProvider``.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.encryption.message_digests import MessageDigests
from pypdfbox.pdmodel.encryption.rc4_cipher import RC4Cipher
from pypdfbox.pdmodel.encryption.sasl_prep import SaslPrep
from pypdfbox.pdmodel.encryption.security_handler_factory import (
    SecurityHandlerFactory,
)
from pypdfbox.pdmodel.encryption.security_provider import SecurityProvider
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)

# --- MessageDigests --------------------------------------------------------


class TestMessageDigests:
    def test_md5_digest_roundtrip(self) -> None:
        digest = MessageDigests.get_md5()
        digest.update(b"hello")
        out = digest.finalize()
        assert len(out) == 16

    def test_sha1_digest_roundtrip(self) -> None:
        digest = MessageDigests.get_sha1()
        digest.update(b"hello")
        out = digest.finalize()
        assert len(out) == 20

    def test_sha256_digest_roundtrip(self) -> None:
        digest = MessageDigests.get_sha256()
        digest.update(b"hello")
        out = digest.finalize()
        assert len(out) == 32

    def test_constructor_raises(self) -> None:
        with pytest.raises(TypeError):
            MessageDigests()


# --- RC4Cipher -------------------------------------------------------------


class TestRC4Cipher:
    def test_set_key_then_write_bytes(self) -> None:
        cipher = RC4Cipher()
        cipher.set_key(b"Secret")
        out = io.BytesIO()
        cipher.write(b"Attack at dawn", out)
        encrypted = out.getvalue()
        assert encrypted != b"Attack at dawn"
        assert len(encrypted) == len(b"Attack at dawn")

    def test_set_key_rejects_too_short(self) -> None:
        cipher = RC4Cipher()
        with pytest.raises(ValueError):
            cipher.set_key(b"")

    def test_set_key_rejects_too_long(self) -> None:
        cipher = RC4Cipher()
        with pytest.raises(ValueError):
            cipher.set_key(b"x" * 33)

    def test_roundtrip_decrypt_matches_plaintext(self) -> None:
        cipher = RC4Cipher()
        cipher.set_key(b"Secret")
        encrypted = io.BytesIO()
        cipher.write(b"Attack at dawn", encrypted)
        # RC4 is symmetric — re-running with the same key decrypts.
        decoder = RC4Cipher()
        decoder.set_key(b"Secret")
        decrypted = io.BytesIO()
        decoder.write(encrypted.getvalue(), decrypted)
        assert decrypted.getvalue() == b"Attack at dawn"

    def test_write_inputstream_form(self) -> None:
        cipher = RC4Cipher()
        cipher.set_key(b"Secret")
        out = io.BytesIO()
        cipher.write(io.BytesIO(b"data" * 300), out)
        assert len(out.getvalue()) == 4 * 300


# --- SaslPrep --------------------------------------------------------------


class TestSaslPrep:
    def test_basic_ascii_unchanged(self) -> None:
        assert SaslPrep.sasl_prep_stored("password") == "password"

    def test_non_ascii_space_mapped_to_ascii_space(self) -> None:
        # U+00A0 (no-break space) → ASCII space.
        assert SaslPrep.sasl_prep_stored("a b") == "a b"

    def test_soft_hyphen_mapped_to_nothing(self) -> None:
        # U+00AD (soft hyphen) is dropped.
        assert SaslPrep.sasl_prep_stored("a­b") == "ab"

    def test_prohibited_codepoint_rejected(self) -> None:
        with pytest.raises(ValueError):
            # NULL is an ASCII control character.
            SaslPrep.sasl_prep_stored("a\x00b")

    def test_unassigned_rejected_in_stored(self) -> None:
        # U+2073 (subscript "3" pre-Unicode 4) is now assigned; pick a
        # codepoint that is currently unassigned in major Python builds.
        # If your Unicode tables are newer this may need updating —
        # we deliberately use a codepoint far above the BMP.
        with pytest.raises(ValueError):
            SaslPrep.sasl_prep_stored("\U000fffff")

    def test_query_accepts_unassigned(self) -> None:
        # Query allowance is the only difference vs stored.
        assert SaslPrep.sasl_prep_query("\U000e0080")[0] == "\U000e0080"

    def test_constructor_raises(self) -> None:
        with pytest.raises(TypeError):
            SaslPrep()


# --- SecurityHandlerFactory ------------------------------------------------


class TestSecurityHandlerFactory:
    def test_singleton_present(self) -> None:
        assert SecurityHandlerFactory.INSTANCE is not None
        assert isinstance(
            SecurityHandlerFactory.INSTANCE, SecurityHandlerFactory
        )

    def test_filter_lookup_returns_standard(self) -> None:
        handler = SecurityHandlerFactory.INSTANCE.new_security_handler_for_filter(
            StandardSecurityHandler.FILTER
        )
        assert isinstance(handler, StandardSecurityHandler)

    def test_filter_lookup_unknown_returns_none(self) -> None:
        assert (
            SecurityHandlerFactory.INSTANCE.new_security_handler_for_filter(
                "MissingFilter"
            )
            is None
        )

    def test_policy_lookup_returns_standard(self) -> None:
        policy = StandardProtectionPolicy()
        handler = (
            SecurityHandlerFactory.INSTANCE.new_security_handler_for_policy(
                policy
            )
        )
        assert isinstance(handler, StandardSecurityHandler)

    def test_register_duplicate_raises(self) -> None:
        factory = SecurityHandlerFactory()
        with pytest.raises(RuntimeError):
            factory.register_handler(
                StandardSecurityHandler.FILTER,
                StandardSecurityHandler,
                StandardProtectionPolicy,
            )


# --- SecurityProvider ------------------------------------------------------


class TestSecurityProvider:
    def test_get_provider_lazy(self) -> None:
        SecurityProvider.set_provider(None)
        provider = SecurityProvider.get_provider()
        assert provider is not None

    def test_set_then_get(self) -> None:
        sentinel = object()
        SecurityProvider.set_provider(sentinel)
        try:
            assert SecurityProvider.get_provider() is sentinel
        finally:
            SecurityProvider.set_provider(None)

    def test_constructor_raises(self) -> None:
        with pytest.raises(TypeError):
            SecurityProvider()
