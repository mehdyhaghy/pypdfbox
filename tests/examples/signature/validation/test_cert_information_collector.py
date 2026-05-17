"""Tests for ``CertInformationCollector``."""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.validation.cert_information_collector import (
    MAX_CERTIFICATE_CHAIN_DEPTH,
    CertificateProccessingException,
    CertificateProcessingException,
    CertInformationCollector,
)
from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_cert(
    subject_cn: str,
    issuer_cn: str,
    signing_key: rsa.RSAPrivateKey,
    subject_key: rsa.RSAPrivateKey | None = None,
) -> x509.Certificate:
    subject_key = subject_key or signing_key
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_cn)])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(subject_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
    )
    return builder.sign(signing_key, hashes.SHA256())


def _build_chain(depth: int) -> tuple[list[x509.Certificate], list[rsa.RSAPrivateKey]]:
    """Build a chain of ``depth`` certs: leaf -> int1 -> ... -> root."""
    keys = [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(depth)]
    certs: list[x509.Certificate] = []
    # root self-signed at index depth-1
    root_name = f"root-{depth - 1}"
    root = _build_cert(root_name, root_name, keys[-1])
    # build from leaf to root
    chain_names = [f"node-{i}" for i in range(depth - 1)]
    issuers = [*chain_names[1:], root_name]
    for i, (cn, issuer_cn) in enumerate(zip(chain_names, issuers, strict=False)):
        cert = _build_cert(cn, issuer_cn, keys[i + 1], subject_key=keys[i])
        certs.append(cert)
    certs.append(root)
    return certs, keys


def _make_pkcs7(certs: list[x509.Certificate], signing_key: rsa.RSAPrivateKey) -> bytes:
    """Build a detached PKCS#7 SignedData containing ``certs``."""
    from cryptography.hazmat.primitives.serialization import Encoding

    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(b"payload")
        .add_signer(certs[0], signing_key, hashes.SHA256())
    )
    for extra in certs[1:]:
        builder = builder.add_certificate(extra)
    return builder.sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])


class _FakeSignature:
    def __init__(self, contents: bytes | None):
        self._contents = contents

    def get_contents(self):
        return self._contents


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


def test_aliases_match():
    assert CertificateProccessingException is CertificateProcessingException


def test_construction():
    collector = CertInformationCollector()
    assert collector.get_certificate_set() == set()


def test_add_all_certs_from_holders(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    collector.add_all_certs_from_holders([cert])
    assert cert in collector.get_certificate_set()


def test_get_last_cert_info_returns_none_when_no_contents():
    collector = CertInformationCollector()
    assert collector.get_last_cert_info(_FakeSignature(None)) is None


def test_get_last_cert_info_raises_on_bad_contents():
    collector = CertInformationCollector()
    with pytest.raises(CertificateProcessingException):
        collector.get_last_cert_info(_FakeSignature(b"not-pkcs7"))


def test_cert_signature_information_default_values():
    info = CertSignatureInformation()
    assert info.get_certificate() is None


# ---------------------------------------------------------------------------
# Coverage uplift — wave 1333
# ---------------------------------------------------------------------------


def test_max_certificate_chain_depth_constant():
    assert MAX_CERTIFICATE_CHAIN_DEPTH == 5


def test_get_last_cert_info_self_signed(self_signed_cert):
    cert, key = self_signed_cert
    blob = _make_pkcs7([cert], key)
    collector = CertInformationCollector()
    info = collector.get_last_cert_info(_FakeSignature(blob))
    assert info is not None
    assert info.get_certificate() is not None
    # the certificate is self-signed so no chain
    assert info.get_cert_chain() is None
    assert info.is_self_signed() is True
    # signature hash is present (SHA-1 of the full PKCS#7 blob)
    assert info.get_signature_hash() is not None
    # collector now holds the cert in its working set
    assert cert in collector.get_certificate_set()


def test_get_last_cert_info_with_chain():
    """A non-self-signed leaf links to its root via _build_node directly."""
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root = _build_cert("root", "root", root_key)
    leaf = _build_cert("leaf", "root", root_key, subject_key=leaf_key)
    # call _build_node directly with leaf at index 0 to avoid PKCS#7 reordering
    collector = CertInformationCollector()
    info = collector._build_node(leaf, [leaf, root], "HASH", depth=0)
    assert info.is_self_signed() is False
    chain = info.get_cert_chain()
    assert chain is not None
    assert chain.is_self_signed() is True
    assert leaf in collector.get_certificate_set()
    assert root in collector.get_certificate_set()


def test_get_last_cert_info_returns_none_when_no_certs(monkeypatch):
    """A PKCS#7 that parses but yields no certs returns None."""
    collector = CertInformationCollector()
    monkeypatch.setattr(
        "pypdfbox.examples.signature.validation.cert_information_collector"
        ".pkcs7.load_der_pkcs7_certificates",
        lambda _payload: [],
    )
    assert collector.get_last_cert_info(_FakeSignature(b"anything")) is None


def test_get_cert_info_self_signed(self_signed_cert):
    cert, key = self_signed_cert
    blob = _make_pkcs7([cert], key)
    collector = CertInformationCollector()
    info = collector.get_cert_info(blob)
    assert info is not None
    assert info.get_certificate() is not None
    # signature hash is not set in get_cert_info
    assert info.get_signature_hash() is None


def test_get_cert_info_returns_none_on_bad_bytes():
    collector = CertInformationCollector()
    assert collector.get_cert_info(b"not-pkcs7") is None


def test_get_cert_info_returns_none_when_pool_empty(monkeypatch):
    collector = CertInformationCollector()
    monkeypatch.setattr(
        "pypdfbox.examples.signature.validation.cert_information_collector"
        ".pkcs7.load_der_pkcs7_certificates",
        lambda _payload: [],
    )
    assert collector.get_cert_info(b"anything") is None


def test_find_issuer_skips_self_and_finds_match():
    collector = CertInformationCollector()
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root = _build_cert("rootA", "rootA", root_key)
    leaf = _build_cert("leafA", "rootA", root_key, subject_key=leaf_key)
    issuer = collector._find_issuer(leaf, [leaf, root])
    assert issuer is root


def test_find_issuer_returns_none_when_missing():
    collector = CertInformationCollector()
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = _build_cert("only", "missing-issuer", root_key, subject_key=leaf_key)
    assert collector._find_issuer(leaf, [leaf]) is None


def test_build_node_respects_max_depth():
    """Walking a chain deeper than MAX_CERTIFICATE_CHAIN_DEPTH stops gracefully."""
    # depth = MAX + 2 so the recursion would naturally exceed the limit
    certs, _keys = _build_chain(MAX_CERTIFICATE_CHAIN_DEPTH + 2)
    collector = CertInformationCollector()
    info = collector._build_node(certs[0], certs, "HASH", depth=0)
    # walk the chain and confirm it doesn't extend past max
    walked = 1
    node = info
    while node.get_cert_chain() is not None:
        node = node.get_cert_chain()
        walked += 1
    assert walked <= MAX_CERTIFICATE_CHAIN_DEPTH + 1


def test_build_node_stops_when_at_max_depth(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    info = collector._build_node(
        cert, [cert], None, depth=MAX_CERTIFICATE_CHAIN_DEPTH,
    )
    # at-max-depth: early return before any descent
    assert info.get_cert_chain() is None


def test_traverse_chain_zero_depth_is_noop(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    collector.traverse_chain(cert, CertSignatureInformation(), max_depth=0)
    assert cert not in collector.get_certificate_set()


def test_traverse_chain_positive_depth_adds_to_set(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    collector.traverse_chain(cert, CertSignatureInformation(), max_depth=3)
    assert cert in collector.get_certificate_set()


def test_add_timestamp_certs_noop():
    collector = CertInformationCollector()
    # stub method should not raise even when handed nothing
    assert collector.add_timestamp_certs(None) is None


def test_process_signer_store_none_returns_none():
    collector = CertInformationCollector()
    assert collector.process_signer_store(None, CertSignatureInformation()) is None


def test_process_signer_store_no_signer_infos_attr():
    """signed_data without get_signer_infos returns None."""

    class _SignedData:
        pass

    collector = CertInformationCollector()
    assert collector.process_signer_store(_SignedData(), CertSignatureInformation()) is None


def test_process_signer_store_empty_signers():
    """signed_data with empty signer set returns None."""

    class _SignedData:
        def get_signer_infos(self):
            return []

    collector = CertInformationCollector()
    assert collector.process_signer_store(_SignedData(), CertSignatureInformation()) is None


def test_process_signer_store_returns_first_signer(self_signed_cert):
    cert, _ = self_signed_cert
    sentinel_signer = object()

    class _SignedData:
        def get_signer_infos(self):
            return [sentinel_signer]

        def get_certificates(self):
            return [cert]

    collector = CertInformationCollector()
    info = CertSignatureInformation()
    result = collector.process_signer_store(_SignedData(), info)
    assert result is sentinel_signer
    assert info.get_certificate() is cert
    assert cert in collector.get_certificate_set()


def test_process_signer_store_without_get_certificates(self_signed_cert):
    """Signed data missing get_certificates still returns the signer."""
    sentinel_signer = object()

    class _SignedData:
        def get_signer_infos(self):
            return [sentinel_signer]

    collector = CertInformationCollector()
    info = CertSignatureInformation()
    result = collector.process_signer_store(_SignedData(), info)
    assert result is sentinel_signer
    assert info.get_certificate() is None


def test_process_signer_store_skips_none_holders():
    """get_cert_from_holder returning None should not crash."""
    sentinel_signer = object()

    class _SignedData:
        def get_signer_infos(self):
            return [sentinel_signer]

        def get_certificates(self):
            return [None, None]

    collector = CertInformationCollector()
    info = CertSignatureInformation()
    result = collector.process_signer_store(_SignedData(), info)
    assert result is sentinel_signer
    assert info.get_certificate() is None


def test_get_alternative_issuer_certificate_noop():
    collector = CertInformationCollector()
    info = CertSignatureInformation()
    assert collector.get_alternative_issuer_certificate(info, max_depth=3) is None


def test_get_cert_from_holder_returns_input(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    assert collector.get_cert_from_holder(cert) is cert


def test_get_cert_from_holder_returns_none_on_none():
    collector = CertInformationCollector()
    assert collector.get_cert_from_holder(None) is None


def test_add_all_certs(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    collector.add_all_certs([cert])
    assert cert in collector.get_certificate_set()


def test_add_all_certs_skips_none(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    collector.add_all_certs([cert, None, cert])
    # set still has exactly the cert
    assert collector.get_certificate_set() == {cert}


def test_process_signature_certificate(self_signed_cert):
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    info = CertSignatureInformation()
    collector.process_signature_certificate(cert, info)
    assert info.get_certificate() is cert
    assert info.is_self_signed() is True


def test_process_signature_certificate_non_self_signed():
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = _build_cert("L", "R", root_key, subject_key=leaf_key)
    collector = CertInformationCollector()
    info = CertSignatureInformation()
    collector.process_signature_certificate(leaf, info)
    assert info.get_certificate() is leaf
    assert info.is_self_signed() is False
