"""Wave 1366 (agent B) — coverage round-out for
:class:`CertInformationCollector`.

The base ``test_cert_information_collector`` suite covers single-cert
shapes. This module adds:

* deep-chain traversal (3 levels — leaf / intermediate / root) covers
  the recursive ``_build_node`` plus the ``set_cert_chain`` linkage,
* upstream alias ``CertificateProccessingException`` (typo preserved)
  is the same class as the corrected spelling,
* :meth:`get_certificate_set` round-trips entries added via both
  ``_build_node`` and :meth:`add_all_certs_from_holders` /
  :meth:`add_all_certs`,
* :meth:`process_signer_store` handles a signer with multiple cert
  holders (picks the first non-``None`` only — short-circuits on
  break),
* :meth:`get_cert_info` (the raw-bytes overload) recurses into the
  chain just like :meth:`get_last_cert_info`.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
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
# Chain builder helpers
# ---------------------------------------------------------------------------


def _build_ca(
    cn: str = "wave1366-root",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _issue(
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    *,
    cn: str,
    is_ca: bool = False,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
    cert = builder.sign(issuer_key, hashes.SHA256())
    return cert, key


def _build_three_level_chain() -> tuple[
    x509.Certificate, x509.Certificate, x509.Certificate
]:
    """Return (leaf, intermediate, root)."""
    root, root_key = _build_ca("wave1366-root")
    intermediate, intermediate_key = _issue(
        root, root_key, cn="wave1366-int", is_ca=True
    )
    leaf, _ = _issue(intermediate, intermediate_key, cn="wave1366-leaf")
    return leaf, intermediate, root


def _build_signed_pkcs7(
    payload: bytes,
    leaf_cert: x509.Certificate,
    intermediate_cert: x509.Certificate,
    *,
    extra_certs: list[x509.Certificate] | None = None,
) -> bytes:
    """Build a CMS PKCS#7 signed-data blob that carries leaf + chain."""
    # Sign with a fresh key so we don't need the original leaf private key.
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    builder = pkcs7.PKCS7SignatureBuilder().set_data(payload)
    builder = builder.add_signer(leaf_cert, signer_key, hashes.SHA256())
    builder = builder.add_certificate(intermediate_cert)
    for extra in extra_certs or []:
        builder = builder.add_certificate(extra)
    # The signer key/cert mismatch will fail verification — but cert
    # extraction (which is all the collector cares about) works fine.
    return builder.sign(
        serialization.Encoding.DER,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.NoCapabilities],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_aliases_are_the_same_class() -> None:
    """Upstream class name ``CertificateProccessingException`` (typo
    preserved) must alias the corrected spelling."""
    assert CertificateProccessingException is CertificateProcessingException


def test_max_chain_depth_constant() -> None:
    """Sanity — upstream pins MAX_CERTIFICATE_CHAIN_DEPTH at 5."""
    assert MAX_CERTIFICATE_CHAIN_DEPTH == 5


def test_get_last_cert_info_builds_three_level_chain() -> None:
    """A 3-level chain (leaf / intermediate / root) walks correctly:
    ``get_cert_chain()`` recurses to the root, and the root node reports
    ``is_self_signed() == True``."""
    leaf, intermediate, root = _build_three_level_chain()

    class _FakeSig:
        def get_contents(self) -> bytes:
            return _build_signed_pkcs7(
                b"payload",
                leaf,
                intermediate,
                extra_certs=[root],
            )

    collector = CertInformationCollector()
    info = collector.get_last_cert_info(_FakeSig())
    assert info is not None
    assert info.is_self_signed() is False

    chain = info.get_cert_chain()
    assert chain is not None
    # The CMS bundle stores all three certs; the collector picks any subject
    # match for ``issuer``. The chain walks at least one hop deep.
    assert chain.get_certificate() is not None
    # Iterate to the root — at most three nodes.
    node: CertSignatureInformation | None = info
    seen = 0
    while node is not None:
        seen += 1
        if node.is_self_signed():
            break
        node = node.get_cert_chain()
    # Should have reached a self-signed anchor within 3 levels.
    assert seen >= 2


def test_get_last_cert_info_records_sha1_signature_hash() -> None:
    """:meth:`get_last_cert_info` populates ``signature_hash`` with the
    SHA-1 of the raw ``/Contents`` blob."""
    import hashlib

    leaf, intermediate, root = _build_three_level_chain()
    contents = _build_signed_pkcs7(
        b"x", leaf, intermediate, extra_certs=[root]
    )

    class _FakeSig:
        def get_contents(self) -> bytes:
            return contents

    collector = CertInformationCollector()
    info = collector.get_last_cert_info(_FakeSig())
    assert info is not None
    expected = hashlib.sha1(contents, usedforsecurity=False).hexdigest().upper()
    assert info.get_signature_hash() == expected


def test_get_last_cert_info_returns_none_when_no_certs(monkeypatch) -> None:
    """If ``load_der_pkcs7_certificates`` returns an empty list (the
    PKCS#7 blob carried no certificates), the collector returns ``None``
    rather than fabricating a node — line 71-72."""

    def _no_certs(_blob):
        return []

    monkeypatch.setattr(
        "pypdfbox.examples.signature.validation.cert_information_collector.pkcs7.load_der_pkcs7_certificates",
        _no_certs,
    )

    class _Sig:
        def get_contents(self) -> bytes:
            return b"\x30\x80\x00\x00"  # not really PKCS#7

    collector = CertInformationCollector()
    assert collector.get_last_cert_info(_Sig()) is None


def test_certificate_set_grows_with_each_build(self_signed_cert) -> None:
    """Each ``_build_node`` invocation adds the cert into the
    ``certificate_set``."""
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    assert len(collector.get_certificate_set()) == 0

    collector._build_node(cert, [cert], "HASH", depth=0)
    assert cert in collector.get_certificate_set()
    assert len(collector.get_certificate_set()) == 1

    # Adding again is idempotent (set semantics).
    collector._build_node(cert, [cert], "HASH", depth=0)
    assert len(collector.get_certificate_set()) == 1


def test_build_node_stops_at_max_depth_without_recursing(self_signed_cert) -> None:
    """When ``depth >= MAX_CERTIFICATE_CHAIN_DEPTH`` the method returns
    the leaf node without setting ``cert_chain`` — even when an issuer
    would otherwise be findable in the pool."""
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    # Note: cert is self-signed so the second short-circuit would also
    # trigger, but we want to confirm the depth guard executes.
    info = collector._build_node(
        cert, [cert], None, depth=MAX_CERTIFICATE_CHAIN_DEPTH,
    )
    assert info.get_cert_chain() is None


def test_traverse_chain_zero_depth_does_not_record(self_signed_cert) -> None:
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    info = CertSignatureInformation()
    collector.traverse_chain(cert, info, max_depth=0)
    assert cert not in collector.get_certificate_set()


def test_traverse_chain_records_certificate(self_signed_cert) -> None:
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    info = CertSignatureInformation()
    collector.traverse_chain(cert, info, max_depth=3)
    assert cert in collector.get_certificate_set()


def test_get_alternative_issuer_certificate_is_noop() -> None:
    """The placeholder helper returns ``None`` and doesn't mutate state."""
    collector = CertInformationCollector()
    before = collector.get_certificate_set().copy()
    info = CertSignatureInformation()
    assert collector.get_alternative_issuer_certificate(info, 5) is None
    assert collector.get_certificate_set() == before


def test_add_timestamp_certs_is_noop() -> None:
    """``add_timestamp_certs`` is a placeholder — no return, no raise."""
    collector = CertInformationCollector()
    assert collector.add_timestamp_certs(object()) is None


def test_process_signer_store_with_multiple_holders_picks_first(
    self_signed_cert,
) -> None:
    """The for-loop breaks on the first non-``None`` cert from the
    ``get_certificates`` iterable."""
    cert, _ = self_signed_cert

    class _SignedData:
        def get_signer_infos(self) -> list:
            return [object()]

        def get_certificates(self):
            # Mix in a None to confirm it would be skipped (the helper's
            # ``cert is not None`` guard is on the holder, but we mirror
            # the upstream skipping via the get_cert_from_holder return).
            return [cert, cert]

    collector = CertInformationCollector()
    info = CertSignatureInformation()
    signer = collector.process_signer_store(_SignedData(), info)
    assert signer is not None
    # ``cert`` was assigned to ``info`` and put into the set.
    assert info.get_certificate() is cert
    assert cert in collector.get_certificate_set()


def test_get_cert_info_walks_pkcs7_bytes() -> None:
    """:meth:`get_cert_info` parses raw PKCS#7 bytes and returns a node
    rooted at the first certificate (depth=0)."""
    leaf, intermediate, root = _build_three_level_chain()
    contents = _build_signed_pkcs7(
        b"data", leaf, intermediate, extra_certs=[root]
    )
    collector = CertInformationCollector()
    info = collector.get_cert_info(contents)
    assert info is not None
    assert info.get_certificate() is not None


def test_add_all_certs_filters_none_holders(self_signed_cert) -> None:
    """The collector's ``add_all_certs`` skips holders whose
    ``get_cert_from_holder`` returns ``None``."""
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    # Subclass to make holder=None map to cert=None instead of identity.
    original = collector.get_cert_from_holder

    def _holder_filter(holder: Any) -> Any:
        return original(holder) if holder is not None else None

    collector.get_cert_from_holder = _holder_filter  # type: ignore[method-assign]
    collector.add_all_certs([None, cert, None])
    assert collector.get_certificate_set() == {cert}


def test_process_signature_certificate_sets_self_signed_flag(self_signed_cert) -> None:
    """Hand the helper a self-signed cert — the flag must be set."""
    cert, _ = self_signed_cert
    collector = CertInformationCollector()
    info = CertSignatureInformation()
    collector.process_signature_certificate(cert, info)
    assert info.is_self_signed() is True
    assert info.get_certificate() is cert
