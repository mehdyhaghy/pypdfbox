"""Live Apache PDFBox differential parity for the standard-security-handler
``/EncryptMetadata false`` *READ* path.

PDF 32000-1 §7.6.3.2: when the ``/Encrypt`` dictionary carries
``/EncryptMetadata false`` the document's XMP ``/Metadata`` stream is left
CLEARTEXT on disk while every other string/stream stays enciphered. A
conforming reader must therefore do two things on open:

1. Derive the file-encryption key on the *false* branch of Algorithm 2. For
   R3/R4 (RC4-128, AES-128) the algorithm appends four ``0xFF`` bytes to the
   MD5 input when ``/EncryptMetadata`` is false; getting that branch wrong
   yields a key that decrypts nothing → ``InvalidPasswordException``. For R6
   (AES-256) the file key is flag-independent (Algorithm 2.A) but the reader
   must still honour the flag for the metadata-skip below.
2. Leave the catalog ``/Metadata`` stream UNTOUCHED — the bytes on disk are
   already plaintext, so applying the cipher would corrupt them.

``test_crypt_filter_oracle.py`` pins the pypdfbox-WRITES → Java-READS direction
(every revision) and the Java-WRITES → pypdfbox-READS direction for R6 only —
because flipping ``/EncryptMetadata`` post-``protect()`` is lossy for R3/R4
(PDFBox 3.0.7 rejects its own R4 md-off output, confirmed via the oracle). This
module pins the missing facet: the *pypdfbox READER* on its own R3 (RC4-128)
and R6 (AES-256) md-off output must recover the SAME metadata bytes (SHA-256)
and decrypted page text that the Apache PDFBox reference reader recovers from
the identical file. Byte-identical recovery across both engines proves the
read-side false-branch key derivation and the metadata-plaintext skip are at
parity.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_OWNER_PW = "owner-md-flag"
_USER_PW = "user-md-flag"

# Cleartext XMP packet — recognisable bytes so the on-disk-cleartext assertion
# is meaningful. Leading BOM mirrors a real-world XMP packet header.
_XMP_PACKET = (
    b"<?xpacket begin='\xef\xbb\xbf' id='EncryptMetadataFlagProbe'?>\n"
    b"<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF "
    b"xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'/>"
    b"</x:xmpmeta>\n<?xpacket end='r'?>"
)
_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (EncryptMetadataFlag read parity) Tj ET"
_EXPECTED_TEXT = "EncryptMetadataFlag read parity"


def _build_doc_with_metadata() -> PDDocument:
    """Fresh one-page PDDocument carrying a ``/Type /Metadata`` XMP stream."""
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)

    content = COSStream()
    with content.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(content)

    meta = COSStream()
    with meta.create_raw_output_stream() as out:
        out.write(_XMP_PACKET)
    meta.set_name(COSName.TYPE, "Metadata")
    meta.set_name(COSName.SUBTYPE, "XML")
    pd.get_document_catalog().set_metadata(PDMetadata(meta))
    return pd


def _py_encrypt_metadata_off(out_path: Path, key_length: int, prefer_aes: bool) -> None:
    """Encrypt with ``/EncryptMetadata false`` and the requested key family.

    Closes the writer document before returning so the file handle is released
    on Windows runners (CLAUDE.md cross-platform note)."""
    pd = _build_doc_with_metadata()
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        policy.set_encrypt_metadata(False)
        pd.protect(policy)
        pd.save(str(out_path))
    finally:
        pd.close()


def _java_report(path: Path, password: str) -> dict[str, str]:
    """Run ``EncryptMetadataFlagProbe`` and parse the framed report.

    Every key is the prefix before the first ``:`` on its line; ``TEXT`` may
    span further newlines so it is reassembled from the tail."""
    raw = run_probe_text("EncryptMetadataFlagProbe", str(path), password)
    lines = raw.split("\n")
    fields: dict[str, str] = {}
    text_idx = None
    for i, line in enumerate(lines):
        if line.startswith("TEXT:"):
            text_idx = i
            break
        key, _, value = line.partition(":")
        fields[key] = value
    if text_idx is not None:
        fields["TEXT"] = "\n".join(lines[text_idx:])[len("TEXT:") :]
    return fields


def _py_read(path: Path, password: str) -> tuple[bool, bytes | None, str]:
    """pypdfbox reader signal: (is_encrypt_metadata, metadata_bytes, text)."""
    with PDDocument.load(str(path), password=password) as doc:
        enc = doc.get_encryption()
        assert enc is not None
        is_meta = enc.is_encrypt_meta_data()
        meta = doc.get_document_catalog().get_metadata()
        meta_bytes: bytes | None = None
        if meta is not None:
            cos = meta.get_cos_object()
            if isinstance(cos, COSStream):
                with cos.create_input_stream() as src:
                    meta_bytes = src.read()
        text = PDFTextStripper().get_text(doc)
    return is_meta, meta_bytes, text


# (id, key_length, prefer_aes, revision) — the two lossless md-off families.
# R3 (RC4-128) exercises the 0xFF-append false branch of the key derivation;
# R6 (AES-256) exercises the flag-independent key + metadata-skip on read.
_FAMILIES = [
    ("rc4_128", 128, False, 3),
    ("aes_256", 256, True, 6),
]


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes", "revision"),
    _FAMILIES,
    ids=[f[0] for f in _FAMILIES],
)
def test_encrypt_metadata_false_read_matches_pdfbox(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    revision: int,
    tmp_path: Path,
) -> None:
    """pypdfbox encrypts with ``/EncryptMetadata false``; both pypdfbox and
    Apache PDFBox 3.0.7 open the file and must recover:

    * ``is_encrypt_meta_data() == False`` on both readers;
    * a byte-identical ``/Metadata`` stream (compared via SHA-256) that equals
      the original cleartext XMP packet — proving neither reader applied the
      cipher to the plaintext-on-disk metadata; and
    * the same decrypted page text — proving the file-encryption key derived on
      the false branch of Algorithm 2 actually deciphers the content stream.
    """
    enc = tmp_path / f"py_mdoff_{algo_id}.pdf"
    _py_encrypt_metadata_off(enc, key_length, prefer_aes)

    # The /Metadata stream is cleartext on disk; /Contents is enciphered.
    disk = enc.read_bytes()
    assert _XMP_PACKET in disk, f"{algo_id}: /Metadata should be cleartext on disk"
    assert _CONTENT_PAYLOAD not in disk, f"{algo_id}: content leaked cleartext"

    expected_sha = hashlib.sha256(_XMP_PACKET).hexdigest()

    # --- Apache PDFBox reference reader ---
    java = _java_report(enc, _USER_PW)
    assert java.get("OPENED") == "true", f"{algo_id}: PDFBox rejected the file: {java}"
    assert java["ENCRYPTMETA"] == "false"
    assert java["METADATA_SHA256"] == expected_sha, (
        f"{algo_id}: PDFBox recovered different /Metadata bytes than the "
        f"cleartext XMP written on disk"
    )
    assert int(java["METADATA_LEN"]) == len(_XMP_PACKET)
    assert _EXPECTED_TEXT in java["TEXT"]

    # --- pypdfbox reader: must match the reference signal exactly ---
    py_is_meta, py_meta_bytes, py_text = _py_read(enc, _USER_PW)
    assert py_is_meta is False
    assert py_meta_bytes is not None
    py_sha = hashlib.sha256(py_meta_bytes).hexdigest()
    assert py_sha == expected_sha, (
        f"{algo_id}: pypdfbox enciphered/garbled the cleartext /Metadata on "
        f"read — false-branch metadata-skip regression"
    )
    assert py_sha == java["METADATA_SHA256"], (
        f"{algo_id}: pypdfbox and PDFBox disagree on recovered /Metadata bytes"
    )
    assert _EXPECTED_TEXT in py_text
    assert py_text.strip() == java["TEXT"].strip(), (
        f"{algo_id}: decrypted page text diverges between pypdfbox and PDFBox"
    )
