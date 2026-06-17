"""Live Apache PDFBox differential parity for /ByteRange byte-offset arithmetic.

Direction: **pypdfbox-writes → Java-reads**. pypdfbox builds a 1-page PDF, adds
a :class:`PDSignature`, and drives the *external-signing* path
(:meth:`PDDocument.save_incremental_for_external_signing` →
:meth:`ExternalSigningSupport.set_signature`). That path is the one that does
the load-bearing byte-offset math: render the increment with a
``/Contents <0…0>`` placeholder and a ``/ByteRange [0 ☐ ☐ ☐]`` placeholder,
then locate the placeholders and patch in the real four-integer
``/ByteRange`` so the two bracketed slices span the *entire file except the
bytes between* ``<`` *and* ``>`` (ISO 32000-1 §12.8.1).

``ByteRangeProbe`` loads the resulting signed PDF with Apache PDFBox 3.0.7 and
reports the four ``/ByteRange`` integers exactly as PDFBox parses them, plus
ground-truth invariants it derives independently from the raw file bytes
(``getSignedContent(fileBytes)`` length, the ``<``/``>`` delimiter positions,
and whether the range covers the whole file minus the ``/Contents`` hex).

We assert THREE things agree:
  1. pypdfbox's :meth:`ExternalSigningSupport.get_byte_range` four-integer
     array == the array PDFBox parses from the on-disk ``/ByteRange``;
  2. pypdfbox's bracketed content (``get_content()`` length) == PDFBox's
     ``getSignedContent(fileBytes).length``;
  3. the byte-offset arithmetic satisfies the spec invariants (range starts at
     0, brackets the ``<…>`` /Contents string at its delimiters, runs to EOF).

No key/cert material is committed; the PKCS#7 blob is produced in-test with a
self-signed cert built via ``cryptography``.
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature, Pkcs7Signature
from tests.oracle.harness import requires_oracle, run_probe_text


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_self_signed_cert(
    cn: str = "pypdfbox-byterange-signer",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-byterange-oracle"),
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


def _build_unsigned_pdf(out: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage()
        page.set_resources(PDResources())
        doc.add_page(page)
        doc.save(out)
    finally:
        doc.close()


def _sign_external(src: Path, out: Path) -> tuple[list[int], int]:
    """Sign ``src`` via the external-signing byte-range path, writing ``out``.

    Returns ``(byte_range, signed_content_len)`` as pypdfbox computed them so
    the test can assert against PDFBox's read-back without re-deriving them.
    """
    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
        sig.set_sub_filter(PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED)
        sig.set_name("pypdfbox byterange signer")
        sig.set_reason("differential byte-range parity")
        # add_signature stages the pending signature; the external path renders
        # the placeholder and computes /ByteRange.
        doc.add_signature(sig, signer)
        with open(out, "wb") as fh:
            handle = doc.save_incremental_for_external_signing(fh)
            content = handle.get_content()
            byte_range = handle.get_byte_range()
            pkcs7 = signer.sign(io.BytesIO(content))
            handle.set_signature(pkcs7)
    return byte_range, len(content)


# --------------------------------------------------------- the parity tests


@requires_oracle
def test_byte_range_array_matches_pdfbox(tmp_path: Path) -> None:
    """The four ``/ByteRange`` integers pypdfbox computes equal exactly the
    array Apache PDFBox parses from the same on-disk signature dictionary."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    py_byte_range, _ = _sign_external(unsigned, signed)

    java = _parse_probe_kv(run_probe_text("ByteRangeProbe", str(signed)))
    assert java["count"] == "1"
    assert java["sig.0.byterange"] == ",".join(str(n) for n in py_byte_range)


@requires_oracle
def test_byte_range_brackets_contents_delimiters(tmp_path: Path) -> None:
    """The computed range brackets the ``/Contents`` hex string exactly at its
    ``<`` and ``>`` delimiters, and starts at byte 0 — the spec invariant."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    py_byte_range, _ = _sign_external(unsigned, signed)

    java = _parse_probe_kv(run_probe_text("ByteRangeProbe", str(signed)))
    # PDFBox-derived: the `<`/`>` delimiters sit OUTSIDE the ranges (matching
    # PDFBox's own COSWriter): the `<` is at a+b, the `>` at c-1.
    assert java["sig.0.byteRangeMatchesContents"] == "true"
    # pypdfbox: a==0, and the byte at range1's end (the first excluded byte)
    # is the `<`; the byte just before range2's start is the `>`.
    a, b, c, d = py_byte_range
    assert a == 0
    raw = signed.read_bytes()
    assert raw[a + b : a + b + 1] == b"<"
    assert raw[c - 1 : c] == b">"


@requires_oracle
def test_byte_range_covers_whole_file_except_contents(tmp_path: Path) -> None:
    """range1 + range2 cover the entire file save the bytes strictly between
    the ``/Contents`` delimiters; range2 runs to EOF (c + d == fileLength)."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    py_byte_range, _ = _sign_external(unsigned, signed)

    java = _parse_probe_kv(run_probe_text("ByteRangeProbe", str(signed)))
    assert java["sig.0.coversWholeFileExceptContents"] == "true"

    a, b, c, d = py_byte_range
    file_len = len(signed.read_bytes())
    assert int(java["sig.0.fileLength"]) == file_len
    assert a == 0
    assert b < c
    assert (c + d) == file_len


@requires_oracle
def test_signed_content_length_matches_pdfbox(tmp_path: Path) -> None:
    """The bracketed bytes pypdfbox hands the external signer
    (``get_content()``) are exactly the bytes PDFBox would digest:
    ``getSignedContent(fileBytes).length == len1 + len2``."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    py_byte_range, py_content_len = _sign_external(unsigned, signed)

    java = _parse_probe_kv(run_probe_text("ByteRangeProbe", str(signed)))
    _, b, _, d = py_byte_range
    assert py_content_len == b + d
    assert int(java["sig.0.signedContentLength"]) == py_content_len


@requires_oracle
def test_get_contents_byterange_matches_pdfbox(tmp_path: Path) -> None:
    """A pypdfbox-signed document, re-sliced by Apache PDFBox's
    ``getContents(byte[])`` (the /ByteRange-arithmetic overload:
    ``begin = br[0]+br[1]+1`` / ``len = br[2]-begin-1``), yields exactly the
    embedded ``/Contents`` COSString blob — AND exactly what pypdfbox's own
    :meth:`PDSignature.get_contents_from_bytes` re-derives. This pins the
    writer's /ByteRange delimiter convention (``<``/``>`` excluded) against
    upstream's exact reader arithmetic in both languages."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    _sign_external(unsigned, signed)

    java = _parse_probe_kv(
        run_probe_text("SignatureContentsByteRangeProbe", str(signed))
    )
    assert java["count"] == "1"
    # Java: the /ByteRange-sliced contents == the embedded COSString contents.
    assert java["sig.0.agree"] == "true"

    # pypdfbox's reader must extract the same blob from the same /ByteRange.
    raw = signed.read_bytes()
    with PDDocument.load(signed) as doc:
        sigs = doc.get_signature_dictionaries()
        assert len(sigs) == 1
        py_via_byte_range = sigs[0].get_contents_from_bytes(raw)
        py_via_cos_string = sigs[0].get_contents()
    assert py_via_byte_range == py_via_cos_string
    # And it agrees with PDFBox's getContents(byte[]) byte-for-byte.
    assert py_via_byte_range.hex().upper() == java["sig.0.byteRangeHex"]
