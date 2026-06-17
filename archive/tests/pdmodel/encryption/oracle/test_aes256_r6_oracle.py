"""Live Apache PDFBox cross-library parity for the AES-256 (V5/R6) standard
security handler — the *deep* facets a basic content round-trip
(``test_encryption_interop_oracle.py``, which already covers Java↔pypdfbox
content recovery + wrong-password rejection for all four algorithms) does not
reach:

* The **/Perms permission-validation block** (PDF 32000-2 §7.6.4.4.9 /
  algorithm 13). R6 stores the permission integer a second time, AES-256-ECB
  encrypted under the file key, so a reader can detect a tampered /P. This
  suite proves pypdfbox writes a /Perms PDFBox honors (restrictive perms
  survive the trip and PDFBox decodes the same bits) AND that pypdfbox
  validates / reads back the /Perms PDFBox writes.
* The **owner-only open** path: a file whose owner and user passwords differ,
  opened with each, must grant the owner full permissions and the user the
  restricted /P set on BOTH libraries.
* The **R6 Algorithm 2.B hardened hash with a multi-byte / Unicode password**,
  including a SASLprep-divergent password (a compatibility character such as
  the ``ﬀ`` ligature U+FB00 that NFKC maps to ``ff``). PDFBox applies
  ``SaslPrep.saslPrepQuery`` (read) / ``saslPrepStored`` (write) before
  UTF-8-encoding an R6 password; pypdfbox must do the same or the file is
  mutually unopenable. Wave 1435 added that SaslPrep step — these tests guard
  it in both directions.

Probe: ``Aes256R6Probe`` — ``encrypt`` (PDFBox writes V5/R6 with a /P-derived
``AccessPermission`` + the /Perms block) and ``inspect`` (PDFBox opens a
V5/R6 file and emits ``V/R/LENGTH/OWNER_AUTH/PERMS_INT`` + each permission
predicate + ``PAGES`` + ``TEXT``). A wrong password makes PDFBox throw
``InvalidPasswordException`` (non-zero exit), asserted via the framing helper.
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

_OWNER_PW = "owner-pw-256"
_USER_PW = "user-pw-256"

# A restrictive /P: printing, modification, content-extraction, form-fill,
# assembly all DENIED (only the always-set high reserved bits remain). The
# all-allowed default is -4; this clears the permission bits a user shouldn't
# get. Owner authentication overrides /P entirely (full permissions).
_RESTRICTIVE_P = -3904

# --------------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _py_encrypt_r6(
    out: Path, owner_pw: str, user_pw: str, p_int: int
) -> None:
    """Encrypt the fixture at AES-256 (V5/R6) via pypdfbox."""
    doc = PDDocument.load(str(_FIXTURE))
    try:
        policy = StandardProtectionPolicy(
            owner_password=owner_pw,
            user_password=user_pw,
            permissions=AccessPermission(p_int),
        )
        policy.set_encryption_key_length(256)
        policy.set_prefer_aes(True)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _java_encrypt_r6(
    out: Path, owner_pw: str, user_pw: str, p_int: int
) -> None:
    run_probe(
        "Aes256R6Probe",
        "encrypt",
        str(_FIXTURE),
        str(out),
        owner_pw,
        user_pw,
        str(p_int),
    )


def _java_inspect(path: Path, password: str) -> dict[str, str]:
    """Run ``Aes256R6Probe inspect`` and parse its framed report into a dict
    (TEXT captured under the ``TEXT`` key as the full remaining body)."""
    raw = run_probe_text("Aes256R6Probe", "inspect", str(path), password)
    fields: dict[str, str] = {}
    head, sep, text = raw.partition("TEXT:")
    for line in head.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key] = val
    if sep:
        fields["TEXT"] = text
    return fields


def _java_inspect_fails(path: Path, password: str) -> bool:
    try:
        run_probe("Aes256R6Probe", "inspect", str(path), password)
    except subprocess.CalledProcessError as exc:
        return b"InvalidPasswordException" in (exc.stderr or b"")
    return False


def _py_open(path: Path, password: str) -> tuple[int, str, AccessPermission]:
    with PDDocument.load(str(path), password=password) as doc:
        return (
            doc.get_number_of_pages(),
            PDFTextStripper().get_text(doc),
            doc.get_current_access_permission(),
        )


# ============================================================ /Perms parity


@requires_oracle
def test_pypdfbox_perms_block_validates_in_pdfbox(tmp_path: Path) -> None:
    """pypdfbox writes the AES-256 /Perms block; PDFBox opens the file with
    the USER password and decodes exactly the restrictive /P pypdfbox set
    (PDFBox validates /Perms internally on load — a /Perms that fails to
    decrypt-and-match would make it fall back / warn). The user must NOT be an
    owner and must NOT be able to print/modify."""
    _fixture_present()
    enc = tmp_path / "py_r6_restrictive.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)

    f = _java_inspect(enc, _USER_PW)
    assert f["V"] == "5"
    assert f["R"] == "6"
    assert f["LENGTH"] == "256"
    assert f["OWNER_AUTH"] == "false"
    # The /P PDFBox decodes from the user-authenticated file is the exact
    # restrictive integer pypdfbox stored — proves the /P round-trips and the
    # /Perms block PDFBox checked did not force a fallback to a different value.
    assert int(f["PERMS_INT"]) == _RESTRICTIVE_P
    assert f["CAN_PRINT"] == "false"
    assert f["CAN_MODIFY"] == "false"
    assert f["CAN_EXTRACT"] == "false"
    assert f["PAGES"] == "2"


@requires_oracle
def test_pypdfbox_reads_and_validates_pdfbox_perms_block(tmp_path: Path) -> None:
    """PDFBox writes the AES-256 /Perms block; pypdfbox opens with the USER
    password, recovers content, and decodes the restrictive /P. pypdfbox runs
    algorithm 13 (``_validate_perms_r5_r6``) on load; a successful restricted
    open proves the /Perms it decrypted matched the dictionary /P."""
    _fixture_present()
    enc = tmp_path / "java_r6_restrictive.pdf"
    _java_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    pages, text, ap = _py_open(enc, _USER_PW)
    assert pages == 2
    assert text == base_text
    assert ap.get_permission_bytes() == _RESTRICTIVE_P
    assert not ap.is_owner_permission()
    assert not ap.can_print()
    assert not ap.can_modify()
    assert not ap.can_extract_content()


@requires_oracle
def test_pypdfbox_detects_tampered_perms_block(tmp_path: Path) -> None:
    """Algorithm 13 is a validator: corrupt the encrypted /Perms block in a
    pypdfbox-written file and pypdfbox must still open (PDFBox-parity: a bad
    /Perms only logs a warning and falls back to the dictionary /P, it does
    not reject the password). Proves the validator is *wired*, not that it
    hard-fails (which would diverge from upstream)."""
    _fixture_present()
    enc = tmp_path / "py_r6_tamper.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)

    # pypdfbox serialises /Perms as a hex string: ``/Perms <CBE3...>``. To
    # corrupt the encrypted AES block while keeping the COS hex string valid
    # (so parsing still reaches algorithm 13 rather than failing earlier), swap
    # ONE hex digit inside the angle-bracketed value for a different hex digit.
    raw = bytearray(enc.read_bytes())
    idx = raw.find(b"/Perms")
    assert idx != -1, "no /Perms entry written"
    lt = raw.index(b"<", idx)  # opening angle bracket of the hex value
    # First hex digit of the value; flip it to a guaranteed-different digit.
    digit_pos = lt + 1
    raw[digit_pos] = ord("F") if raw[digit_pos] != ord("F") else ord("0")
    tampered = tmp_path / "py_r6_tampered.pdf"
    tampered.write_bytes(bytes(raw))

    # Opening still succeeds (password is valid; /Perms only validates /P) and
    # the dictionary /P is honored.
    pages, _text, ap = _py_open(tampered, _USER_PW)
    assert pages == 2
    assert ap.get_permission_bytes() == _RESTRICTIVE_P


# ===================================================== owner-only open parity


@requires_oracle
@pytest.mark.parametrize(
    ("opener", "expect_owner"),
    [(_USER_PW, False), (_OWNER_PW, True)],
    ids=["user", "owner"],
)
def test_pypdfbox_encrypts_distinct_passwords_pdfbox_opens(
    opener: str, expect_owner: bool, tmp_path: Path
) -> None:
    """pypdfbox encrypts with DISTINCT owner/user passwords + restrictive /P.
    PDFBox opening with the user password is restricted (not owner); opening
    with the owner password is granted full permissions."""
    _fixture_present()
    enc = tmp_path / "py_r6_distinct.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)

    f = _java_inspect(enc, opener)
    assert f["PAGES"] == "2"
    assert (f["OWNER_AUTH"] == "true") is expect_owner
    if expect_owner:
        assert f["CAN_PRINT"] == "true"
        assert f["CAN_MODIFY"] == "true"
    else:
        assert f["CAN_PRINT"] == "false"
        assert f["CAN_MODIFY"] == "false"


@requires_oracle
@pytest.mark.parametrize(
    ("opener", "expect_owner"),
    [(_USER_PW, False), (_OWNER_PW, True)],
    ids=["user", "owner"],
)
def test_pdfbox_encrypts_distinct_passwords_pypdfbox_opens(
    opener: str, expect_owner: bool, tmp_path: Path
) -> None:
    """PDFBox encrypts with DISTINCT owner/user passwords + restrictive /P.
    pypdfbox opening with the user password is restricted; with the owner
    password it gets the owner all-permissions set (the R6 owner-key path,
    /OE recovery, must work)."""
    _fixture_present()
    enc = tmp_path / "java_r6_distinct.pdf"
    _java_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    pages, text, ap = _py_open(enc, opener)
    assert pages == 2
    assert text == base_text
    assert ap.is_owner_permission() is expect_owner
    if expect_owner:
        assert ap.can_print()
        assert ap.can_modify()
    else:
        assert not ap.can_print()
        assert not ap.can_modify()


@requires_oracle
def test_owner_password_recovers_file_key_via_oe(tmp_path: Path) -> None:
    """Owner-only open is the /O /OE key-recovery path (R6 algorithm 2.A on the
    owner-validation salt, then AES-CBC-unwrap of /OE). Encrypt with pypdfbox,
    open with ONLY the owner password (user password not supplied), and prove
    content recovery — exercises owner-side 2.B hash + /OE unwrap independent
    of the user path."""
    _fixture_present()
    enc = tmp_path / "py_r6_owner_only.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)
    base_pages, base_text, _ = _py_open(enc, _OWNER_PW)
    # Java side as a second oracle on the same /OE recovery.
    f = _java_inspect(enc, _OWNER_PW)
    assert f["OWNER_AUTH"] == "true"
    assert int(f["PAGES"]) == base_pages
    assert base_pages == 2
    assert base_text  # non-empty recovery


# =============================== R6 2.B hardened hash — multi-byte passwords


# Plain multi-byte (NFKC-stable) password — SaslPrep is a no-op, so raw UTF-8
# and SaslPrep'd UTF-8 coincide. Guards the 2.B hash + UTF-8 encoding only.
_UNICODE_PW = "pä55-wörd-密码-Ω"
# SASLprep-divergent password: U+FB00 (ﬀ ligature) NFKC-maps to "ff". Raw UTF-8
# of the ligature differs from the SaslPrep'd ("offfice") UTF-8 — only matches
# PDFBox if SaslPrep is applied on both sides.
_SASLPREP_PW = "oﬀice-pass"
_SASLPREP_NORMALIZED = "office-pass"


@requires_oracle
@pytest.mark.parametrize(
    "password",
    [_UNICODE_PW, _SASLPREP_PW],
    ids=["nfkc_stable", "saslprep_ligature"],
)
def test_unicode_password_pypdfbox_to_pdfbox(password: str, tmp_path: Path) -> None:
    """pypdfbox encrypts at R6 with a multi-byte user password; PDFBox opens
    with the SAME literal password. For the SASLprep-divergent case this only
    works if pypdfbox applied ``saslPrepStored`` on write (otherwise PDFBox's
    ``saslPrepQuery`` on read produces different bytes and rejects the pw)."""
    _fixture_present()
    enc = tmp_path / "py_r6_unicode.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, password, _RESTRICTIVE_P)

    f = _java_inspect(enc, password)
    assert f["V"] == "5"
    assert f["R"] == "6"
    assert f["PAGES"] == "2"


@requires_oracle
def test_saslprep_normalized_form_opens_pypdfbox_file(tmp_path: Path) -> None:
    """A pypdfbox R6 file written with the ligature password also opens with
    the NFKC-normalized form, because both SaslPrep to the same string — the
    defining property of SASLprep canonicalisation."""
    _fixture_present()
    enc = tmp_path / "py_r6_ligature.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, _SASLPREP_PW, _RESTRICTIVE_P)

    pages_lig, _, _ = _py_open(enc, _SASLPREP_PW)
    pages_norm, _, _ = _py_open(enc, _SASLPREP_NORMALIZED)
    assert pages_lig == pages_norm == 2
    # PDFBox agrees on both forms too.
    assert _java_inspect(enc, _SASLPREP_PW)["PAGES"] == "2"
    assert _java_inspect(enc, _SASLPREP_NORMALIZED)["PAGES"] == "2"


@requires_oracle
@pytest.mark.parametrize(
    "password",
    [_UNICODE_PW, _SASLPREP_PW],
    ids=["nfkc_stable", "saslprep_ligature"],
)
def test_unicode_password_pdfbox_to_pypdfbox(password: str, tmp_path: Path) -> None:
    """PDFBox encrypts at R6 with a multi-byte user password; pypdfbox opens
    with the SAME literal password. For the ligature this only works if
    pypdfbox applies ``saslPrepQuery`` on read (PDFBox stored the hash of the
    SaslPrep'd bytes)."""
    _fixture_present()
    enc = tmp_path / "java_r6_unicode.pdf"
    _java_encrypt_r6(enc, _OWNER_PW, password, _RESTRICTIVE_P)
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    pages, text, _ = _py_open(enc, password)
    assert pages == 2
    assert text == base_text


@requires_oracle
def test_pdfbox_ligature_file_opens_with_normalized_in_pypdfbox(
    tmp_path: Path,
) -> None:
    """Cross-check: a PDFBox R6 file written with the ligature password opens
    in pypdfbox with the NFKC-normalized form too (both SaslPrep equal)."""
    _fixture_present()
    enc = tmp_path / "java_r6_ligature.pdf"
    _java_encrypt_r6(enc, _OWNER_PW, _SASLPREP_PW, _RESTRICTIVE_P)

    pages_lig, _, _ = _py_open(enc, _SASLPREP_PW)
    pages_norm, _, _ = _py_open(enc, _SASLPREP_NORMALIZED)
    assert pages_lig == pages_norm == 2


# ---------------------------------------------------- wrong-password rejection


@requires_oracle
def test_pypdfbox_rejects_wrong_password_on_pdfbox_r6_file(tmp_path: Path) -> None:
    _fixture_present()
    enc = tmp_path / "java_r6_wrong.pdf"
    _java_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)
    with pytest.raises(InvalidPasswordException):
        _py_open(enc, "definitely-not-it")


@requires_oracle
def test_pdfbox_rejects_wrong_password_on_pypdfbox_r6_file(tmp_path: Path) -> None:
    _fixture_present()
    enc = tmp_path / "py_r6_wrong.pdf"
    _py_encrypt_r6(enc, _OWNER_PW, _USER_PW, _RESTRICTIVE_P)
    assert _java_inspect_fails(enc, "definitely-not-it")
