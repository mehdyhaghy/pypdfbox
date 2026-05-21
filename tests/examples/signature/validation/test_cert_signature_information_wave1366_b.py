"""Wave 1366 (agent B) — coverage round-out for
:class:`CertSignatureInformation`.

The base ``test_cert_signature_information`` suite only covers two
shallow round-trip cases. This file fills out each getter/setter pair,
the chained-node linkage (``cert_chain``, ``tsa_certs``,
``alternative_cert_chain``), and the ``issuer_certificates`` mutable
set accessor.
"""

from __future__ import annotations

from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)


def test_certificate_round_trip(self_signed_cert) -> None:
    cert, _ = self_signed_cert
    info = CertSignatureInformation()
    info.set_certificate(cert)
    assert info.get_certificate() is cert


def test_signature_hash_round_trip() -> None:
    info = CertSignatureInformation()
    info.set_signature_hash("CAFEBABE")
    assert info.get_signature_hash() == "CAFEBABE"


def test_signature_hash_accepts_none() -> None:
    """The setter accepts ``None`` to clear a previously stored value."""
    info = CertSignatureInformation()
    info.set_signature_hash("AABB")
    info.set_signature_hash(None)
    assert info.get_signature_hash() is None


def test_self_signed_flag_round_trip() -> None:
    info = CertSignatureInformation()
    assert info.is_self_signed() is False
    info.set_self_signed(True)
    assert info.is_self_signed() is True


def test_ocsp_url_round_trip() -> None:
    info = CertSignatureInformation()
    assert info.get_ocsp_url() is None
    info.set_ocsp_url("http://ocsp.test.invalid")
    assert info.get_ocsp_url() == "http://ocsp.test.invalid"


def test_crl_url_round_trip() -> None:
    info = CertSignatureInformation()
    assert info.get_crl_url() is None
    info.set_crl_url("http://crl.test.invalid")
    assert info.get_crl_url() == "http://crl.test.invalid"


def test_issuer_url_round_trip() -> None:
    info = CertSignatureInformation()
    assert info.get_issuer_url() is None
    info.set_issuer_url("http://ca.test.invalid/issuer.crt")
    assert info.get_issuer_url() == "http://ca.test.invalid/issuer.crt"


def test_issuer_certificates_default_empty_set() -> None:
    """The mutable ``issuer_certificates`` set defaults to ``set()`` so
    callers can mutate it in place."""
    info = CertSignatureInformation()
    issuers = info.get_issuer_certificates()
    assert isinstance(issuers, set)
    assert len(issuers) == 0


def test_issuer_certificates_mutation_visible_through_getter(self_signed_cert) -> None:
    """The set returned by :meth:`get_issuer_certificates` is the same
    backing object as ``self._issuer_certificates`` — mutating it via the
    getter is visible on subsequent calls."""
    cert, _ = self_signed_cert
    info = CertSignatureInformation()
    issuers = info.get_issuer_certificates()
    issuers.add(cert)
    # Same object returned the second time.
    assert info.get_issuer_certificates() is issuers
    assert cert in info.get_issuer_certificates()


def test_cert_chain_round_trip() -> None:
    parent = CertSignatureInformation()
    child = CertSignatureInformation()
    parent.set_cert_chain(child)
    assert parent.get_cert_chain() is child


def test_cert_chain_can_be_cleared() -> None:
    parent = CertSignatureInformation()
    child = CertSignatureInformation()
    parent.set_cert_chain(child)
    parent.set_cert_chain(None)
    assert parent.get_cert_chain() is None


def test_tsa_certs_round_trip() -> None:
    parent = CertSignatureInformation()
    tsa = CertSignatureInformation()
    parent.set_tsa_certs(tsa)
    assert parent.get_tsa_certs() is tsa


def test_alternative_cert_chain_round_trip() -> None:
    parent = CertSignatureInformation()
    alt = CertSignatureInformation()
    parent.set_alternative_cert_chain(alt)
    assert parent.get_alternative_cert_chain() is alt


def test_alternative_cert_chain_default_is_none() -> None:
    info = CertSignatureInformation()
    assert info.get_alternative_cert_chain() is None


def test_two_instances_have_independent_issuer_sets(self_signed_cert) -> None:
    """A defensive check on the ctor — two instances must NOT share the
    ``_issuer_certificates`` backing set (would happen if the default
    was set on the class body instead of in ``__init__``)."""
    cert, _ = self_signed_cert
    a = CertSignatureInformation()
    b = CertSignatureInformation()
    a.get_issuer_certificates().add(cert)
    assert cert not in b.get_issuer_certificates()


def test_chained_nodes_form_three_level_tree() -> None:
    """Build a leaf→intermediate→root tree via ``set_cert_chain`` and
    confirm the chain walks correctly."""
    root = CertSignatureInformation()
    root.set_self_signed(True)
    intermediate = CertSignatureInformation()
    intermediate.set_cert_chain(root)
    leaf = CertSignatureInformation()
    leaf.set_cert_chain(intermediate)

    walked = []
    node: CertSignatureInformation | None = leaf
    while node is not None:
        walked.append(node)
        node = node.get_cert_chain()
    assert len(walked) == 3
    assert walked[-1] is root
    assert walked[-1].is_self_signed() is True
