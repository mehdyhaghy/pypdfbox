"""Live Apache PDFBox cross-library encryption interop parity.

The strongest possible parity check for the standard security handler: encrypt
a real PDF with *one* library and decrypt it with the *other*, asserting the
recovered content (page count + extracted text) matches the plaintext original.
Two Java probes drive the oracle side:

* ``EncryptProbe`` — load a plaintext PDF, apply a ``StandardProtectionPolicy``
  (owner + user passwords, default all-allowed permissions) selecting the
  algorithm via ``(keyLengthBits, preferAES)``, and save the encrypted result.
* ``DecryptProbe`` — open a password-encrypted PDF with PDFBox and print
  ``PAGES:<n>`` followed by ``PDFTextStripper`` text (a wrong password makes
  ``Loader.loadPDF`` throw ``InvalidPasswordException`` → non-zero exit).

Algorithm matrix (matches ``compute_revision_number`` in the standard handler):

| key length | preferAES | algorithm | wire V/R                |
|-----------:|-----------|-----------|-------------------------|
| 40         | false     | RC4-40    | V=1/2, R=3, /Length 40  |
| 128        | false     | RC4-128   | V=2,   R=3, /Length 128 |
| 128        | true      | AES-128   | V=4,   R=4              |
| 256        | true      | AES-256   | V=5,   R=6              |

For every algorithm we run BOTH directions (Java→pypdfbox and pypdfbox→Java)
with BOTH the user and the owner password, plus a wrong-password rejection on
each side. The recovered text is byte-compared against the plaintext baseline
PDFBox / pypdfbox extract from the unencrypted fixture, so a silent
mis-decryption (garbage that still "opens") cannot pass.

These tests caught and now guard two real interop bugs fixed in wave 1409:

1. Object-stream members were double-decrypted — pypdfbox attached a per-object
   cipher to objects living *inside* an encrypted ``/Type /ObjStm`` container
   (which the spec leaves cleartext once the container is decrypted), turning
   their FlateDecode bodies to garbage. Fixed in ``PDDocument.decrypt``.
2. The RC4-40 owner-password key-derivation (Algorithm 7) hashed the full
   16-byte MD5 digest in its 50-round loop instead of truncating to the 5-byte
   key length, so a valid owner password was rejected on 40-bit documents.
   Fixed in ``StandardSecurityHandler`` (and the matching /O write path).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    InvalidPasswordException,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "ownerpw"
_USER_PW = "userpw"

# (id, key_length_bits, prefer_aes)
_ALGORITHMS = [
    ("rc4_40", 40, False),
    ("rc4_128", 128, False),
    ("aes_128", 128, True),
    ("aes_256", 256, True),
]


# ----------------------------------------------------------------- helpers


def _plaintext_baseline() -> tuple[int, str]:
    """``(page_count, extracted_text)`` of the unencrypted fixture via
    pypdfbox — the gold value every decrypted variant must reproduce."""
    with PDDocument.load(_FIXTURE) as doc:
        return doc.get_number_of_pages(), PDFTextStripper().get_text(doc)


def _py_extract(path: Path, password: str) -> tuple[int, str]:
    """Open ``path`` with pypdfbox + ``password`` and return (pages, text).

    Uses a ``with`` block so the document (and its source handle) is closed
    before any caller reopens/overwrites — Windows file-lock safety."""
    with PDDocument.load(str(path), password=password) as doc:
        return doc.get_number_of_pages(), PDFTextStripper().get_text(doc)


def _py_encrypt(src: Path, out: Path, key_length: int, prefer_aes: bool) -> None:
    """Encrypt ``src`` to ``out`` via pypdfbox with both passwords set."""
    doc = PDDocument.load(str(src))
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _java_decrypt(path: Path, password: str) -> tuple[int, str]:
    """Run DecryptProbe and parse its ``PAGES:<n>\\n<text>`` framing."""
    raw = run_probe_text("DecryptProbe", str(path), password)
    first, _, rest = raw.partition("\n")
    assert first.startswith("PAGES:"), f"probe framing broke: {first!r}"
    return int(first[len("PAGES:") :]), rest


def _java_decrypt_fails(path: Path, password: str) -> bool:
    """True when DecryptProbe rejects ``password`` (non-zero exit, the
    ``InvalidPasswordException`` PDFBox throws for a bad password)."""
    try:
        run_probe("DecryptProbe", str(path), password)
    except subprocess.CalledProcessError as exc:
        return b"InvalidPasswordException" in (exc.stderr or b"")
    return False


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


# --------------------------------------------------- Java encrypts → py decrypts


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_java_encrypts_pypdfbox_decrypts(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    password: str,
    tmp_path: Path,
) -> None:
    """PDFBox encrypts; pypdfbox opens with the user/owner password and
    recovers byte-identical content to the plaintext original."""
    _fixture_present()
    base_pages, base_text = _plaintext_baseline()

    enc = tmp_path / f"java_{algo_id}.pdf"
    run_probe(
        "EncryptProbe",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
    )
    # The ciphertext must NOT contain the plaintext verbatim — proves the
    # stream bodies were really enciphered by PDFBox.
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    pages, text = _py_extract(enc, password)
    assert pages == base_pages
    assert text == base_text


# --------------------------------------------------- py encrypts → Java decrypts


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_pypdfbox_encrypts_java_decrypts(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    password: str,
    tmp_path: Path,
) -> None:
    """pypdfbox encrypts; Apache PDFBox opens with the user/owner password
    and recovers the same page count + text as the plaintext baseline."""
    _fixture_present()
    # Baseline via the Java side so we compare PDFBox-extracted text to
    # PDFBox-extracted text (its stripper spacing differs subtly from ours).
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, key_length, prefer_aes)
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    pages, text = _java_decrypt(enc, password)
    assert pages == 2
    assert text == base_text


# ------------------------------------------------------- wrong-password handling


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_pypdfbox_rejects_wrong_password_on_java_encrypted_file(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """A Java-encrypted file opened by pypdfbox with the wrong password
    raises ``InvalidPasswordException`` for every algorithm."""
    _fixture_present()
    enc = tmp_path / f"java_{algo_id}.pdf"
    run_probe(
        "EncryptProbe",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
    )
    with pytest.raises(InvalidPasswordException):
        _py_extract(enc, "definitely-wrong")


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_java_rejects_wrong_password_on_pypdfbox_encrypted_file(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """A pypdfbox-encrypted file opened by Apache PDFBox with the wrong
    password is rejected (InvalidPasswordException) for every algorithm."""
    _fixture_present()
    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, key_length, prefer_aes)
    assert _java_decrypt_fails(enc, "definitely-wrong")


# ------------------------------------------------------------ full round-trip


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_double_hop_java_to_py_to_java_preserves_content(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """End-to-end: Java encrypts → pypdfbox decrypts-and-re-encrypts →
    Java decrypts again, recovering the original text. Exercises both the
    read AND write halves of pypdfbox's standard handler in one chain.

    Wave 1418: the writer now forces the lazy stream-body decrypt before
    re-enciphering on save (COSStream.ensure_decrypted +
    COSWriter.visit_from_stream), so the double-hop no longer double-
    enciphers stream bodies."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    # Hop 1: Java encrypts.
    hop1 = tmp_path / f"hop1_{algo_id}.pdf"
    run_probe(
        "EncryptProbe",
        str(_FIXTURE),
        str(hop1),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
    )

    # Hop 2: pypdfbox opens (user pw), re-protects, re-saves.
    hop2 = tmp_path / f"hop2_{algo_id}.pdf"
    doc = PDDocument.load(str(hop1), password=_USER_PW)
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        doc.save(str(hop2))
    finally:
        doc.close()

    # Hop 3: Java opens the pypdfbox-re-encrypted file.
    pages, text = _java_decrypt(hop2, _USER_PW)
    assert pages == 2
    assert text == base_text


# ------------------------------------------- pypdfbox-only re-encrypt round-trip


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_load_encrypted_resave_encrypted_roundtrip_pypdfbox(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """pypdfbox-only double hop: Java encrypts → pypdfbox loads, re-protects,
    re-saves → pypdfbox loads the re-encrypted file and recovers the original
    content. Guards the wave-1418 decrypt-on-write fix without involving the
    Java decrypt side, so a regression surfaces even if the oracle JAR is the
    only thing that drifts."""
    _fixture_present()
    base_pages, base_text = _plaintext_baseline()

    enc = tmp_path / f"src_{algo_id}.pdf"
    run_probe(
        "EncryptProbe",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
    )

    resaved = tmp_path / f"resaved_{algo_id}.pdf"
    doc = PDDocument.load(str(enc), password=_USER_PW)
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        doc.save(str(resaved))
    finally:
        doc.close()

    # The re-encrypted file must not leak the plaintext verbatim.
    assert base_text[:40].encode("latin-1", "ignore") not in resaved.read_bytes()

    pages, text = _py_extract(resaved, _USER_PW)
    assert pages == base_pages
    assert text == base_text
