"""Live Apache PDFBox cross-library interop for the RC4 standard security
handler — revisions 2 (40-bit) and 3 (128-bit).

The generic ``test_encryption_interop_oracle`` module already round-trips RC4
content (page count + text) in both directions with an all-allowed permission
set. This module pins the parts that module does NOT cover for RC4:

* **On-the-wire field parity** — ``/V``, ``/R``, ``/Length`` and the ``/P``
  permission integer a reader sees. RC4 is deterministic, so a Java reader
  opening a pypdfbox-encrypted file must report the *exact* same revision /
  key length / permission bits PDFBox would have written itself.
* **Restrictive permission set** — a deny-modify / deny-extract / deny-annotate
  / deny-assemble profile (keeping print + form-fill + accessibility), proving
  ``/P`` survives an RC4 round trip in both directions.
* **Owner-only protection (empty user password)** — a legal but rarely tested
  configuration: the document opens with *no* password and inherits the policy;
  the owner password unlocks owner permissions.

The probe ``oracle/probes/Rc4InteropProbe.java`` drives the oracle:

* ``encrypt <in> <out> <ownerPw> <userPw> <keyBits> <restrict>`` — apply a
  ``StandardProtectionPolicy`` at RC4 ``keyBits`` (40→R2-eligible, 128→R3),
  optionally restrictive, empty ``userPw`` ⇒ owner-only. ``preferAES`` is
  always false (pure RC4).
* ``inspect <in> <password>`` — open and print ``V:``/``R:``/``LENGTH:``/``P:``/
  ``PAGES:`` lines followed by ``TEXT:<stripped text>``.

Revision note (PDF 32000-1 + PDFBox ``computeRevisionNumber``): a 40-bit
(``/V 1``) document is written at **R3** whenever any revision-3 permission bit
(fill-in-form / extract-for-accessibility / assemble / print-faithful) is set,
and at **R2** only when none are. The default ``AccessPermission()`` sets all
four, so a plain 40-bit protect is R3 in both libraries; clearing those four
bits drops it to R2. Wave 1434 fixed pypdfbox's ``prepare_document``, which
previously hardcoded R2 for every 40-bit document regardless of permissions.
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

# (id, key_length_bits, expected wire revision for the DEFAULT all-allowed perms)
_RC4 = [
    ("rc4_40", 40, 3),  # /V 1; default perms set rev-3 bits ⇒ R3
    ("rc4_128", 128, 3),  # /V 2; always R3
]


# ----------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _restrictive() -> AccessPermission:
    """Deny modify / extract / annotate / assemble; keep print + form-fill +
    accessibility + faithful-print. Keeps revision-3 bits set (so R3)."""
    p = AccessPermission()
    p.set_can_modify(False)
    p.set_can_extract_content(False)
    p.set_can_modify_annotations(False)
    p.set_can_assemble_document(False)
    p.set_can_print(True)
    p.set_can_fill_in_form(True)
    p.set_can_extract_for_accessibility(True)
    p.set_can_print_faithful(True)
    return p


def _py_extract(path: Path, password: str) -> tuple[int, str]:
    with PDDocument.load(str(path), password=password) as doc:
        return doc.get_number_of_pages(), PDFTextStripper().get_text(doc)


def _py_encrypt(
    src: Path,
    out: Path,
    key_length: int,
    *,
    owner_pw: str = _OWNER_PW,
    user_pw: str = _USER_PW,
    perms: AccessPermission | None = None,
) -> None:
    doc = PDDocument.load(str(src))
    try:
        policy = StandardProtectionPolicy(
            owner_password=owner_pw,
            user_password=user_pw,
            permissions=perms if perms is not None else AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(False)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _java_encrypt(
    out: Path,
    key_length: int,
    *,
    owner_pw: str = _OWNER_PW,
    user_pw: str = _USER_PW,
    restrict: bool = False,
) -> None:
    run_probe(
        "Rc4InteropProbe",
        "encrypt",
        str(_FIXTURE),
        str(out),
        owner_pw,
        user_pw,
        str(key_length),
        "true" if restrict else "false",
    )


def _java_inspect(path: Path, password: str) -> tuple[dict[str, int], str]:
    """Run Rc4InteropProbe inspect → ({V,R,LENGTH,P,PAGES}, text)."""
    raw = run_probe_text("Rc4InteropProbe", "inspect", str(path), password)
    head, _, text = raw.partition("TEXT:")
    fields: dict[str, int] = {}
    for line in head.splitlines():
        if ":" in line:
            name, _, value = line.partition(":")
            fields[name] = int(value)
    return fields, text


def _java_decrypt_fails(path: Path, password: str) -> bool:
    try:
        run_probe("Rc4InteropProbe", "inspect", str(path), password)
    except subprocess.CalledProcessError as exc:
        return b"InvalidPasswordException" in (exc.stderr or b"")
    return False


# ----------------------------------------------- Java encrypts → pypdfbox reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_java_rc4_pypdfbox_decrypts_default(
    algo_id: str, key_length: int, _exp_rev: int, password: str, tmp_path: Path
) -> None:
    """PDFBox encrypts RC4 (default perms); pypdfbox recovers byte-identical
    content with the user / owner password."""
    _fixture_present()
    base_pages, base_text = _py_extract(_FIXTURE, "")  # plaintext fixture

    enc = tmp_path / f"j_{algo_id}.pdf"
    _java_encrypt(enc, key_length)
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    pages, text = _py_extract(enc, password)
    assert pages == base_pages
    assert text == base_text


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
def test_java_rc4_restrictive_pypdfbox_reads_permissions(
    algo_id: str, key_length: int, _exp_rev: int, tmp_path: Path
) -> None:
    """PDFBox encrypts RC4 with a restrictive permission set; pypdfbox reads
    back the same /P bits under the user password."""
    _fixture_present()
    enc = tmp_path / f"jr_{algo_id}.pdf"
    _java_encrypt(enc, key_length, restrict=True)

    with PDDocument.load(str(enc), password=_USER_PW) as doc:
        ap = doc.get_current_access_permission()
        # The restriction profile, as the user sees it.
        assert ap.can_print() is True
        assert ap.can_fill_in_form() is True
        assert ap.can_extract_for_accessibility() is True
        assert ap.can_print_faithful() is True
        assert ap.can_modify() is False
        assert ap.can_extract_content() is False
        assert ap.can_modify_annotations() is False
        assert ap.can_assemble_document() is False


# ----------------------------------------------- pypdfbox encrypts → Java reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_pypdfbox_rc4_java_decrypts_default(
    algo_id: str, key_length: int, exp_rev: int, password: str, tmp_path: Path
) -> None:
    """pypdfbox encrypts RC4 (default perms); PDFBox recovers the content AND
    reports the exact /V, /R, /Length PDFBox itself would write."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    enc = tmp_path / f"p_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, key_length)
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    fields, text = _java_inspect(enc, password)
    assert fields["PAGES"] == 2
    assert text == base_text
    # Wire-field parity — RC4 is deterministic; these must match PDFBox.
    assert fields["LENGTH"] == key_length
    assert fields["R"] == exp_rev
    assert fields["V"] == (1 if key_length == 40 else 2)


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
def test_pypdfbox_rc4_restrictive_java_reads_permissions(
    algo_id: str, key_length: int, _exp_rev: int, tmp_path: Path
) -> None:
    """pypdfbox encrypts RC4 with a restrictive permission set; PDFBox reads
    back the same /P integer pypdfbox wrote (proves /P round-trips)."""
    _fixture_present()
    perms = _restrictive()
    expected_p = perms.get_permission_bytes()

    enc = tmp_path / f"pr_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, key_length, perms=perms)

    fields, _ = _java_inspect(enc, _USER_PW)
    assert fields["P"] == expected_p
    assert fields["PAGES"] == 2


@requires_oracle
def test_pypdfbox_rc4_40_revision_matches_pdfbox(tmp_path: Path) -> None:
    """The 40-bit revision pypdfbox writes equals what PDFBox writes for the
    same permission set: R3 with default (rev-3) perms, R2 when every
    revision-3 bit is cleared. Guards the wave-1434 prepare_document fix."""
    _fixture_present()

    # Default perms ⇒ R3 (rev-3 bits set).
    enc_default = tmp_path / "rev_default.pdf"
    _py_encrypt(_FIXTURE, enc_default, 40)
    fields_default, _ = _java_inspect(enc_default, _USER_PW)
    assert fields_default["V"] == 1
    assert fields_default["R"] == 3

    # No revision-3 bits ⇒ R2.
    no_rev3 = AccessPermission()
    no_rev3.set_can_fill_in_form(False)
    no_rev3.set_can_extract_for_accessibility(False)
    no_rev3.set_can_assemble_document(False)
    no_rev3.set_can_print_faithful(False)
    enc_r2 = tmp_path / "rev_r2.pdf"
    _py_encrypt(_FIXTURE, enc_r2, 40, perms=no_rev3)
    fields_r2, _ = _java_inspect(enc_r2, _USER_PW)
    assert fields_r2["V"] == 1
    assert fields_r2["R"] == 2


# --------------------------------------------- owner-only (empty user password)


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
def test_java_rc4_owner_only_pypdfbox_opens_no_password(
    algo_id: str, key_length: int, _exp_rev: int, tmp_path: Path
) -> None:
    """PDFBox encrypts RC4 owner-only (empty user password); pypdfbox opens it
    with no password AND with the owner password, recovering the content."""
    _fixture_present()
    base_pages, base_text = _py_extract(_FIXTURE, "")

    enc = tmp_path / f"jowner_{algo_id}.pdf"
    _java_encrypt(enc, key_length, user_pw="")
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    # Empty user password (the default user view).
    pages_u, text_u = _py_extract(enc, "")
    assert pages_u == base_pages
    assert text_u == base_text

    # Owner password unlocks the same content.
    pages_o, text_o = _py_extract(enc, _OWNER_PW)
    assert pages_o == base_pages
    assert text_o == base_text


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
def test_pypdfbox_rc4_owner_only_java_opens_no_password(
    algo_id: str, key_length: int, _exp_rev: int, tmp_path: Path
) -> None:
    """pypdfbox encrypts RC4 owner-only (empty user password); PDFBox opens it
    with no password AND with the owner password."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    enc = tmp_path / f"powner_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, key_length, user_pw="")
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    fields_u, text_u = _java_inspect(enc, "")
    assert fields_u["PAGES"] == 2
    assert text_u == base_text

    fields_o, text_o = _java_inspect(enc, _OWNER_PW)
    assert fields_o["PAGES"] == 2
    assert text_o == base_text


# ------------------------------------------------------- wrong-password handling


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
def test_pypdfbox_rejects_wrong_password_on_java_rc4(
    algo_id: str, key_length: int, _exp_rev: int, tmp_path: Path
) -> None:
    """A Java-encrypted RC4 file opened by pypdfbox with the wrong password is
    rejected."""
    _fixture_present()
    enc = tmp_path / f"jwrong_{algo_id}.pdf"
    _java_encrypt(enc, key_length)
    with pytest.raises(InvalidPasswordException):
        _py_extract(enc, "definitely-wrong")


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "_exp_rev"), _RC4, ids=[a[0] for a in _RC4]
)
def test_java_rejects_wrong_password_on_pypdfbox_rc4(
    algo_id: str, key_length: int, _exp_rev: int, tmp_path: Path
) -> None:
    """A pypdfbox-encrypted RC4 file opened by PDFBox with the wrong password
    is rejected (InvalidPasswordException → non-zero exit)."""
    _fixture_present()
    enc = tmp_path / f"pwrong_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, key_length)
    assert _java_decrypt_fails(enc, "definitely-wrong")
