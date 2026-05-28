"""Live Apache PDFBox differential parity for AES-256 ``/EncryptMetadata`` —
the *wire-bytes* facet that the decoded-metadata cases in
``test_crypt_filter_oracle.py`` (wave 1427) don't reach.

Per PDF 32000-1 §7.6.4.4.1, when the ``/Encrypt`` dictionary carries
``/EncryptMetadata false`` the catalog's ``/Metadata`` XMP stream MUST be
left CLEARTEXT on the wire — the bytes between ``stream\\n`` and
``\\nendstream`` are the literal XMP packet, with no AES enciphering
applied. This is the standard pattern for "search-engine-indexable
encrypted PDF": an indexer that doesn't have the password can still walk
the catalog and read the metadata. ``test_crypt_filter_oracle.py``
exercises PDFBox's ``PDMetadata.exportXMPMetadata`` (the decoded payload);
this module looks at the literal disk bytes via the ``EncryptMetadataWire``
probe, which reads the raw file and isolates the on-disk stream payload
without going through PDFBox's automatic decrypt pass.

Directions covered (AES-256 / V=5 / R=6):

* **pypdfbox writes ``/EncryptMetadata false`` → PDFBox reads** — the wire
  prefix is the literal XMP (starts with ``<?xpacket``) AND PDFBox confirms
  ``/EncryptMetadata`` is ``false`` on the wire.
* **pypdfbox writes ``/EncryptMetadata true`` (default) → PDFBox reads** —
  the wire prefix does NOT look like XML (AES-CBC ciphertext starts with
  the 16-byte IV which is uniformly random) and PDFBox confirms
  ``/EncryptMetadata`` is either ``true`` or ``absent`` (spec default).
* **PDFBox writes (``true`` only — 3.0.7's ``StandardProtectionPolicy``
  lacks ``setEncryptMetadata``) → pypdfbox reads** — the wire prefix is
  ciphertext (PDFBox enciphered the metadata) and pypdfbox's reader still
  recovers the decoded XMP via ``PDMetadata.export_xmp_metadata`` (the
  decryption path works).

Triage if the cleartext-on-wire case fails: pypdfbox's
``COSWriter.visit_from_stream`` is supposed to skip the encryption pass
when the active handler reports ``is_encrypt_metadata()==False`` AND the
stream carries ``/Type /Metadata`` (the wave 1367 exemption). A failure
here means the writer enciphered the metadata bytes despite the policy
flag — the regression /EncryptMetadata false is designed to avoid.
"""

from __future__ import annotations

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
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "owner-md-wire"
_USER_PW = "user-md-wire"

# A small, deterministic XMP packet — the wire-bytes assertions key off the
# fact that this byte string is *recognisable* (starts with ``<?xpacket``)
# and PDFBox's metadata-off output puts it on disk verbatim. The leading BOM
# (``\xef\xbb\xbf``) is part of the conventional XMP packet header so a
# real-world indexer would see it on disk; we keep it for realism but the
# wire-prefix check tolerates whatever first byte the writer emits as long
# as it's the XML angle-bracket on the cleartext path.
_XMP_PACKET = (
    b"<?xpacket begin='\xef\xbb\xbf' id='EncryptMetadataWireWave1452'?>\n"
    b"<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF "
    b"xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'/>"
    b"</x:xmpmeta>\n<?xpacket end='r'?>"
)
_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (EncMetaWire wave1452 payload) Tj ET"


# --------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _build_doc_with_metadata() -> PDDocument:
    """Fresh PDDocument with one page + a ``/Type /Metadata`` XMP stream."""
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)

    content = COSStream()
    with content.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(content)

    meta_stream = COSStream()
    with meta_stream.create_raw_output_stream() as out:
        out.write(_XMP_PACKET)
    meta_stream.set_name(COSName.TYPE, "Metadata")
    meta_stream.set_name(COSName.SUBTYPE, "XML")
    pd.get_document_catalog().set_metadata(PDMetadata(meta_stream))
    return pd


def _py_encrypt_aes256(
    out_path: Path, *, encrypt_metadata: bool
) -> None:
    """Write an AES-256 (V=5 / R=6) encrypted PDF with the requested
    ``/EncryptMetadata`` flag. Closes the writer doc before returning so the
    file handle is released on Windows runners (CLAUDE.md cross-platform
    note)."""
    pd = _build_doc_with_metadata()
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(256)
        policy.set_prefer_aes(True)
        policy.set_encrypt_metadata(encrypt_metadata)
        pd.protect(policy)
        pd.save(str(out_path))
    finally:
        pd.close()


def _java_inspect(path: Path, password: str) -> dict[str, str]:
    """Run ``EncryptMetadataWireProbe inspect`` and parse the framed report
    into a dict — every key is ``<name>`` (without the trailing colon)."""
    raw = run_probe_text(
        "EncryptMetadataWireProbe", "inspect", str(path), password
    )
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key] = value
    return fields


# ====================== pypdfbox writes → PDFBox reads ======================


@requires_oracle
def test_pypdfbox_encrypt_metadata_false_leaves_xmp_cleartext_on_wire(
    tmp_path: Path,
) -> None:
    """pypdfbox writes AES-256 with ``/EncryptMetadata false``. PDFBox reads
    the raw file bytes and confirms:

    * the ``/Encrypt`` dict carries ``/EncryptMetadata false``;
    * the catalog ``/Metadata`` stream's first 32 disk bytes are the literal
      XMP packet (start with ``<`` — angle bracket of the XMP open tag);
    * the entire XMP packet is present verbatim on disk (no AES applied).

    This is the regression `/EncryptMetadata false` is designed to avoid —
    a writer that obeys the flag in key derivation only but still enciphers
    the metadata bytes would break every external indexer."""
    enc = tmp_path / "py_md_false.pdf"
    _py_encrypt_aes256(enc, encrypt_metadata=False)

    # Wire-byte sanity: the XMP packet appears verbatim on disk.
    assert _XMP_PACKET in enc.read_bytes(), (
        "pypdfbox enciphered the /Metadata stream despite "
        "/EncryptMetadata=false — wave 1452 wire-bytes regression"
    )

    fields = _java_inspect(enc, _USER_PW)
    assert fields["ENCRYPT_METADATA"] == "false"
    assert fields["METADATA_OBJ"] != "-"
    # First disk byte is the literal ``<`` of the XMP packet open. AES-CBC
    # output starts with a random 16-byte IV so this would be a 1/256 false-
    # positive risk against a buggy encryptor; the verbatim-substring check
    # above plus METADATA_LOOKS_XML below pin the assertion further.
    assert fields["METADATA_RAW_HEX"].startswith("3c"), (  # 0x3c == '<'
        f"metadata not cleartext on disk: prefix={fields['METADATA_RAW_HEX']}"
    )
    assert fields["METADATA_LOOKS_XML"] == "true"
    assert int(fields["METADATA_RAW_LEN"]) == len(_XMP_PACKET)


@requires_oracle
def test_pypdfbox_encrypt_metadata_true_enciphers_metadata_on_wire(
    tmp_path: Path,
) -> None:
    """pypdfbox writes AES-256 with the default ``/EncryptMetadata true``.
    PDFBox reads the raw file bytes and confirms:

    * the ``/Encrypt`` dict carries ``/EncryptMetadata true`` or omits the
      entry (spec default is true — pypdfbox doesn't emit the entry when it
      matches the default, see ``prepare_document`` wave 1367);
    * the catalog ``/Metadata`` stream's first 32 disk bytes do NOT match
      the literal XMP packet — AES-CBC enciphering produced ciphertext;
    * the ``LOOKS_XML`` heuristic returns ``false``.

    This is the symmetric guard: when the flag is true (default) the
    metadata MUST be enciphered, otherwise an attacker can read it without
    the password."""
    enc = tmp_path / "py_md_true.pdf"
    _py_encrypt_aes256(enc, encrypt_metadata=True)

    # /EncryptMetadata true is the default — XMP packet does NOT appear
    # verbatim anywhere on disk (the stream body is ciphertext).
    assert _XMP_PACKET not in enc.read_bytes(), (
        "metadata leaked cleartext despite /EncryptMetadata=true"
    )

    fields = _java_inspect(enc, _USER_PW)
    # pypdfbox omits the entry when it matches the spec default (wave 1367)
    # — both "true" and "absent" are spec-valid signals of "encrypt metadata".
    assert fields["ENCRYPT_METADATA"] in ("true", "absent")
    assert fields["METADATA_OBJ"] != "-"
    # On-disk prefix is AES ciphertext — vanishingly unlikely to start with
    # the ``<`` byte that XML starts with (1/256 false positive). The
    # LOOKS_XML predicate captures the heuristic so we don't depend on a
    # single byte alone.
    assert fields["METADATA_LOOKS_XML"] == "false", (
        f"metadata prefix looks like XML on wire when /EncryptMetadata=true: "
        f"hex={fields['METADATA_RAW_HEX']}"
    )
    # AES-CBC pads to a 16-byte block boundary; the on-disk body is at least
    # the IV (16 bytes) + one block, so >= 32 bytes regardless of XMP length.
    assert int(fields["METADATA_RAW_LEN"]) >= 32


# ====================== PDFBox writes (true only) → pypdfbox reads ==========


@requires_oracle
def test_pdfbox_aes256_default_metadata_encrypted_pypdfbox_recovers(
    tmp_path: Path,
) -> None:
    """PDFBox 3.0.7's ``StandardProtectionPolicy`` has no
    ``setEncryptMetadata``, so the WRITE side always emits R6 with metadata
    ENCIPHERED (the wave-1427 ``CryptFilterProbe`` flips the flag post-protect
    to test the false case for R6 — a different scenario). This direction
    confirms the symmetric reverse: a PDFBox-encrypted file with the default
    ``/EncryptMetadata`` is enciphered on the wire AND pypdfbox decrypts the
    metadata back to its original XMP packet via its R6 reader.

    Uses the existing ``EncryptProbe`` (R6 = key length 256, preferAES=true)
    which never sets ``/EncryptMetadata`` so the on-the-wire dict either
    omits the entry (spec default true) or carries ``true``. The shared
    fixture carries a catalog ``/Metadata`` XMP packet (a stock
    ``<?xpacket ...>`` block produced by the original fixture author), so
    PDFBox enciphers it on save — we assert the wire prefix is NOT the
    cleartext XMP byte and that pypdfbox's reader recovers the original
    XMP through its R6 decrypt path."""
    _fixture_present()
    from pypdfbox.text import PDFTextStripper  # noqa: PLC0415 — local oracle dep

    # Capture the plaintext catalog /Metadata before encryption — the
    # plaintext bytes are what the AES pass enciphers, so they must NOT
    # appear verbatim on disk in the encrypted file.
    with PDDocument.load(str(_FIXTURE)) as src_doc:
        src_meta = src_doc.get_document_catalog().get_metadata()
        assert src_meta is not None, (
            "fixture changed — re-pick a fixture with a /Metadata stream"
        )
        with src_meta.get_cos_object().create_input_stream() as src_stream:
            plaintext_xmp = src_stream.read()

    enc = tmp_path / "java_md_true.pdf"
    run_probe(
        "EncryptProbe",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        "256",
        "true",
    )

    # Wire-bytes sanity: the original XMP packet does NOT appear verbatim
    # in the encrypted file (PDFBox enciphered it under the default
    # /EncryptMetadata=true).
    assert plaintext_xmp not in enc.read_bytes(), (
        "PDFBox 3.0.7 leaked plaintext /Metadata despite default "
        "/EncryptMetadata — fixture or PDFBox behaviour drifted"
    )

    fields = _java_inspect(enc, _USER_PW)
    # PDFBox 3.0.7's StandardProtectionPolicy always leaves /EncryptMetadata
    # at its default (entry absent → spec default true). pypdfbox's
    # PDEncryption.is_encrypt_meta_data also defaults to true on absence.
    assert fields["ENCRYPT_METADATA"] in ("true", "absent")
    assert fields["METADATA_OBJ"] != "-"
    # On-disk prefix is AES ciphertext — the cleartext XMP started with
    # ``<?xpacket`` (0x3c). The first byte of AES output is the random IV
    # so this would be a 1/256 false-positive risk; the verbatim-substring
    # check above plus LOOKS_XML pin the assertion further.
    assert fields["METADATA_LOOKS_XML"] == "false", (
        "PDFBox-encrypted /Metadata still looks like XML on the wire: "
        f"hex={fields['METADATA_RAW_HEX']}"
    )

    with PDDocument.load(str(enc), password=_USER_PW) as doc:
        py_enc = doc.get_encryption()
        assert py_enc is not None
        assert py_enc.is_encrypt_meta_data() is True
        # pypdfbox decrypts the metadata stream back to the original XMP.
        py_meta = doc.get_document_catalog().get_metadata()
        assert py_meta is not None
        with py_meta.get_cos_object().create_input_stream() as src:
            recovered = src.read()
        text = PDFTextStripper().get_text(doc)
    assert recovered == plaintext_xmp, (
        "pypdfbox's R6 reader did not recover the cleartext XMP from "
        "PDFBox-enciphered metadata"
    )
    # Fixture has page content — non-empty recovery proves the AES-256
    # read path works on a PDFBox-written file.
    assert text.strip(), "pypdfbox failed to recover text from PDFBox R6 file"
