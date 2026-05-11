"""Shared fixtures for the signature example tests.

These fixtures build a self-signed RSA certificate + matching PKCS#12
keystore entirely in-memory so the suite never depends on a real CA.
"""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    ExtendedKeyUsageOID,
    NameOID,
)


def _build_self_signed(
    *,
    common_name: str = "pypdfbox-test",
    add_ocsp: bool = False,
    add_crl: bool = False,
    extended_key_usage: list = None,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)],
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
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
    )
    eku_list = extended_key_usage or [ExtendedKeyUsageOID.CODE_SIGNING]
    builder = builder.add_extension(
        x509.ExtendedKeyUsage(eku_list),
        critical=False,
    )
    aia_descriptions = []
    if add_ocsp:
        aia_descriptions.append(
            x509.AccessDescription(
                access_method=AuthorityInformationAccessOID.OCSP,
                access_location=x509.UniformResourceIdentifier(
                    "http://ocsp.test.invalid/check"
                ),
            )
        )
        aia_descriptions.append(
            x509.AccessDescription(
                access_method=AuthorityInformationAccessOID.CA_ISSUERS,
                access_location=x509.UniformResourceIdentifier(
                    "http://ca.test.invalid/issuer.crt"
                ),
            )
        )
    if aia_descriptions:
        builder = builder.add_extension(
            x509.AuthorityInformationAccess(aia_descriptions),
            critical=False,
        )
    if add_crl:
        builder = builder.add_extension(
            x509.CRLDistributionPoints(
                [
                    x509.DistributionPoint(
                        full_name=[
                            x509.UniformResourceIdentifier(
                                "http://crl.test.invalid/list.crl"
                            )
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ]
            ),
            critical=False,
        )
    cert = builder.sign(key, hashes.SHA256())
    return cert, key


@pytest.fixture
def self_signed_cert() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    return _build_self_signed()


@pytest.fixture
def self_signed_with_revocation() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    return _build_self_signed(add_ocsp=True, add_crl=True)


@pytest.fixture
def pkcs12_bytes(self_signed_cert) -> bytes:
    cert, key = self_signed_cert
    return pkcs12.serialize_key_and_certificates(
        name=b"pypdfbox-test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"hunter2"),
    )


@pytest.fixture
def tsa_password() -> bytes:
    return b"hunter2"
