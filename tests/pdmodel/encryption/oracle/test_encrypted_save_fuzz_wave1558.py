"""Live Apache PDFBox differential fuzz for the encrypted COSWriter save path.

Wave 1558. Where ``test_protect_save_oracle`` pins two key-length families and
``test_encryption_interop_oracle`` exercises the Java↔pypdfbox cross-decrypt
matrix on a fixed fixture, this module fans the ``protect()`` + ``save()`` write
path across a ~20-cell configuration grid and asserts the *shape* of the
on-the-wire ``/Encrypt`` dictionary plus the round-trip facts that the live
PDFBox 3.0.7 oracle reports when it reloads the pypdfbox-produced bytes:

* the cipher family wire constants — ``/V`` / ``/R`` / ``/Length`` and, for
  V>=4, ``/StmF`` = ``/StrF`` = ``StdCF`` with the StdCF ``/CFM`` —
  (RC4-40 → V1/R3, RC4-128 → V2/R3, AES-128 → V4/R4/AESV2,
  AES-256 → V5/R6/AESV3);
* the ``/U`` / ``/O`` presence for every revision and the ``/UE`` / ``/OE``
  key-wrap entries for r5/r6 only;
* the propagated ``/EncryptMetadata`` flag (default True; False emitted only
  when the policy asks for cleartext metadata);
* a decrypted ``/Info /Title`` containing literal-string delimiters
  (``(`` ``)`` ``\\``) so the write-side string-escaping + per-object string
  encryption path is exercised, not just stream encryption;
* the decrypted page text (stream encryption); and
* the ``AccessPermission`` bits PDFBox reconstructs from the decrypted ``/P``
  (all-allowed vs all-denied), authenticating with both the user and the
  owner password.

Every config is also self-round-tripped through pypdfbox's own reader and
checked for plaintext leakage (the title/body must not survive verbatim in the
ciphertext), so a regression surfaces even when the oracle JAR is absent.

Compares structural + round-trip facts only — never exact ciphertext bytes,
which differ on every save (random salt / IV / file key for r6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

# A page-content stream (exercises stream encryption) and a /Info /Title with
# literal-string delimiters (exercises write-side string escaping + per-object
# string encryption). The backslash + balanced/unbalanced parens force the
# COSString writer through its escaping branches before the bytes are
# enciphered.
_BODY_MARKER = "Encrypted save fuzz body w1558"
_CONTENT = f"BT /F1 12 Tf 50 700 Td ({_BODY_MARKER}) Tj ET".encode("latin-1")
_TITLE = r"Ti(tle) \with\ esc \\ and )paren( w1558"

_OWNER_PW = "0wn3r-pass"
_USER_PW = "us3r-pass"


def _build_protected(
    path: Path,
    *,
    key_length: int,
    prefer_aes: bool,
    owner_password: str,
    user_password: str,
    encrypt_metadata: bool,
    all_clear: bool,
) -> None:
    """Build a one-page PDF with a delimiter-laden title, ``protect()`` it
    under the given configuration, and ``save()`` to ``path``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT)
        page.set_contents(stream)
        doc.get_document_information().set_title(_TITLE)

        ap = AccessPermission()
        if all_clear:
            ap.set_can_print(False)
            ap.set_can_modify(False)
            ap.set_can_extract_content(False)
            ap.set_can_modify_annotations(False)
            ap.set_can_fill_in_form(False)
            ap.set_can_extract_for_accessibility(False)
            ap.set_can_assemble_document(False)
            ap.set_can_print_faithful(False)

        policy = StandardProtectionPolicy(
            owner_password=owner_password,
            user_password=user_password,
            permissions=ap,
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        policy.set_encrypt_metadata(encrypt_metadata)
        doc.protect(policy)
        doc.save(path)
    finally:
        doc.close()


def _py_reload(path: Path, password: str) -> tuple[str | None, str]:
    """Open ``path`` with pypdfbox + ``password``; return (title, page_text).

    ``with`` block closes the source handle before any caller overwrites —
    Windows file-lock safety per CLAUDE.md."""
    with PDDocument.load(str(path), password=password) as doc:
        title = doc.get_document_information().get_title()
        text = PDFTextStripper().get_text(doc)
        return title, text


# (id, key_length, prefer_aes, exp_version, exp_revision, exp_cfm,
#  exp_stm_f, exp_has_ue)
_FAMILIES = [
    ("rc4_40", 40, False, 1, 3, None, None, False),
    ("rc4_128", 128, False, 2, 3, None, None, False),
    ("aes_128", 128, True, 4, 4, "AESV2", "StdCF", False),
    ("aes_256", 256, False, 5, 6, "AESV3", "StdCF", True),
]


# ----------------------------------------------------- full-config wire shape


@requires_oracle
@pytest.mark.parametrize(
    (
        "algo_id",
        "key_length",
        "prefer_aes",
        "exp_version",
        "exp_revision",
        "exp_cfm",
        "exp_stm_f",
        "exp_has_ue",
    ),
    _FAMILIES,
    ids=[a[0] for a in _FAMILIES],
)
@pytest.mark.parametrize("encrypt_metadata", [True, False], ids=["meta", "nometa"])
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_protect_save_wire_shape_matches_pdfbox(
    tmp_path: Path,
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    exp_version: int,
    exp_revision: int,
    exp_cfm: str | None,
    exp_stm_f: str | None,
    exp_has_ue: bool,
    encrypt_metadata: bool,
    password: str,
) -> None:
    """Every cipher family × /EncryptMetadata × {user,owner} password reloads
    in PDFBox with the spec /Encrypt shape and decrypts to the original title
    + body."""
    out = tmp_path / f"{algo_id}_{encrypt_metadata}.pdf"
    _build_protected(
        out,
        key_length=key_length,
        prefer_aes=prefer_aes,
        owner_password=_OWNER_PW,
        user_password=_USER_PW,
        encrypt_metadata=encrypt_metadata,
        all_clear=False,
    )

    probe = json.loads(run_probe_text("EncryptedSaveFuzzProbe", str(out), password))
    assert probe.get("opened") is True, probe
    assert probe["isEncrypted"] is True
    assert probe["pages"] == 1

    # /Encrypt wire shape per cipher family.
    assert probe["version"] == exp_version
    assert probe["revision"] == exp_revision
    assert probe["length"] == key_length
    assert probe["hasU"] is True
    assert probe["hasO"] is True
    assert probe["hasUE"] is exp_has_ue
    assert probe["hasOE"] is exp_has_ue
    assert probe["stmF"] == exp_stm_f
    assert probe["strF"] == exp_stm_f
    assert probe["cfm"] == exp_cfm

    # /EncryptMetadata propagation (default True; only emitted False when asked).
    assert probe["encryptMetadata"] is encrypt_metadata

    # Decrypted string (escaped + per-object encrypted) + decrypted stream body.
    assert probe["title"] == _TITLE, f"title divergence: {probe['title']!r}"
    assert _BODY_MARKER in probe["text"], f"body divergence: {probe['text']!r}"


# ----------------------------------------------------- permission reconstruction


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    [(f[0], f[1], f[2]) for f in _FAMILIES],
    ids=[a[0] for a in _FAMILIES],
)
def test_protect_save_permissions_roundtrip(
    tmp_path: Path, algo_id: str, key_length: int, prefer_aes: bool
) -> None:
    """All-denied AccessPermission round-trips through /P to PDFBox under the
    user-password view; the owner password unlocks everything upstream."""
    out = tmp_path / f"{algo_id}_clear.pdf"
    _build_protected(
        out,
        key_length=key_length,
        prefer_aes=prefer_aes,
        owner_password=_OWNER_PW,
        user_password=_USER_PW,
        encrypt_metadata=True,
        all_clear=True,
    )

    user_view = json.loads(
        run_probe_text("EncryptedSaveFuzzProbe", str(out), _USER_PW)
    )
    assert user_view.get("opened") is True, user_view
    assert user_view["canPrint"] is False
    assert user_view["canModify"] is False
    assert user_view["canExtract"] is False

    owner_view = json.loads(
        run_probe_text("EncryptedSaveFuzzProbe", str(out), _OWNER_PW)
    )
    assert owner_view.get("opened") is True, owner_view
    assert owner_view["canPrint"] is True
    assert owner_view["canModify"] is True
    assert owner_view["canExtract"] is True


# ----------------------------------------------------- empty / owner-only password


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    [(f[0], f[1], f[2]) for f in _FAMILIES],
    ids=[a[0] for a in _FAMILIES],
)
def test_protect_save_empty_user_password(
    tmp_path: Path, algo_id: str, key_length: int, prefer_aes: bool
) -> None:
    """An owner-protected file with an EMPTY user password opens in PDFBox both
    with no password (empty user) and with the owner password, and decrypts to
    the original content. Mirrors the common 'restrict permissions, no open
    password' protection scheme."""
    out = tmp_path / f"{algo_id}_emptyuser.pdf"
    _build_protected(
        out,
        key_length=key_length,
        prefer_aes=prefer_aes,
        owner_password=_OWNER_PW,
        user_password="",
        encrypt_metadata=True,
        all_clear=False,
    )

    for password in ("", _OWNER_PW):
        probe = json.loads(
            run_probe_text("EncryptedSaveFuzzProbe", str(out), password)
        )
        assert probe.get("opened") is True, (password, probe)
        assert probe["isEncrypted"] is True
        assert probe["title"] == _TITLE
        assert _BODY_MARKER in probe["text"]


# -------------------------------------- oracle-free self round-trip + leak guard


@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    [(f[0], f[1], f[2]) for f in _FAMILIES],
    ids=[a[0] for a in _FAMILIES],
)
@pytest.mark.parametrize("encrypt_metadata", [True, False], ids=["meta", "nometa"])
def test_protect_save_self_roundtrip_no_plaintext_leak(
    tmp_path: Path,
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    encrypt_metadata: bool,
) -> None:
    """pypdfbox reads back its own encrypted bytes (user + owner password) and
    recovers the title + body, while the ciphertext leaks neither verbatim.

    Runs WITHOUT the oracle so a write-path regression surfaces on any machine
    — the JAR-gated tests above add the cross-impl interop confirmation."""
    out = tmp_path / f"{algo_id}_{encrypt_metadata}_self.pdf"
    _build_protected(
        out,
        key_length=key_length,
        prefer_aes=prefer_aes,
        owner_password=_OWNER_PW,
        user_password=_USER_PW,
        encrypt_metadata=encrypt_metadata,
        all_clear=False,
    )

    raw = out.read_bytes()
    assert _TITLE.encode("latin-1") not in raw, "title leaked in ciphertext"
    assert _BODY_MARKER.encode("latin-1") not in raw, "body leaked in ciphertext"

    for password in (_USER_PW, _OWNER_PW):
        title, text = _py_reload(out, password)
        assert title == _TITLE, (password, title)
        assert _BODY_MARKER in text, (password, text)
