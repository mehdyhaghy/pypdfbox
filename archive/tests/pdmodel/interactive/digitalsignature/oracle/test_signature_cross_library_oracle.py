"""Live cross-library differential parity for PDF digital signatures.

Two directions, both anchored against the pinned Apache PDFBox 3.0.7 jar
(via BouncyCastle, which the app jar bundles):

* **Java-signs → pypdfbox-verifies** (``SignProbe``). Apache PDFBox signs a
  fixture with a freshly minted self-signed RSA cert, producing a detached
  ``adbe.pkcs7.detached`` SignedData. We reload the signed file in pypdfbox
  and assert :meth:`PDSignature.verify` recovers the *same* signer subject
  and serial, the *same* ``/ByteRange``, and reports digest-match +
  ``is_valid``. This is the direction that surfaced the BER indefinite-length
  bug: BouncyCastle's ``CMSSignedDataGenerator`` emits the blob in BER
  indefinite-length form, which the DER-only ``strip_signature_padding`` /
  SignerInfo walker mishandled (fixed wave 1411).

* **pypdfbox-signs → Java-verifies** (``SigInspectProbe``). pypdfbox signs a
  fixture via :class:`Pkcs7Signature` + :meth:`PDDocument.save_incremental`;
  the Java probe reloads it, rebuilds the detached CMS over the bracketed
  ``/ByteRange`` bytes, and asks BouncyCastle's
  ``SignerInformation.verify(...)`` whether the digest + signer signature
  hold. We assert Java recovers the same signer/serial/byte-range and reports
  ``digestIntact=true``.

The probes mint their own certs (Java in ``SignProbe``, Python here), so the
suite stays offline and deterministic.
"""

from __future__ import annotations

import datetime
import warnings
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    Pkcs7Signature,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[5]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"
_FIXTURE = _FIXTURES / "pdfwriter" / "unencrypted.pdf"

# Subject DN string SignProbe.java mints (kept in sync with the probe).
_JAVA_SIGNER_CN = "oracle-sign-probe"


# --------------------------------------------------------------- helpers


def _parse_probe_kv(text: str) -> dict[str, str]:
    """Parse ``key=value`` lines from a probe's stdout into a dict."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_self_signed_cert(
    common_name: str,
    org: str,
    serial: int,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


# ---------------------------------------------- Java-signs → pypdfbox-verifies


@requires_oracle
def test_java_signed_document_verifies_in_pypdfbox(tmp_path: Path) -> None:
    """Apache PDFBox signs; pypdfbox verifies the same signer, byte-range and
    a matching, intact digest."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    signed = tmp_path / "java_signed.pdf"
    probe_out = _parse_probe_kv(
        run_probe_text("SignProbe", str(_FIXTURE), str(signed))
    )
    # SignProbe prints the cert it minted; capture for cross-checks.
    java_serial = int(probe_out["serial"])
    assert _JAVA_SIGNER_CN in probe_out["subject"]

    data = signed.read_bytes()
    with PDDocument.load(signed) as doc:
        sigs = doc.get_signature_dictionaries()
        assert len(sigs) == 1
        sig = sigs[0]

        # Byte range is the canonical four-tuple bracketing the whole file
        # minus the /Contents window.
        byte_range = sig.get_byte_range()
        assert byte_range is not None
        assert len(byte_range) == 4
        assert byte_range[0] == 0
        assert byte_range[2] + byte_range[3] == len(data)
        assert sig.get_sub_filter() == "adbe.pkcs7.detached"

        # Full verify must succeed end-to-end: parse the BER (indefinite-length)
        # BouncyCastle blob, recover the cert, match the digest, and pass the
        # SignerInfo signature math.
        result = sig.verify(data)
        assert result.is_valid is True, result.errors
        assert not result.errors

        # Same signer the Java probe minted.
        assert result.signer_serial_number == java_serial
        assert _JAVA_SIGNER_CN in (result.signer_subject or "")
        assert result.has_signer()
        assert result.has_signed_digest()
        assert result.has_computed_digest()
        assert result.digest_matches()


@requires_oracle
def test_java_signed_document_byte_range_matches_inspect_probe(
    tmp_path: Path,
) -> None:
    """The /ByteRange pypdfbox reads equals what PDFBox's own getByteRange
    reports for the same signed file — a pure byte-range parity cross-check."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    signed = tmp_path / "java_signed.pdf"
    run_probe_text("SignProbe", str(_FIXTURE), str(signed))

    java_inspect = _parse_probe_kv(
        run_probe_text("SigInspectProbe", str(signed))
    )
    java_byte_range = [int(x) for x in java_inspect["sig.0.byterange"].split(",")]
    assert java_inspect["sig.0.digestIntact"] == "true"

    with PDDocument.load(signed) as doc:
        py_byte_range = doc.get_signature_dictionaries()[0].get_byte_range()
    assert py_byte_range == java_byte_range


@requires_oracle
def test_java_signed_then_tampered_fails_pypdfbox_verify(tmp_path: Path) -> None:
    """A byte flipped inside the signed /ByteRange of a Java-signed file makes
    pypdfbox report a digest mismatch — the interop verify is not a rubber
    stamp."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    signed = tmp_path / "java_signed.pdf"
    run_probe_text("SignProbe", str(_FIXTURE), str(signed))
    data = bytearray(signed.read_bytes())

    with PDDocument.load(signed) as doc:
        byte_range = doc.get_signature_dictionaries()[0].get_byte_range()
    assert byte_range is not None
    # Flip a byte squarely inside range 1 (well before the /Contents window).
    tamper_idx = byte_range[1] // 2
    data[tamper_idx] ^= 0xFF
    tampered = signed.with_name("java_signed_tampered.pdf")
    tampered.write_bytes(bytes(data))

    with PDDocument.load(tampered) as doc:
        sig = doc.get_signature_dictionaries()[0]
        result = sig.verify(bytes(data))
        assert result.is_valid is False
        assert not result.digest_matches()
        assert any("digest" in e.lower() for e in result.errors)


# ---------------------------------------------- pypdfbox-signs → Java-verifies


@requires_oracle
def test_pypdfbox_signed_document_verifies_in_java(tmp_path: Path) -> None:
    """pypdfbox signs; the Java oracle recovers the same signer/serial and
    byte-range and reports the digest intact under BouncyCastle's verifier."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    serial = 0x0CAFE1234
    cert, key = _make_self_signed_cert(
        "pypdfbox-sign-probe", "pypdfbox-py-signer", serial
    )
    signed = tmp_path / "py_signed.pdf"

    with PDDocument.load(_FIXTURE) as doc:
        sig = PDSignature()
        sig.set_name("pypdfbox signer")
        sig.set_reason("py -> java parity")
        doc.add_signature(sig, Pkcs7Signature(cert, key))
        doc.save_incremental(signed)

    data = signed.read_bytes()
    # pypdfbox-side byte range, for the cross-check below.
    with PDDocument.load(signed) as doc:
        py_byte_range = doc.get_signature_dictionaries()[0].get_byte_range()
    assert py_byte_range is not None
    assert py_byte_range[0] == 0
    assert py_byte_range[2] + py_byte_range[3] == len(data)

    # --- Java oracle inspects + verifies ---
    java = _parse_probe_kv(run_probe_text("SigInspectProbe", str(signed)))
    assert java["count"] == "1"
    assert java["sig.0.subfilter"] == "adbe.pkcs7.detached"
    assert java["sig.0.digestIntact"] == "true"
    assert int(java["sig.0.serial"]) == serial
    assert "pypdfbox-sign-probe" in java["sig.0.subject"]

    java_byte_range = [int(x) for x in java["sig.0.byterange"].split(",")]
    assert java_byte_range == py_byte_range


@requires_oracle
def test_pypdfbox_signed_then_tampered_fails_java_verify(tmp_path: Path) -> None:
    """A byte flipped inside the signed range of a pypdfbox-signed file makes
    the Java oracle report ``digestIntact=false`` — the py→Java digest binding
    is real, not coincidental."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    cert, key = _make_self_signed_cert(
        "pypdfbox-tamper-probe", "pypdfbox-py-signer", 0xBEEF
    )
    signed = tmp_path / "py_signed_for_tamper.pdf"
    with PDDocument.load(_FIXTURE) as doc:
        sig = PDSignature()
        doc.add_signature(sig, Pkcs7Signature(cert, key))
        doc.save_incremental(signed)

    data = bytearray(signed.read_bytes())
    with PDDocument.load(signed) as doc:
        byte_range = doc.get_signature_dictionaries()[0].get_byte_range()
    assert byte_range is not None
    data[byte_range[1] // 2] ^= 0xFF
    tampered = tmp_path / "py_signed_tampered.pdf"
    tampered.write_bytes(bytes(data))

    java = _parse_probe_kv(run_probe_text("SigInspectProbe", str(tampered)))
    # Cert is still recovered (the tamper is outside /Contents), but the
    # digest no longer matches the signed messageDigest. BouncyCastle signals
    # this either by returning false or by throwing a digest-mismatch
    # exception (CMSSignerDigestMismatchException); both mean "not intact".
    digest_intact = java["sig.0.digestIntact"]
    assert digest_intact != "true"
    assert digest_intact == "false" or digest_intact.startswith("error:")
    assert "pypdfbox-tamper-probe" in java["sig.0.subject"]


# --------------------------------------- round-trip robustness (no warnings)


@requires_oracle
def test_java_signed_verify_robust_under_warning_as_error(tmp_path: Path) -> None:
    """Verifying a Java-signed (BER indefinite-length) blob must not let the
    PyCA ``cryptography`` BER UserWarning escalate into a verify failure when
    the caller runs under ``-W error`` (strict test suites do). Regression
    guard for the wave-1411 warning-suppression fix."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    signed = tmp_path / "java_signed_warn.pdf"
    run_probe_text("SignProbe", str(_FIXTURE), str(signed))
    data = signed.read_bytes()

    with PDDocument.load(signed) as doc:
        sig = doc.get_signature_dictionaries()[0]
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            result = sig.verify(data)
    assert result.is_valid is True, result.errors
    assert not result.errors
