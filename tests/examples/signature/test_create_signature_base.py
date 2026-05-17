"""Tests for ``CreateSignatureBase``."""

from __future__ import annotations

import datetime as _dt
from io import BytesIO

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from pypdfbox.examples.signature.create_signature_base import CreateSignatureBase


def _build_pkcs12(
    *,
    not_before: _dt.datetime | None = None,
    not_after: _dt.datetime | None = None,
    extra_chain: int = 0,
    password: bytes | None = b"hunter2",
) -> bytes:
    now = _dt.datetime.now(_dt.UTC)
    not_before = not_before or (now - _dt.timedelta(days=1))
    not_after = not_after or (now + _dt.timedelta(days=365))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CODE_SIGNING]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cas: list[x509.Certificate] = []
    for i in range(extra_chain):
        extra_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        extra_subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, f"pypdfbox-extra-{i}")]
        )
        cas.append(
            x509.CertificateBuilder()
            .subject_name(extra_subject)
            .issuer_name(extra_subject)
            .public_key(extra_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _dt.timedelta(days=1))
            .not_valid_after(now + _dt.timedelta(days=365))
            .sign(extra_key, hashes.SHA256())
        )
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"pypdfbox-test",
        key=key,
        cert=cert,
        cas=cas or None,
        encryption_algorithm=encryption,
    )


def test_loads_pkcs12_keystore(pkcs12_bytes, tsa_password):
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    chain = signer.get_certificate_chain()
    assert len(chain) >= 1


def test_external_signing_flag_round_trips(pkcs12_bytes, tsa_password):
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    assert signer.is_external_signing() is False
    signer.set_external_signing(True)
    assert signer.is_external_signing() is True


def test_sign_returns_detached_pkcs7(pkcs12_bytes, tsa_password):
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    payload = b"document content"
    blob = signer.sign(BytesIO(payload))
    assert isinstance(blob, bytes) and len(blob) > 0
    # PKCS#7 contents should at least carry the signing certificate.
    certs = pkcs7.load_der_pkcs7_certificates(blob)
    assert len(certs) >= 1


def test_constructor_raises_with_bad_password(pkcs12_bytes):
    # cryptography raises ValueError when the PKCS#12 password is wrong.
    with pytest.raises(ValueError):
        CreateSignatureBase(pkcs12_bytes, b"wrong-pin")


def test_constructor_accepts_str_pin():
    """Cover the ``isinstance(pin, str)`` branch (line 37)."""
    blob = _build_pkcs12(password=b"hunter2")
    signer = CreateSignatureBase(blob, "hunter2")
    assert signer.get_certificate_chain()


def test_constructor_accepts_none_pin():
    """Cover the ``pin is None`` branch (line 35)."""
    blob = _build_pkcs12(password=None)
    signer = CreateSignatureBase(blob, None)
    assert signer.get_certificate_chain()


def test_constructor_rejects_expired_certificate():
    """Cover the validity-window guard (line 54)."""
    expired_before = _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=30)
    expired_after = _dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1)
    blob = _build_pkcs12(not_before=expired_before, not_after=expired_after)
    with pytest.raises(OSError, match="not currently valid"):
        CreateSignatureBase(blob, "hunter2")


def test_constructor_rejects_future_dated_certificate():
    """Same guard, but the not-before-future branch (line 54)."""
    future_before = _dt.datetime.now(_dt.UTC) + _dt.timedelta(days=30)
    future_after = _dt.datetime.now(_dt.UTC) + _dt.timedelta(days=60)
    blob = _build_pkcs12(not_before=future_before, not_after=future_after)
    with pytest.raises(OSError, match="not currently valid"):
        CreateSignatureBase(blob, "hunter2")


def test_set_private_key_replaces_key(pkcs12_bytes, tsa_password):
    """Cover ``set_private_key`` (line 65)."""
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer.set_private_key(new_key)
    assert signer._private_key is new_key


def test_set_certificate_chain_replaces_chain(pkcs12_bytes, tsa_password):
    """Cover ``set_certificate_chain`` (line 68)."""
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    original_chain = signer.get_certificate_chain()
    signer.set_certificate_chain(original_chain)
    second = signer.get_certificate_chain()
    assert len(second) == len(original_chain)
    # New list, not the same object.
    assert second is not original_chain


def test_set_tsa_url_round_trips(pkcs12_bytes, tsa_password):
    """Cover ``set_tsa_url`` (line 74) and the tsa branch in ``sign`` (103-104)."""
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    signer.set_tsa_url("http://tsa.test.invalid")
    assert signer._tsa_url == "http://tsa.test.invalid"


def test_sign_with_tsa_url_appends_token(pkcs12_bytes, tsa_password, monkeypatch):
    """Cover lines 103-104: when ``_tsa_url`` is set, ``ValidationTimeStamp``
    is invoked. Patch the TSA round-trip so no real HTTP happens."""
    import pypdfbox.examples.signature.create_signature_base as mod

    captured: dict[str, bytes] = {}

    class _StubValidation:
        def __init__(self, url: str) -> None:
            captured["url"] = url

        def add_signed_time_stamp(self, signed_data: bytes) -> bytes:
            captured["signed_data"] = signed_data
            return signed_data + b"|TSA_TOKEN"

    monkeypatch.setattr(mod, "ValidationTimeStamp", _StubValidation)
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    signer.set_tsa_url("http://tsa.test.invalid")
    blob = signer.sign(BytesIO(b"payload"))
    assert blob.endswith(b"|TSA_TOKEN")
    assert captured["url"] == "http://tsa.test.invalid"


def test_sign_with_multi_cert_chain_emits_add_certificate(tsa_password):
    """Cover line 97 (``builder.add_certificate(extra)`` loop)."""
    blob = _build_pkcs12(extra_chain=2, password=tsa_password)
    signer = CreateSignatureBase(blob, tsa_password)
    chain = signer.get_certificate_chain()
    assert len(chain) >= 3
    result = signer.sign(BytesIO(b"payload"))
    assert isinstance(result, bytes) and len(result) > 0


def test_sign_stream_wraps_payload(pkcs12_bytes, tsa_password):
    """Cover ``sign_stream`` (line 109)."""
    signer = CreateSignatureBase(pkcs12_bytes, tsa_password)
    blob = signer.sign_stream(b"hello")
    assert isinstance(blob, bytes) and len(blob) > 0


def test_constructor_raises_when_certificate_missing(monkeypatch, pkcs12_bytes):
    """Cover the cert/private_key ``None`` guard (line 45)."""
    import pypdfbox.examples.signature.create_signature_base as mod

    def _no_cert(data, password):  # noqa: ARG001
        return (None, None, [])

    monkeypatch.setattr(mod.pkcs12, "load_key_and_certificates", _no_cert)
    with pytest.raises(OSError, match="Could not find certificate"):
        CreateSignatureBase(pkcs12_bytes, b"hunter2")
