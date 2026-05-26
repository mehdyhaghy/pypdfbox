"""Wave 1286 tests for the closed-loop PKCS#7 verifier in
:meth:`PDSignature.verify`.

Covers the upstream-TODO redesign in two halves:

1. Full SignedAttributes signature math (RFC 5652 §5.4) — the
   SignerInfo signature is now verified against the certificate's
   public key, not just the message-digest digest-of-byteranges.
2. Optional chain-trust walk against an explicit list of trust roots,
   wired through the new ``trust_roots`` keyword argument.

All certs in the tests are self-signed and inline so the test suite
stays offline.
"""

from __future__ import annotations

import datetime
import io

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    Pkcs7Signature,
    compute_byte_range,
    strip_signature_padding,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
    _DIGEST_OID_HEX_TO_HASH,
    _encode_der_length,
    _hash_for_oid,
    _read_der_tlv,
    _verify_chain_trust,
    _verify_signed_attrs_signature,
    _walk_signer_info,
)

# ---------- inline self-signed cert helpers ----------


def _make_signed_cert(
    common_name: str,
    issuer_key: rsa.RSAPrivateKey,
    issuer_name: x509.Name,
    *,
    is_ca: bool = False,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Sign a fresh RSA cert with ``issuer_key``."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(tz=datetime.UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
    cert = builder.sign(issuer_key, hashes.SHA256())
    return cert, key


_root_counter = 0


def _make_root(name: str = "") -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Self-signed root. Each call uses a unique subject DN so two
    independently-generated roots don't collide by name when compared."""
    global _root_counter
    _root_counter += 1
    cn = name or f"test-root-{_root_counter}"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
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


def _build_pkcs7_signed_document(
    signer_cert: x509.Certificate,
    signer_key: rsa.RSAPrivateKey,
    additional_certs: list[x509.Certificate] | None = None,
) -> tuple[bytes, list[int], bytes]:
    """Build (document_bytes, /ByteRange, splice_bytes) signed by ``signer_cert``."""
    prefix = b"%PDF-1.7\n" + b"A" * 32
    suffix = b"B" * 32 + b"\n%%EOF\n"
    placeholder = b"\x00" * 4096
    document_template = prefix + b"<" + placeholder + b">" + suffix
    open_idx = len(prefix)
    close_idx = open_idx + 1 + len(placeholder)
    byte_range = compute_byte_range(document_template, open_idx, close_idx)
    bracketed = (
        document_template[byte_range[0] : byte_range[0] + byte_range[1]]
        + document_template[byte_range[2] : byte_range[2] + byte_range[3]]
    )
    signer = Pkcs7Signature(
        signer_cert,
        signer_key,
        additional_certificates=additional_certs or [],
    )
    blob = signer.sign(io.BytesIO(bracketed))
    splice = blob + b"\x00" * (len(placeholder) - len(blob))
    document = prefix + b"<" + splice + b">" + suffix
    return document, byte_range, splice


# ---------- low-level DER helpers ----------


def test_encode_der_length_short_form() -> None:
    assert _encode_der_length(0) == b"\x00"
    assert _encode_der_length(127) == b"\x7f"


def test_encode_der_length_long_form() -> None:
    assert _encode_der_length(128) == b"\x81\x80"
    assert _encode_der_length(256) == b"\x82\x01\x00"


def test_encode_der_length_rejects_negative() -> None:
    try:
        _encode_der_length(-1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for negative length")


def test_read_der_tlv_parses_sequence() -> None:
    # DER encoding of `INTEGER 42` is 0x02 0x01 0x2a
    tag, header_len, body, body_len = _read_der_tlv(b"\x02\x01\x2a", 0)
    assert tag == 0x02
    assert header_len == 2
    assert body == 2
    assert body_len == 1


# ---------- digest-OID map sanity ----------


def test_digest_oid_map_covers_sha256_to_512() -> None:
    """Exact OIDs from RFC 5754 §3.2."""
    assert _DIGEST_OID_HEX_TO_HASH["608648016503040201"] == "SHA256"
    assert _DIGEST_OID_HEX_TO_HASH["608648016503040202"] == "SHA384"
    assert _DIGEST_OID_HEX_TO_HASH["608648016503040203"] == "SHA512"


def test_hash_for_oid_returns_pyca_object() -> None:
    h = _hash_for_oid(bytes.fromhex("608648016503040201"))
    assert h is not None
    assert h.name.lower() == "sha256"


def test_hash_for_oid_returns_none_for_unknown() -> None:
    assert _hash_for_oid(b"\x99\x99") is None


# ---------- SignerInfo walker ----------


def test_walk_signer_info_extracts_fields() -> None:
    cert, key = _make_root()
    blob = Pkcs7Signature(cert, key).sign(io.BytesIO(b"payload"))
    info = _walk_signer_info(blob)
    assert info is not None
    assert info["signed_attrs_set"].startswith(b"\x31")  # SET tag
    assert len(info["signature"]) >= 64  # at minimum a real RSA sig
    # SHA-256 OID body present somewhere in the digest_algo_oid field.
    assert info["digest_algo_oid"] == bytes.fromhex("608648016503040201")
    # rsaEncryption OID body.
    assert info["signature_algo_oid"] == bytes.fromhex("2a864886f70d010101")


def test_walk_signer_info_returns_none_for_garbage() -> None:
    assert _walk_signer_info(b"this is not DER") is None


# ---------- end-to-end PDSignature.verify ----------


def test_verify_full_pkcs7_signature_math_passes() -> None:
    """A PKCS#7 blob freshly produced by ``Pkcs7Signature`` must verify
    end-to-end: digest match + signed-attrs signature math."""
    cert, key = _make_root()
    document, byte_range, splice = _build_pkcs7_signed_document(cert, key)

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document)
    assert result.is_valid is True
    assert not result.errors


def test_verify_tampered_signature_blob_fails_signature_math() -> None:
    """If we corrupt the signature octets the digest check would still
    pass (it's a separate field) but the signed-attrs math must fail."""
    cert, key = _make_root()
    document, byte_range, splice = _build_pkcs7_signed_document(cert, key)
    # Flip a byte deep inside the splice (target the signature OCTET
    # STRING tail, well past the SignerInfo header).
    tampered_splice = bytearray(splice)
    # The pkcs#7 blob ends well before the placeholder fills up; flip
    # a byte ~256 bytes from the end of the real blob.
    pkcs7_end = len(strip_signature_padding(bytes(tampered_splice)))
    tampered_splice[pkcs7_end - 16] ^= 0xFF

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(bytes(tampered_splice))

    result = sig.verify(document)
    assert result.is_valid is False
    assert result.errors


def test_verify_chain_trust_against_trusted_root_passes() -> None:
    """Chain-trust walk with the signer's own cert as a trust root must
    pass even though the chain is trivial (signer is self-signed)."""
    cert, key = _make_root()
    document, byte_range, splice = _build_pkcs7_signed_document(cert, key)

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document, trust_roots=[cert])
    assert result.is_valid is True
    assert not result.errors


def test_verify_chain_trust_with_unrelated_root_fails() -> None:
    """An unrelated trust root must reject the signer's chain."""
    cert, key = _make_root()
    unrelated_root, _ = _make_root()
    document, byte_range, splice = _build_pkcs7_signed_document(cert, key)

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document, trust_roots=[unrelated_root])
    assert result.is_valid is False
    # Diagnostic mentions the chain.
    assert any(
        "self-signed" in e or "chain" in e.lower() for e in result.errors
    )


def test_verify_chain_trust_through_intermediate() -> None:
    """signer -> intermediate -> root, root is the trust anchor."""
    root_cert, root_key = _make_root()
    inter_cert, inter_key = _make_signed_cert(
        "test-intermediate", root_key, root_cert.subject, is_ca=True
    )
    leaf_cert, leaf_key = _make_signed_cert(
        "test-leaf", inter_key, inter_cert.subject
    )

    document, byte_range, splice = _build_pkcs7_signed_document(
        leaf_cert, leaf_key, additional_certs=[inter_cert]
    )

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document, trust_roots=[root_cert])
    assert result.is_valid is True, result.errors


def test_verify_chain_trust_broken_when_intermediate_missing() -> None:
    """When the intermediate isn't embedded in the PKCS#7 blob the
    walker can't reach the trusted root."""
    root_cert, root_key = _make_root()
    inter_cert, inter_key = _make_signed_cert(
        "test-intermediate", root_key, root_cert.subject, is_ca=True
    )
    leaf_cert, leaf_key = _make_signed_cert(
        "test-leaf", inter_key, inter_cert.subject
    )
    # Don't include the intermediate in additional_certs.
    document, byte_range, splice = _build_pkcs7_signed_document(
        leaf_cert, leaf_key
    )

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document, trust_roots=[root_cert])
    assert result.is_valid is False
    assert any("chain" in e.lower() for e in result.errors)


def test_verify_with_empty_trust_roots_skips_chain_trust() -> None:
    """``trust_roots=[]`` keeps the upstream behaviour of digest +
    signature math only."""
    cert, key = _make_root()
    document, byte_range, splice = _build_pkcs7_signed_document(cert, key)

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document, trust_roots=[])
    assert result.is_valid is True


# ---------- low-level helpers callable independently ----------


def test_verify_signed_attrs_signature_unknown_algorithm() -> None:
    """An unknown signature algorithm OID yields ``ok=False`` with
    a diagnostic rather than raising."""
    cert, _ = _make_root()
    ok, err = _verify_signed_attrs_signature(
        cert,
        b"\x31\x00",
        b"\x00" * 256,
        digest_algo_oid=bytes.fromhex("608648016503040201"),
        signature_algo_oid=b"\x99\x99\x99",
    )
    assert ok is False
    assert err is not None
    assert "unsupported" in err.lower()


def test_verify_chain_trust_no_roots_skips() -> None:
    """An empty trust-roots list returns ``ok=False`` with a "no roots"
    error (the verify-level caller treats this as a *skip*, not a fail)."""
    cert, _ = _make_root()
    ok, err = _verify_chain_trust(cert, [], [])
    assert ok is False
    assert err is not None
    assert "no trust roots" in err.lower()


def test_verify_chain_trust_with_self_signed_in_roots() -> None:
    """Self-signed cert IS its own root."""
    cert, _ = _make_root()
    ok, err = _verify_chain_trust(cert, [], [cert])
    assert ok is True
    assert err is None
