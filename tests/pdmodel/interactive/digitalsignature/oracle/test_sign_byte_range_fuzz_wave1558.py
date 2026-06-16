"""Live Apache PDFBox differential parity for the SAVE-TIME signature
``/ByteRange`` + ``/Contents`` placeholder computation.

Direction: **both-sides**. ``SignByteRangeFuzzProbe`` (Java) signs a tiny
self-built PDF with Apache PDFBox 3.0.7 across ~18 configurations — default
/Contents size, several explicit ``SignatureOptions.setPreferredSignatureSize``
values, a non-positive preferred size (ignored → default), multi-page docs, a
document signed a SECOND time (two incremental revisions), and a preferred size
too small for the CMS blob — and projects the structural facts: the four
``/ByteRange`` integers, the /Contents hex length, the gap between the two
ByteRange segments (which must equal the hex length + 2 for the ``<`` / ``>``
delimiters), the signature count after save, file-coverage, and loadability.

pypdfbox reproduces the same matrix through
:meth:`PDDocument.add_signature` + :meth:`PDDocument.save_incremental` and the
test pins BOTH the Java oracle output (when the jar + JDK are present) and the
pypdfbox output against the PDFBox-3.0.7-derived expected values.

Key invariants pinned (oracle-confirmed, see ``SignByteRangeFuzzProbe``):
  * the /Contents hex slot is exactly ``2 * preferred_signature_size`` chars,
    where ``preferred_signature_size`` defaults to
    ``SignatureOptions.DEFAULT_SIGNATURE_SIZE`` (0x2500 = 9472 bytes →
    18944 hex chars) when no positive size is set;
  * the gap between the two ByteRange segments == hex length + 2;
  * range1 starts at byte 0 and range2 ends at EOF (whole file minus the
    bracketed ``/Contents`` token);
  * signing an already-signed document produces a second signature dict
    (sigCount == 2 after the second incremental revision).

Honest divergence (pinned below): when the preferred size is too small to hold
the CMS blob, **Apache PDFBox** raises ``IOException`` "Can't write signature,
not enough space ..." from its COSWriter, while **pypdfbox** raises
``ValueError`` "... larger than reserved /Contents placeholder ..." from its
splice helper. Both reject; the exception type and message differ.

No key/cert material is committed; the PKCS#7 blob is produced in-test with a
self-signed cert built via ``cryptography``.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature, Pkcs7Signature
from pypdfbox.pdmodel.interactive.digitalsignature.signature_options import (
    DEFAULT_SIGNATURE_SIZE,
    SignatureOptions,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_self_signed_cert(
    cn: str = "pypdfbox-sign-byterange-fuzz",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-oracle"),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_unsigned_pdf(out: Path, page_count: int) -> None:
    doc = PDDocument()
    try:
        for _ in range(page_count):
            page = PDPage()
            page.set_resources(PDResources())
            doc.add_page(page)
        doc.save(out)
    finally:
        doc.close()


def _sign(src: Path, out: Path, preferred_size: int) -> None:
    """Sign ``src`` → ``out`` via add_signature + save_incremental.

    ``preferred_size <= 0`` means "don't attach SignatureOptions" (default
    placeholder); a positive value sets
    ``SignatureOptions.set_preferred_signature_size``.
    """
    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
        sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
        sig.set_name("pypdfbox sign byterange fuzz")
        options = None
        if preferred_size > 0:
            options = SignatureOptions()
            options.set_preferred_signature_size(preferred_size)
        doc.add_signature(sig, signer, options)
        with open(out, "wb") as fh:
            doc.save_incremental(fh)


def _byte_range_facts(signed: Path) -> dict[str, int]:
    """Reload ``signed`` and return the structural facts the probe projects
    for the LAST signature dictionary."""
    raw = signed.read_bytes()
    with PDDocument.load(signed) as doc:
        sigs = doc.get_signature_dictionaries()
        sig_count = len(sigs)
        br = sigs[-1].get_byte_range()
    a, b, c, d = br
    gap = c - (a + b)
    contents_hex_len = -1
    if (
        a + b < len(raw)
        and raw[a + b] == ord("<")
        and 0 <= c - 1 < len(raw)
        and raw[c - 1] == ord(">")
    ):
        contents_hex_len = (c - 1) - (a + b + 1)
    return {
        "sig_count": sig_count,
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "gap": gap,
        "contents_hex_len": contents_hex_len,
        "file_len": len(raw),
    }


# Mirror of SignByteRangeFuzzProbe's emit configurations: (label, pages, pref).
# pref <= 0 means default placeholder. The "too small" case is exercised
# separately (it raises rather than producing a file).
_CONFIGS = [
    ("default_1page", 1, 0),
    ("pref_4096_1page", 1, 4096),
    ("pref_12000_1page", 1, 12000),
    ("pref_0x2500_1page", 1, 0x2500),
    ("pref_nonpositive_1page", 1, -1),
    ("default_2page", 2, 0),
    ("default_3page", 3, 0),
    ("pref_8192_2page", 2, 8192),
    ("pref_3000_3page", 3, 3000),
    ("pref_20000_1page", 1, 20000),
    ("pref_5000_1page", 1, 5000),
    ("pref_2500_1page", 1, 2500),
    ("pref_15000_2page", 2, 15000),
    ("default_4page", 4, 0),
]

_LABEL_IDS = [c[0] for c in _CONFIGS]


# --------------------------------------------------------- pypdfbox-side facts


@pytest.mark.parametrize(("label", "pages", "pref"), _CONFIGS, ids=_LABEL_IDS)
def test_pypdfbox_placeholder_hex_len_matches_preferred_size(
    tmp_path: Path, label: str, pages: int, pref: int
) -> None:
    """pypdfbox reserves exactly ``2 * preferred_size`` hex chars (or
    ``2 * DEFAULT_SIGNATURE_SIZE`` when no positive preference is set), and the
    gap between the two ByteRange segments == hex length + 2. PDFBox-3.0.7-
    derived expectations (SignByteRangeFuzzProbe)."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned, pages)
    _sign(unsigned, signed, pref)

    facts = _byte_range_facts(signed)
    effective_size = pref if pref > 0 else DEFAULT_SIGNATURE_SIZE
    expected_hex_len = effective_size * 2

    assert facts["sig_count"] == 1
    assert facts["contents_hex_len"] == expected_hex_len
    # The gap (range2.start - range1.end) brackets the `<` + hex + `>`.
    assert facts["gap"] == expected_hex_len + 2
    # Whole-file coverage: range1 at 0, range2 to EOF.
    assert facts["a"] == 0
    assert facts["c"] + facts["d"] == facts["file_len"]


def test_pypdfbox_default_size_is_0x2500(tmp_path: Path) -> None:
    """The default reservation equals SignatureOptions.DEFAULT_SIGNATURE_SIZE
    (0x2500 = 9472 bytes → 18944 hex chars), matching Apache PDFBox. Wave 1558
    raised the pypdfbox default from a constant 16384 hex chars to honour the
    upstream default."""
    assert DEFAULT_SIGNATURE_SIZE == 0x2500
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned, 1)
    _sign(unsigned, signed, 0)
    facts = _byte_range_facts(signed)
    assert facts["contents_hex_len"] == 0x2500 * 2
    assert facts["contents_hex_len"] == 18944


def test_pypdfbox_second_sign_yields_two_signatures(tmp_path: Path) -> None:
    """Signing an already-signed document (a second incremental revision)
    produces a second signature dict; the new signature's range still covers
    the whole file minus its own /Contents. Mirrors the probe's
    second_sign_* cases (sigCount == 2)."""
    unsigned = tmp_path / "unsigned.pdf"
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    _build_unsigned_pdf(unsigned, 1)
    _sign(unsigned, first, 0)
    _sign(first, second, 0)

    facts = _byte_range_facts(second)
    assert facts["sig_count"] == 2
    assert facts["a"] == 0
    assert facts["c"] + facts["d"] == facts["file_len"]
    assert facts["gap"] == facts["contents_hex_len"] + 2


def test_pypdfbox_too_small_preferred_size_rejected(tmp_path: Path) -> None:
    """A preferred size too small for the CMS blob is rejected at save time.

    Honest divergence: Apache PDFBox raises ``IOException`` "Can't write
    signature, not enough space ..."; pypdfbox raises ``ValueError`` "...
    larger than reserved /Contents placeholder ...". Both reject."""
    unsigned = tmp_path / "unsigned.pdf"
    out = tmp_path / "should-fail.pdf"
    _build_unsigned_pdf(unsigned, 1)
    with pytest.raises(ValueError, match="larger than reserved"):
        _sign(unsigned, out, 1024)


# --------------------------------------------------------- live oracle parity


@requires_oracle
def test_oracle_placeholder_and_byterange_arithmetic(tmp_path: Path) -> None:
    """Apache PDFBox 3.0.7's own save-time output (SignByteRangeFuzzProbe)
    confirms every structural invariant the pypdfbox-side tests assert, and
    that the default + preferred sizes pypdfbox reproduces match PDFBox's."""
    java = _parse_probe_kv(run_probe_text("SignByteRangeFuzzProbe"))
    count = int(java["count"])
    assert count == 18

    # Map probe label → effective preferred size for the single-sign cases so
    # we can cross-check the Java contentsHexLen against 2 * size.
    expected_size = {
        "default_1page": DEFAULT_SIGNATURE_SIZE,
        "pref_4096_1page": 4096,
        "pref_12000_1page": 12000,
        "pref_0x2500_1page": 0x2500,
        "pref_nonpositive_1page": DEFAULT_SIGNATURE_SIZE,
        "default_2page": DEFAULT_SIGNATURE_SIZE,
        "default_3page": DEFAULT_SIGNATURE_SIZE,
        "pref_8192_2page": 8192,
        "pref_3000_3page": 3000,
        "pref_20000_1page": 20000,
        "pref_5000_1page": 5000,
        "pref_2500_1page": 2500,
        "pref_15000_2page": 15000,
        "default_4page": DEFAULT_SIGNATURE_SIZE,
    }

    saw_too_small = False
    saw_second_sign = False
    for i in range(count):
        prefix = f"case.{i}."
        label = java[prefix + "label"]
        if label.endswith("too_small"):
            # Oracle rejects: raised + "not enough space".
            assert java[prefix + "raised"] == "true"
            assert java[prefix + "messageHasNotEnoughSpace"] == "true"
            saw_too_small = True
            continue

        # Every successful case is loadable and covers the whole file.
        assert java[prefix + "loadable"] == "true"
        assert java[prefix + "coversWholeFileExceptContents"] == "true"
        assert java[prefix + "gapEqualsHexPlusTwo"] == "true"

        gap = int(java[prefix + "gap"])
        contents_hex_len = int(java[prefix + "contentsHexLen"])
        assert gap == contents_hex_len + 2

        if label.startswith("second_sign"):
            assert java[prefix + "sigCount"] == "2"
            saw_second_sign = True
        else:
            assert java[prefix + "sigCount"] == "1"
            assert contents_hex_len == expected_size[label] * 2

    assert saw_too_small
    assert saw_second_sign


@requires_oracle
@pytest.mark.parametrize(("label", "pages", "pref"), _CONFIGS, ids=_LABEL_IDS)
def test_oracle_pypdfbox_same_hex_len(
    tmp_path: Path, label: str, pages: int, pref: int
) -> None:
    """For each single-sign config, pypdfbox's /Contents hex slot equals the
    one Apache PDFBox reserves for the same preferred size."""
    java = _parse_probe_kv(run_probe_text("SignByteRangeFuzzProbe"))
    # Find the matching probe case by label.
    java_hex_len = None
    count = int(java["count"])
    for i in range(count):
        if java[f"case.{i}.label"] == label:
            java_hex_len = int(java[f"case.{i}.contentsHexLen"])
            break
    assert java_hex_len is not None, f"probe case {label} not found"

    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned, pages)
    _sign(unsigned, signed, pref)
    py = _byte_range_facts(signed)

    assert py["contents_hex_len"] == java_hex_len
