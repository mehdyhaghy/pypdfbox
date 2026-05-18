"""Wave 1352 coverage-boost tests for the pd_signature module.

Closes the remaining uncovered branches in
:mod:`pypdfbox.pdmodel.interactive.digitalsignature.pd_signature`:

* line 301 — ``_verify_signed_attrs_signature`` EC successful-verify return.
* lines 304-305 — EC arm raising :class:`ValueError`.
* line 366 — ``_verify_chain_trust`` non-root link with invalid issuer
  signature (the ``return err or "..."`` fallback).
* line 370 — chain pathological-loop guard.
* line 385 — ``_verify_cert_signature`` cert with no
  ``signature_hash_algorithm`` (Ed25519 / RFC 8410 certs).
* lines 404-406 — issuer-side ``ValueError`` + unsupported-issuer-key-type.
"""

from __future__ import annotations

import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
    _verify_cert_signature,
    _verify_chain_trust,
    _verify_signed_attrs_signature,
)


def _ec_self_signed(name: str) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _rsa_self_signed(name: str) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _ed25519_self_signed(name: str) -> tuple[x509.Certificate, ed25519.Ed25519PrivateKey]:
    key = ed25519.Ed25519PrivateKey.generate()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(key, None)  # Ed25519 doesn't take a hash algorithm
    )
    return cert, key


# ---------- _verify_signed_attrs_signature EC success path (line 301) ----------


def test_verify_signed_attrs_signature_ec_success() -> None:
    """A fresh ECDSA signature over signed-attrs DER passes — exercises the
    EC ``return True, None`` branch (line 301)."""
    cert, key = _ec_self_signed("ec-good")
    signed_attrs = b"\x31\x05\x02\x01\x00\x01\x01"
    # Sign with the SAME hash family the verifier will use (SHA-256 for
    # 2.16.840.1.101.3.4.2.1).
    sig = key.sign(signed_attrs, ec.ECDSA(hashes.SHA256()))
    ok, err = _verify_signed_attrs_signature(
        cert,
        signed_attrs_set_der=signed_attrs,
        signature=sig,
        digest_algo_oid=bytes.fromhex("608648016503040201"),
        signature_algo_oid=bytes.fromhex("2a8648ce3d040302"),  # ecdsa-with-SHA256
    )
    assert ok is True
    assert err is None


# ---------- _verify_signed_attrs_signature EC arm ValueError (lines 304-305) ----------


def test_verify_signed_attrs_signature_ec_value_error_path() -> None:
    """A TypeError raised by cryptography's verify() lands in the EC
    arm's (ValueError, TypeError) handler — lines 304-305."""
    cert, _ = _ec_self_signed("ec-value-error")
    ok, err = _verify_signed_attrs_signature(
        cert,
        signed_attrs_set_der=b"\x31\x00",
        # str (not bytes) → cryptography raises TypeError, caught at
        # line 304-305.
        signature="not bytes",  # type: ignore[arg-type]
        digest_algo_oid=bytes.fromhex("608648016503040201"),
        signature_algo_oid=bytes.fromhex("2a8648ce3d040302"),
    )
    assert ok is False
    assert err is not None
    assert "raised" in err.lower()


# ---------- _verify_chain_trust invalid issuer sig in chain (line 366) ----------


def test_verify_chain_trust_intermediate_signature_invalid() -> None:
    """Build a chain where the leaf claims to be issued by an intermediate
    that's in the embedded pool, but the leaf's actual signature was made
    with the wrong key. The chain walk reaches ``_verify_cert_signature``,
    that returns ok=False, and the ``return False, err`` line (366) fires."""
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "rsa-root")]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_subject)
        .issuer_name(root_subject)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(root_key, hashes.SHA256())
    )
    # Leaf claims root_subject as issuer but is signed with its own (leaf)
    # key — so verifying leaf.signature with root's public key fails.
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "rsa-leaf-mismatch")]
    )
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(leaf_subject)
        .issuer_name(root_subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(leaf_key, hashes.SHA256())  # wrong signer
    )
    ok, err = _verify_chain_trust(leaf_cert, [], [root_cert])
    assert ok is False
    assert err is not None
    # Could be "issuer signature is invalid" (from cert_signature path)
    # or "issuer signature check failed" fallback.
    assert "invalid" in err.lower() or "issuer" in err.lower()


# ---------- _verify_chain_trust pathological loop (line 370) ----------


def test_verify_chain_trust_loop_guard() -> None:
    """Two non-root certs whose ``issuer`` fields point at each other —
    A.issuer = B.subject, B.issuer = A.subject. The walker bounces
    between them without ever finding a self-signed root or hitting one
    of the trust_roots, eventually exhausting the loop counter and
    returning the chain-too-long error (line 370).

    To exercise the bouncing path we need each cert's signature to be
    verifiable by the other (i.e. each really did sign the other), which
    is impossible to build with the real X.509 builder in a single step.
    Instead we cross-sign: A is signed by B's key, B is signed by A's
    key, but neither is self-signed. The chain-walker reaches each cert,
    verifies the signature against the (other) cert's public key, and
    keeps walking until the counter expires.
    """
    key_a = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_b = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subj_a = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "A")])
    subj_b = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "B")])
    now = datetime.datetime.now(tz=datetime.UTC)
    # cert_a: subject A, issuer B, signed by key_b
    cert_a = (
        x509.CertificateBuilder()
        .subject_name(subj_a)
        .issuer_name(subj_b)
        .public_key(key_a.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key_b, hashes.SHA256())
    )
    # cert_b: subject B, issuer A, signed by key_a
    cert_b = (
        x509.CertificateBuilder()
        .subject_name(subj_b)
        .issuer_name(subj_a)
        .public_key(key_b.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key_a, hashes.SHA256())
    )
    # A different self-signed cert as the trust root — neither cert_a
    # nor cert_b chain to it. Both cert_a AND cert_b are in the embedded
    # pool so the walker can hop back-and-forth and eventually exhaust
    # the iteration budget at line 370.
    unrelated_root, _ = _rsa_self_signed("unrelated-root")
    ok, err = _verify_chain_trust(
        cert_a,
        embedded_certs=[cert_a, cert_b],
        trust_roots=[unrelated_root],
    )
    assert ok is False
    assert err is not None
    assert "too long" in err.lower() or "loop" in err.lower()


# ---------- _verify_cert_signature: no signature_hash_algorithm (line 385) ----------


def test_verify_cert_signature_ed25519_has_no_hash_algorithm() -> None:
    """Ed25519 / RFC 8410 X.509 certs have ``signature_hash_algorithm
    is None`` because EdDSA does its own internal hashing. The chain
    walker bails with the no-hash-algorithm error (line 385)."""
    cert, _ = _ed25519_self_signed("ed25519-cert")
    # ``cert`` as both the subject and the issuer — the hash-algorithm
    # check fires before any key-type dispatch.
    ok, err = _verify_cert_signature(cert, cert)
    assert ok is False
    assert err is not None
    assert "hash algorithm" in err.lower()


# ---------- _verify_cert_signature ValueError (line 404-405) ----------


def test_verify_cert_signature_value_error_path() -> None:
    """Force the issuer's RSA verify() to raise ValueError. Subclass
    RSAPublicKey + ABC-register the stub so the isinstance(public_key,
    rsa.RSAPublicKey) check passes; the verify call then raises
    ValueError which is caught at lines 404-405.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

    cert, _ = _rsa_self_signed("cert-needing-verify")

    class _BrokenRSAKey:
        def verify(self, *_args: object, **_kwargs: object) -> None:
            raise ValueError("simulated cryptography ValueError")

    _rsa.RSAPublicKey.register(_BrokenRSAKey)

    class _IssuerWrapper:
        def __init__(self, subject: x509.Name) -> None:
            self.subject = subject

        def public_key(self) -> _BrokenRSAKey:
            return _BrokenRSAKey()

    ok, err = _verify_cert_signature(
        cert,
        _IssuerWrapper(cert.subject),  # type: ignore[arg-type]
    )
    assert ok is False
    assert err is not None
    assert "raised" in err.lower()


# ---------- _verify_cert_signature unsupported issuer key type (line 406) ----------


def test_verify_cert_signature_unsupported_issuer_key_type() -> None:
    """Issuer holds an Ed25519 public key — neither the RSA nor the EC
    arm matches, and the function falls through to the "unsupported
    issuer key type" return (line 406).

    To trigger this we wrap a real Ed25519 issuer cert. The subject
    cert is an RSA cert whose .signature_hash_algorithm is not None
    (so we get past line 385).
    """
    cert, _ = _rsa_self_signed("rsa-subject")
    ed_cert, _ = _ed25519_self_signed("ed-issuer")
    # Use real Ed25519 cert as issuer — its public_key() is Ed25519PublicKey
    # which is neither RSA nor EC.
    ok, err = _verify_cert_signature(cert, ed_cert)
    assert ok is False
    assert err is not None
    assert "unsupported" in err.lower()


# ---------- bonus: _verify_signed_attrs_signature with key-OID mismatch ----------


def test_verify_signed_attrs_signature_oid_key_mismatch_returns_unsupported() -> None:
    """RSA cert + ECDSA-style signature OID → neither arm of the
    isinstance/startswith dispatch matches, and the function falls
    through to the "unsupported signature algorithm" return at line 307."""
    cert, _ = _rsa_self_signed("rsa-key-ec-oid")
    ok, err = _verify_signed_attrs_signature(
        cert,
        signed_attrs_set_der=b"\x31\x00",
        signature=b"\x00" * 256,
        digest_algo_oid=bytes.fromhex("608648016503040201"),
        signature_algo_oid=bytes.fromhex("2a8648ce3d040302"),  # ECDSA OID
    )
    assert ok is False
    assert err is not None
    assert "unsupported" in err.lower()


def test_verify_chain_trust_root_self_signed_invalid_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A root cert in trust_roots that fails its OWN self-signature
    check returns the "self-signed root failed self-verify" error
    (lines 354-357). Monkeypatch the cert's verify path to fail."""
    cert, _ = _rsa_self_signed("bad-self-verify")

    # Replace the cert's public_key().verify with a stub that raises
    # InvalidSignature so the self-verify fails. To do this without
    # touching the immutable certificate, monkeypatch the module-level
    # helper to return ok=False for self-signed checks.
    from pypdfbox.pdmodel.interactive.digitalsignature import pd_signature

    original = pd_signature._verify_cert_signature

    def _fail_self(c: object, i: object) -> tuple[bool, str | None]:
        if c is i:
            return False, "synthetic failure"
        return original(c, i)  # type: ignore[arg-type]

    monkeypatch.setattr(pd_signature, "_verify_cert_signature", _fail_self)
    ok, err = _verify_chain_trust(cert, [], [cert])
    assert ok is False
    assert err is not None
    assert "self-verify" in err.lower() or "self-signed" in err.lower()
