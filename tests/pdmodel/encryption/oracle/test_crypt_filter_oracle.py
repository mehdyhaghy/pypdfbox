"""Live Apache PDFBox differential parity for crypt-filter granularity,
``/EncryptMetadata`` handling, and the ``/Identity`` crypt filter.

Companion to ``test_encryption_interop_oracle.py`` (which covers the
standard-handler password matrix). This module narrows in on the parts of
PDF 32000-1 §7.6.5 / §7.6.3.2 that the password matrix doesn't touch:

* **``/EncryptMetadata false``** — when set, the document's ``/Metadata``
  stream is *not* enciphered (external indexers can read the catalog
  without the password) and the file-encryption key derivation changes for
  R4. pypdfbox encrypts with the flag OFF and Apache PDFBox reads it back,
  confirming ``isEncryptMetaData()==false`` and recovering the cleartext
  metadata + text. The reverse direction (Java produces, pypdfbox reads) is
  pinned through R6 — see ``_ENCRYPT_MD_OFF_NOTE`` for why R4 cannot be used.
* **crypt-filter introspection** — ``/StmF`` / ``/StrF`` / ``/CF`` (with each
  filter's ``/CFM``) and ``isEncryptMetaData()`` must read identically on
  both sides for an AES-encrypted document.
* **``/Identity`` crypt filter** — a stream/string slot pointed at
  ``/Identity`` stays cleartext. pypdfbox's read-side routing table resolves
  it to the pass-through cipher, matching upstream
  ``SecurityHandler``'s ``Identity`` short-circuit.

The Java side is driven by ``oracle/probes/CryptFilterProbe.java`` with three
sub-commands: ``introspect`` (V/R/StmF/StrF/CF/EncryptMeta), ``meta``
(EncryptMeta + the hex of the catalog metadata + extracted text), and
``encrypt-md-off`` (encrypt then flip ``/EncryptMetadata false`` on the live
``/Encrypt`` dict — only valid for R6, where the key is flag-independent).

``_ENCRYPT_MD_OFF_NOTE``: Apache PDFBox 3.0.7 (the pinned oracle baseline)
exposes **no** ``StandardProtectionPolicy.setEncryptMetadata`` — that policy
setter landed in a later release. The only way the 3.0.7 oracle can emit a
standard-handler ``/EncryptMetadata false`` document is to flip the flag on
the ``/Encrypt`` dictionary *after* ``protect()``. For R4 (AES-128) the
file-encryption key derivation depends on the flag (PDF 32000-1 Algorithm 2
step f appends ``0xFFFFFFFF`` when the flag is false), so a post-hoc flip
desynchronises the key — *PDFBox itself* then throws
``InvalidPasswordException`` reopening its own output (verified). For R6
(AES-256) the key is flag-independent (PDF 32000-2 Algorithm 2.A), so the
post-hoc flip is lossless. Hence the Java→pypdfbox metadata-off direction is
pinned at R6 only; the pypdfbox→Java direction covers R3/R4/R6 because
pypdfbox's ``StandardProtectionPolicy.set_encrypt_metadata`` derives the key
with the flag from the start.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "ownerpw"
_USER_PW = "userpw"

_METADATA_XML = (
    b"<?xpacket begin='\xef\xbb\xbf' id='CryptFilterProbeWave1427'?>\n"
    b"<x:xmpmeta xmlns:x='adobe:ns:meta/'><rdf:RDF "
    b"xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'/>"
    b"</x:xmpmeta>\n<?xpacket end='r'?>"
)
_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (CryptFilter wave1427 payload) Tj ET"


# --------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _build_doc_with_metadata() -> tuple[PDDocument, bytes]:
    """Fresh PDDocument with a content stream + ``/Type /Metadata`` stream."""
    pd = PDDocument()
    page = PDPage()
    pd.add_page(page)

    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(_CONTENT_PAYLOAD)
    page.set_contents(stream)

    meta_stream = COSStream()
    with meta_stream.create_raw_output_stream() as out:
        out.write(_METADATA_XML)
    meta_stream.set_name(COSName.TYPE, "Metadata")
    meta_stream.set_name(COSName.SUBTYPE, "XML")
    pd.get_document_catalog().set_metadata(PDMetadata(meta_stream))
    return pd, _CONTENT_PAYLOAD


def _py_encrypt_metadata_off(
    out: Path, key_length: int, prefer_aes: bool
) -> bytes:
    """Encrypt a fresh doc with /EncryptMetadata OFF; return the metadata XML."""
    pd, _payload = _build_doc_with_metadata()
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
        pd.save(str(out))
    finally:
        pd.close()
    return _METADATA_XML


def _py_introspect(path: Path, password: str) -> dict[str, str]:
    """Read the same fields CryptFilterProbe 'introspect' prints, via pypdfbox."""
    with PDDocument.load(str(path), password=password) as doc:
        enc = doc.get_encryption()
        assert enc is not None
        cf = enc.get_cf()
        if cf is None:
            cf_summary = "-"
        else:
            parts: list[str] = []
            for key in cf.key_set():
                name = key.get_name()
                cfd = enc.get_crypt_filter_dictionary(name)
                cfm = cfd.get_cfm() if cfd is not None else None
                parts.append(f"{name}={cfm or '-'}")
            cf_summary = ",".join(parts) if parts else "-"
        return {
            "V": str(enc.get_v()),
            "R": str(enc.get_revision()),
            "STMF": enc.get_stm_f() or "-",
            "STRF": enc.get_str_f() or "-",
            "CF": cf_summary,
            "ENCRYPTMETA": str(enc.is_encrypt_meta_data()).lower(),
        }


def _java_introspect(path: Path, password: str) -> dict[str, str]:
    raw = run_probe_text("CryptFilterProbe", "introspect", str(path), password)
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key] = value
    return fields


def _java_meta(path: Path, password: str) -> tuple[str, bytes | None, str]:
    """Return (encrypt_meta, metadata_bytes_or_None, text) from the Java probe."""
    raw = run_probe_text("CryptFilterProbe", "meta", str(path), password)
    lines = raw.split("\n")
    encrypt_meta = lines[0][len("ENCRYPTMETA:") :]
    meta_field = lines[1][len("META:") :]
    meta_bytes = None if meta_field == "-" else bytes.fromhex(meta_field)
    # TEXT: prefix on line 2, body may contain further newlines.
    text = "\n".join(lines[2:])
    assert text.startswith("TEXT:"), f"probe framing broke: {text[:40]!r}"
    return encrypt_meta, meta_bytes, text[len("TEXT:") :]


def _py_metadata_bytes(path: Path, password: str) -> bytes | None:
    with PDDocument.load(str(path), password=password) as doc:
        meta = doc.get_document_catalog().get_metadata()
        if meta is None:
            return None
        cos = meta.get_cos_object()
        if not isinstance(cos, COSStream):
            return None
        with cos.create_input_stream() as src:
            return src.read()


def _py_text(path: Path, password: str) -> str:
    with PDDocument.load(str(path), password=password) as doc:
        return PDFTextStripper().get_text(doc)


# (id, key_length, prefer_aes) for the pypdfbox→Java metadata-off direction.
_PY_MD_OFF = [
    ("rc4_128", 128, False),
    ("aes_128", 128, True),
    ("aes_256", 256, False),
]


# ----------------------- /EncryptMetadata false: pypdfbox → Java reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _PY_MD_OFF,
    ids=[a[0] for a in _PY_MD_OFF],
)
def test_pypdfbox_encrypts_metadata_off_java_reads(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """pypdfbox encrypts with /EncryptMetadata OFF; Apache PDFBox confirms
    ``isEncryptMetaData()==false``, reads the /Metadata stream as cleartext,
    and recovers the page text. Proves pypdfbox's metadata-off output is
    spec-correct against the reference reader for every supported revision."""
    enc = tmp_path / f"py_mdoff_{algo_id}.pdf"
    meta_xml = _py_encrypt_metadata_off(enc, key_length, prefer_aes)

    # /Metadata stays cleartext on disk; /Contents is enciphered.
    disk = enc.read_bytes()
    assert meta_xml in disk, f"{algo_id}: /Metadata should be cleartext on disk"
    assert _CONTENT_PAYLOAD not in disk, f"{algo_id}: content leaked cleartext"

    encrypt_meta, meta_bytes, text = _java_meta(enc, _USER_PW)
    assert encrypt_meta == "false"
    assert meta_bytes == meta_xml
    assert "CryptFilter wave1427 payload" in text


# ----------------------- /EncryptMetadata false: Java → pypdfbox reads (R6)


@requires_oracle
def test_java_encrypts_metadata_off_pypdfbox_reads(tmp_path: Path) -> None:
    """Apache PDFBox emits an R6 /EncryptMetadata=false document (flag flipped
    post-protect — lossless only for R6, see _ENCRYPT_MD_OFF_NOTE). pypdfbox
    reads ``is_encrypt_meta_data()==False``, recovers the text, and returns
    the SAME /Metadata bytes PDFBox does (both honour the flag and leave the
    /Metadata stream untouched on disk → identical bytes)."""
    _fixture_present()
    enc = tmp_path / "java_mdoff_r6.pdf"
    run_probe(
        "CryptFilterProbe",
        "encrypt-md-off",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        "256",
        "false",
    )

    # PDFBox can reopen its own R6 md-off output (key is flag-independent).
    java_meta, java_meta_bytes, java_text = _java_meta(enc, _USER_PW)
    assert java_meta == "false"

    with PDDocument.load(str(enc), password=_USER_PW) as doc:
        py_enc = doc.get_encryption()
        assert py_enc is not None
        assert py_enc.is_encrypt_meta_data() is False
        py_text = PDFTextStripper().get_text(doc)

    # Text recovered on both sides (encrypted content decrypts normally).
    assert py_text.strip() == java_text.strip()
    # Both libraries leave the /Metadata stream byte-identical on read
    # (neither deciphers it because the flag is false).
    assert _py_metadata_bytes(enc, _USER_PW) == java_meta_bytes


# --------------------------------- crypt-filter introspection parity


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes", "expected_cfm"),
    [
        ("aes_128", 128, True, "AESV2"),
        ("aes_256", 256, True, "AESV3"),
    ],
    ids=["aes_128", "aes_256"],
)
def test_crypt_filter_introspection_matches_java(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    expected_cfm: str,
    tmp_path: Path,
) -> None:
    """pypdfbox reads the SAME /StmF, /StrF, /CF (with /CFM) and
    isEncryptMetaData as Apache PDFBox on an AES-encrypted document."""
    _fixture_present()
    enc = tmp_path / f"{algo_id}.pdf"
    run_probe(
        "EncryptProbe",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
    )

    java = _java_introspect(enc, _USER_PW)
    py = _py_introspect(enc, _USER_PW)
    assert py == java, f"{algo_id}: pypdfbox introspection diverges: {py} != {java}"
    # Sanity-pin the absolute values too (so a both-wrong drift can't pass).
    assert py["STMF"] == "StdCF"
    assert py["STRF"] == "StdCF"
    assert py["CF"] == f"StdCF={expected_cfm}"
    assert py["ENCRYPTMETA"] == "true"


# ------------------------------------------- /Identity crypt filter


def test_identity_crypt_filter_resolves_to_passthrough() -> None:
    """A /StmF or /StrF slot pointed at /Identity resolves to the
    pass-through cipher (no enciphering) while a sibling slot pointed at a
    real /CF entry still selects AES.

    Producing a whole-document /Identity round-trip is not expressible via
    either library's 3.0.7 *high-level* API (StandardProtectionPolicy always
    installs a single StdCF for both StmF and StrF), so this pins the
    read-side routing table directly — the surface that decides whether a
    stream/string stays cleartext. Mirrors upstream SecurityHandler's
    ``Identity`` short-circuit (PDF 32000-1 §7.6.5)."""
    enc = PDEncryption()
    enc.set_v(4)
    enc.set_revision(4)
    std = PDCryptFilterDictionary()
    std.set_cfm("AESV2")
    std.set_length(16)
    enc.set_std_crypt_filter_dictionary(std)
    enc.set_stm_f("StdCF")  # streams enciphered with AES
    enc.set_str_f("Identity")  # strings left cleartext

    handler = StandardSecurityHandler(enc)
    handler._populate_routing_table(enc)  # noqa: SLF001 — read-side surface

    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "Identity"
    # /EFF inherits /StmF when absent (spec default §7.6.5).
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_identity_stmf_keeps_streams_cleartext() -> None:
    """When /StmF itself is /Identity, the stream cipher is the pass-through
    — pypdfbox resolves the stream routing slot to /Identity so no AES pass
    is applied to stream bodies (PDF 32000-1 §7.6.5)."""
    enc = PDEncryption()
    enc.set_v(4)
    enc.set_revision(4)
    std = PDCryptFilterDictionary()
    std.set_cfm("AESV2")
    std.set_length(16)
    enc.set_std_crypt_filter_dictionary(std)
    enc.set_stm_f("Identity")  # streams cleartext
    enc.set_str_f("StdCF")  # strings enciphered

    handler = StandardSecurityHandler(enc)
    handler._populate_routing_table(enc)  # noqa: SLF001 — read-side surface

    assert handler.get_stream_cfm() == "Identity"
    assert handler.get_string_cfm() == "AESV2"
