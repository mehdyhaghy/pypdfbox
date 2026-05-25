"""Wave 1403 branch round-out for ``cert_information_collector``.

Closes ``98->102``: when ``_build_node`` processes a non-self-signed
certificate whose issuer is absent from the candidate pool,
``_find_issuer`` returns None so the ``if issuer is not None and issuer is
not cert`` guard takes its False arc and no child node is attached.
"""

from __future__ import annotations

import datetime as _dt

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.validation.cert_information_collector import (
    CertInformationCollector,
)


def _make_ca_and_leaf() -> tuple[x509.Certificate, x509.Certificate]:
    """An issuer CA and a leaf signed by it (so the leaf is *not*
    self-signed)."""
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    now = _dt.datetime.now(_dt.UTC)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test Leaf")],
    )
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)  # issued by the CA → not self-signed
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=180))
        .sign(ca_key, hashes.SHA256())
    )
    return ca_cert, leaf_cert


def test_build_node_without_issuer_in_pool_skips_chain() -> None:
    _ca, leaf = _make_ca_and_leaf()
    collector = CertInformationCollector()
    # Pool contains only the leaf: the issuer (CA) is absent so
    # _find_issuer returns None → 98->102 (no cert chain attached).
    info = collector._build_node(  # noqa: SLF001 - exercising the helper
        leaf, [leaf], signature_hash=None, depth=0,
    )
    assert info.is_self_signed() is False
    assert info.get_cert_chain() is None
