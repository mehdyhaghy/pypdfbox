"""Tests for ``CertificateVerifier``."""

from __future__ import annotations

import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.cert.certificate_verifier import (
    CertificateVerificationException,
    CertificateVerifier,
)


def _build_intermediate_cert(
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    *,
    common_name: str = "pypdfbox-intermediate",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Issue an intermediate CA cert signed by ``issuer_cert`` / ``issuer_key``.

    The new cert is NOT self-signed: subject != issuer, signature verifiable
    via the issuer's public key. Carries Basic Constraints CA:TRUE so chain
    walks treat it as a CA.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)],
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
    )
    cert = builder.sign(issuer_key, hashes.SHA256())
    return cert, key


def _build_leaf_signed_by(
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    *,
    common_name: str = "pypdfbox-leaf",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)],
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
    )
    cert = builder.sign(issuer_key, hashes.SHA256())
    return cert, key


def _build_ec_self_signed() -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-ec")],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        CertificateVerifier()


def test_is_self_signed_true_for_self_signed_cert(self_signed_cert):
    cert, _ = self_signed_cert
    assert CertificateVerifier.is_self_signed(cert) is True


def test_verify_certificate_rejects_self_signed_when_disallowed(self_signed_cert):
    cert, _ = self_signed_cert
    result = CertificateVerifier.verify_certificate(
        cert, additional_certs=[], verify_self_signed_cert=False, sign_date=None
    )
    assert result.is_valid() is False
    assert isinstance(result.get_exception(), CertificateVerificationException)


def test_verify_certificate_accepts_self_signed_when_allowed(self_signed_cert):
    cert, _ = self_signed_cert
    result = CertificateVerifier.verify_certificate(
        cert, additional_certs=[cert], verify_self_signed_cert=True, sign_date=None
    )
    assert result.is_valid() is True
    assert result.get_result() == [cert]


def test_extract_ocsp_url(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    assert (
        CertificateVerifier.extract_ocsp_url(cert)
        == "http://ocsp.test.invalid/check"
    )


def test_extract_ca_issuers_url(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    urls = CertificateVerifier.extract_ca_issuers_url(cert)
    assert urls == ["http://ca.test.invalid/issuer.crt"]


def test_download_extra_certificates_returns_empty_set(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    # Offline-safe stub — should not attempt the network.
    assert CertificateVerifier.download_extra_certificates(cert) == set()


def test_check_revocations_returns_for_self_signed(self_signed_cert):
    cert, _ = self_signed_cert
    # A self-signed cert is the trust anchor — should short-circuit.
    CertificateVerifier.check_revocations(cert, [cert], sign_date=None)


def test_check_revocations_with_issuer_uses_crl_when_ocsp_absent(self_signed_cert):
    """When the cert has no OCSP AIA URL we fall straight through to CRL.

    Without ``crl_overrides`` the offline-friendly :class:`CRLVerifier`
    just logs and returns, so the dispatch should complete cleanly.
    """
    cert, _ = self_signed_cert
    # ``cert`` is self-signed; issuer is itself. Recursion stops immediately.
    CertificateVerifier.check_revocations_with_issuer(
        cert, cert, [cert], sign_date=None,
    )


def test_check_revocations_with_issuer_attempts_ocsp_then_falls_back(
    self_signed_with_revocation,
):
    """When OCSP is advertised, an OcspHelper is constructed and consulted.

    The offline OcspHelper stub's ``get_response_ocsp`` returns ``None`` so
    no exception is raised and the CRL fall-back path is never taken.
    """
    cert, _ = self_signed_with_revocation
    # Self-signed, so the recursion stops after the OCSP attempt.
    CertificateVerifier.check_revocations_with_issuer(
        cert, cert, [cert], sign_date=None,
    )


def test_extract_ocspurl_alias_returns_same_value(self_signed_with_revocation):
    cert, _ = self_signed_with_revocation
    assert (
        CertificateVerifier.extract_ocspurl(cert)
        == CertificateVerifier.extract_ocsp_url(cert)
    )


def test_extract_ocsp_url_absent(self_signed_cert):
    cert, _ = self_signed_cert
    # No AIA extension at all → returns None.
    assert CertificateVerifier.extract_ocsp_url(cert) is None


def test_extract_ca_issuers_url_absent(self_signed_cert):
    cert, _ = self_signed_cert
    # No AIA extension → empty list.
    assert CertificateVerifier.extract_ca_issuers_url(cert) == []


def test_verify_certificate_no_root_raises(self_signed_cert):
    """An intermediate-only ``additional_certs`` list lacks a self-signed
    anchor, so ``verify_certificate`` must produce a CertificateVerification
    Exception result with the ``No root certificate`` message."""
    root_cert, root_key = self_signed_cert
    intermediate, _intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    result = CertificateVerifier.verify_certificate(
        intermediate,
        additional_certs=[intermediate],  # not self-signed → treated as intermediate
        verify_self_signed_cert=True,
        sign_date=None,
    )
    assert result.is_valid() is False
    assert "No root certificate" in str(result.get_exception())


def test_verify_certificate_builds_chain_with_intermediate(self_signed_cert):
    root_cert, root_key = self_signed_cert
    intermediate, intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    leaf, _leaf_key = _build_leaf_signed_by(intermediate, intermediate_key)
    result = CertificateVerifier.verify_certificate(
        leaf,
        additional_certs=[intermediate, root_cert],
        verify_self_signed_cert=True,
        sign_date=None,
    )
    assert result.is_valid() is True
    chain = result.get_result()
    assert chain[0] == leaf
    assert chain[1] == intermediate
    assert chain[-1] == root_cert


def test_verify_certificate_wraps_unexpected_exception(
    self_signed_cert, monkeypatch,
):
    """Force ``_build_chain`` to raise a non-CertificateVerificationException
    so the broad ``except Exception`` branch wraps it as a fresh
    CertificateVerificationException result."""
    root_cert, _root_key = self_signed_cert

    def _explode(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(CertificateVerifier, "_build_chain", _explode)

    result = CertificateVerifier.verify_certificate(
        root_cert,
        additional_certs=[root_cert],
        verify_self_signed_cert=True,
        sign_date=None,
    )
    assert result.is_valid() is False
    assert "verifying" in str(result.get_exception()).lower()


def test_verify_certificate_chain_returns_chain(self_signed_cert):
    root_cert, root_key = self_signed_cert
    intermediate, _ik = _build_intermediate_cert(root_cert, root_key)
    chain = CertificateVerifier.verify_certificate_chain(
        intermediate,
        trust_anchors=[root_cert],
        intermediate_certs=[],
        sign_date=None,
    )
    assert chain[0] == intermediate
    assert chain[-1] == root_cert


def test_build_chain_raises_when_issuer_missing(self_signed_cert):
    root_cert, root_key = self_signed_cert
    intermediate, intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    leaf, _leaf_key = _build_leaf_signed_by(intermediate, intermediate_key)
    # Provide only the leaf — neither intermediate nor root is in the pool.
    with pytest.raises(CertificateVerificationException):
        CertificateVerifier.verify_certificate_chain(
            leaf,
            trust_anchors=[],
            intermediate_certs=[],
            sign_date=None,
        )


def test_is_self_signed_false_when_subject_differs(self_signed_cert):
    root_cert, root_key = self_signed_cert
    intermediate, _ = _build_intermediate_cert(root_cert, root_key)
    assert CertificateVerifier.is_self_signed(intermediate) is False


def test_is_self_signed_handles_exception_gracefully(monkeypatch):
    """When the verification helper raises an unexpected exception, the
    lenient catch should return False (mirroring the upstream
    ``Couldn't get signature information`` branch)."""

    class _Cert:
        class _Name:
            def __eq__(self, other):  # noqa: D401 - x-ref
                # Force ``cert.subject == cert.issuer`` to be True so we
                # exercise the inner ``_verify_signed_by`` call.
                return True

            def __ne__(self, other):
                return False

        subject = _Name()
        issuer = _Name()

    monkeypatch.setattr(
        CertificateVerifier,
        "_verify_signed_by",
        staticmethod(
            lambda _a, _b: (_ for _ in ()).throw(RuntimeError("noise")),
        ),
    )
    # ``_verify_signed_by`` is invoked inside the try-block; since the
    # contrived cert raises, the surrounding catch returns False.
    assert CertificateVerifier.is_self_signed(_Cert()) is False


def test_verify_signed_by_returns_false_when_signature_invalid(
    self_signed_cert,
):
    root_cert, root_key = self_signed_cert
    intermediate, intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    # ``intermediate`` is signed by ``root_key`` but we feed the leaf's own
    # cert in place of the issuer, so the signature check must fail and the
    # helper returns False.
    assert (
        CertificateVerifier._verify_signed_by(intermediate, intermediate)  # noqa: SLF001
        is False
    )


def test_verify_signed_by_supports_ec_issuer():
    ec_cert, _ = _build_ec_self_signed()
    # The EC self-signed cert verifies against its own public key, exercising
    # the EllipticCurvePublicKey branch.
    assert (
        CertificateVerifier._verify_signed_by(ec_cert, ec_cert)  # noqa: SLF001
        is True
    )


def test_check_revocations_raises_when_issuer_missing(self_signed_cert):
    root_cert, root_key = self_signed_cert
    intermediate, intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    leaf, _leaf_key = _build_leaf_signed_by(intermediate, intermediate_key)
    with pytest.raises(CertificateVerificationException):
        CertificateVerifier.check_revocations(
            leaf, additional_certs=[], sign_date=None,
        )


def test_check_revocations_recurses_to_self_signed_anchor(self_signed_cert):
    root_cert, root_key = self_signed_cert
    intermediate, intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    leaf, _leaf_key = _build_leaf_signed_by(intermediate, intermediate_key)
    # No OCSP / no CRL on any cert → CRLVerifier is a no-op so the recursive
    # walk terminates cleanly at the root anchor.
    CertificateVerifier.check_revocations(
        leaf,
        additional_certs=[intermediate, root_cert],
        sign_date=None,
    )


def test_check_revocations_with_issuer_falls_back_to_crl_on_ocsp_exception(
    self_signed_with_revocation, monkeypatch,
):
    cert, _ = self_signed_with_revocation

    from pypdfbox.examples.signature.cert import ocsp_helper as _ocsp_mod

    class _ExplodingOcsp:
        def __init__(self, *args, **kwargs):
            pass

        def get_response_ocsp(self):
            raise _ocsp_mod.OcspException("boom")

    monkeypatch.setattr(_ocsp_mod, "OcspHelper", _ExplodingOcsp)

    # CRL fall-back: the offline CRLVerifier is a no-op so the call returns
    # silently after logging the warning.
    CertificateVerifier.check_revocations_with_issuer(
        cert, cert, [cert], sign_date=None,
    )


def test_check_revocations_with_issuer_recurses_into_non_self_signed_issuer(
    self_signed_cert,
):
    root_cert, root_key = self_signed_cert
    intermediate, intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )
    leaf, _leaf_key = _build_leaf_signed_by(intermediate, intermediate_key)
    # Issuer (intermediate) is not self-signed, so the helper must recurse
    # back into ``check_revocations`` to walk up to the root.
    CertificateVerifier.check_revocations_with_issuer(
        leaf, intermediate, [intermediate, root_cert], sign_date=None,
    )


def test_verify_ocsp_calls_verify_resp_status_when_response_present():
    captured = {}

    class _Resp:
        pass

    class _Helper:
        def get_response_ocsp(self):
            return _Resp()

        def verify_resp_status(self, resp):
            captured["resp"] = resp

    CertificateVerifier.verify_ocsp(_Helper(), additional_certs=[])
    assert isinstance(captured["resp"], _Resp)


def test_verify_ocsp_skips_when_no_response():
    class _Helper:
        def get_response_ocsp(self):
            return None

        def verify_resp_status(self, resp):  # pragma: no cover - shouldn't fire
            raise AssertionError("verify_resp_status should not be called")

    # No response → verify_resp_status never invoked, no exception.
    CertificateVerifier.verify_ocsp(_Helper(), additional_certs=[])


def test_download_extra_certificates_with_ca_issuers_url(
    self_signed_with_revocation,
):
    # The cert has a caIssuers URL; the helper logs but never fetches.
    cert, _ = self_signed_with_revocation
    assert CertificateVerifier.download_extra_certificates(cert) == set()


def test_build_chain_breaks_on_cycle(self_signed_cert, monkeypatch):
    """If the chain loops (issuer fingerprint already seen), ``_build_chain``
    must break out of the while loop rather than infinite-recurse."""
    root_cert, root_key = self_signed_cert
    intermediate, _intermediate_key = _build_intermediate_cert(
        root_cert, root_key,
    )

    # Force is_self_signed → False so the while-loop keeps running, and
    # _find_issuer keeps returning the same intermediate (which is already
    # in ``seen`` once we've appended it once).
    monkeypatch.setattr(
        CertificateVerifier, "is_self_signed", staticmethod(lambda _c: False),
    )

    call_count = {"n": 0}

    def _stub_find(cert, _pool):  # noqa: ARG001
        call_count["n"] += 1
        return intermediate

    monkeypatch.setattr(
        CertificateVerifier, "_find_issuer", staticmethod(_stub_find),
    )
    chain = CertificateVerifier._build_chain(  # noqa: SLF001
        intermediate, [intermediate], [root_cert],
    )
    # The break fires the second iteration (issuer already seen), so the
    # chain has at most two entries.
    assert len(chain) <= 2


def test_verify_signed_by_else_branch_via_stub(monkeypatch):
    """Drive the ``else`` branch (neither RSA nor EC) of ``_verify_signed_by``
    by feeding stubs whose ``public_key()`` is neither RSAPublicKey nor
    EllipticCurvePublicKey. The bare ``verify`` call is invoked and, on
    success, returns True."""
    call: dict[str, int] = {"n": 0}

    class _Pk:
        def verify(self, *_args):
            call["n"] += 1

    class _Cert:
        signature = b"\x00\x00"
        tbs_certificate_bytes = b"\x00\x00"
        signature_hash_algorithm = None

    class _Issuer:
        @staticmethod
        def public_key():
            return _Pk()

    assert (
        CertificateVerifier._verify_signed_by(_Cert(), _Issuer())  # noqa: SLF001
        is True
    )
    assert call["n"] == 1


def test_first_aia_returns_none_when_only_other_method_present():
    """Build a cert whose AIA carries ONLY ``caIssuers`` (no OCSP), then
    confirm ``extract_ocsp_url`` returns ``None`` even though the AIA
    extension itself is present — exercising the loop-completion branch."""
    from cryptography.x509.oid import AuthorityInformationAccessOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-ca-only")],
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        access_method=AuthorityInformationAccessOID.CA_ISSUERS,
                        access_location=x509.UniformResourceIdentifier(
                            "http://ca-only.test.invalid/issuer.crt"
                        ),
                    )
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    assert CertificateVerifier.extract_ocsp_url(cert) is None
