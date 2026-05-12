"""Wave 1289 — wire ``PublicKeyProtectionPolicy`` through ``PDDocument.protect``
and the ``COSWriter`` save path.

Up to wave 1288 both surfaces rejected non-standard policies with
``NotImplementedError``; this wave routes public-key policies to
``PublicKeySecurityHandler.prepare_document`` so a full encrypt path works.
"""

from __future__ import annotations

import datetime
import io

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.pdfwriter.cos_writer import COSWriter
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def _build_self_signed_rsa() -> tuple[object, object]:
    """Return ``(cert, private_key)`` — a fresh self-signed 2048-bit RSA pair.

    Used so the dispatch tests can build a real ``PublicKeyRecipient`` without
    pulling network-fetched fixtures.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-wave1289-recipient")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(private_key, hashes.SHA256())
    )
    return cert, private_key


def test_pd_document_protect_accepts_public_key_policy() -> None:
    """``protect`` now accepts ``PublicKeyProtectionPolicy`` and stashes it
    in the same ``_protection_policy`` slot the writer reads from."""
    policy = PublicKeyProtectionPolicy()
    with PDDocument() as pd:
        pd.protect(policy)
        assert pd._protection_policy is policy  # noqa: SLF001


def test_pd_document_protect_rejects_unknown_policy_with_typeerror() -> None:
    """Anything other than the two PDFBox-native policy shapes is a caller
    bug — surfaces as ``TypeError`` rather than the old ``NotImplementedError``."""
    with PDDocument() as pd, pytest.raises(TypeError, match="PublicKeyProtectionPolicy"):
        pd.protect(object())


def test_cos_writer_stage_encryption_routes_public_key_policy() -> None:
    """The save-time dispatch builds a ``PublicKeySecurityHandler`` and
    attaches it back on the PDDocument so subsequent reads see an active
    handler. Mirrors the standard-policy branch already covered upstream."""
    try:
        cert, _key = _build_self_signed_rsa()
    except Exception:  # noqa: BLE001
        pytest.skip("cert generation too heavy in this environment")

    policy = PublicKeyProtectionPolicy()
    policy.add_recipient(
        PublicKeyRecipient(certificate=cert, permissions=AccessPermission())
    )
    policy.set_encryption_key_length(128)

    cos_document = COSDocument()
    captured: dict[str, object] = {}

    class _FakePDDocument:
        _protection_policy = policy
        _security_handler: object | None = None

        def is_all_security_to_be_removed(self) -> bool:
            return False

        def is_encrypted(self) -> bool:
            return False

        def set_encryption_dictionary(self, encryption: object) -> None:
            captured["encryption"] = encryption

    fake = _FakePDDocument()
    with COSWriter(io.BytesIO()) as writer:
        writer._stage_encryption(fake, cos_document)

    assert isinstance(fake._security_handler, PublicKeySecurityHandler)
    assert fake._security_handler.is_aes() is True
    assert "encryption" in captured
    encryption = captured["encryption"]
    assert encryption.get_filter() == "Adobe.PubSec"


def test_cos_writer_stage_encryption_rejects_unknown_policy_with_typeerror() -> None:
    """Unknown policy shapes now surface as ``TypeError`` from the writer
    side, matching the ``PDDocument.protect`` guard."""

    class _FakePDDocument:
        _protection_policy = object()

        def is_all_security_to_be_removed(self) -> bool:
            return False

    with (
        COSWriter(io.BytesIO()) as writer,
        pytest.raises(TypeError, match="PublicKeyProtectionPolicy"),
    ):
        writer._stage_encryption(_FakePDDocument(), COSDocument())
