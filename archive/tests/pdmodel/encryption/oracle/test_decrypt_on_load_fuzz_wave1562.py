"""Live Apache PDFBox differential fuzz of the DECRYPT-ON-LOAD path of the
``StandardSecurityHandler`` — what a real document open RECOVERS once the
user/owner password authenticates (wave 1562).

Sibling oracle modules cover adjacent facets but NOT this projection:

* ``test_encryption_interop_oracle`` (wave 1409) — page-text round trip across
  the 4 algorithms, both directions.
* ``test_decrypt_data_fuzz_wave1532`` — the raw AES/RC4 cipher dispatch on
  malformed ciphertext (no document open).
* ``test_standard_security_handler_fuzz_wave1524`` — key derivation + auth.
* ``test_encrypt_metadata_wire_oracle`` — the ``/EncryptMetadata`` wire bytes.

This module projects the *high-level decrypt-on-load result*: a decrypted
``/Info /Title`` STRING, the auth ROLE (owner vs user) the open resolved, the
restricted permission bits a user-role open keeps, the first line of decrypted
page TEXT (a stream), an EMPTY user-password open, and a wrong-password
rejection's exception class. The ``DecryptOnLoadFuzzProbe`` builds each
encrypted file with PDFBox's own ``StandardProtectionPolicy`` (verb ``make``)
and re-opens it projecting that tuple (verb ``open``); the Python side opens the
IDENTICAL ciphertext with pypdfbox and the projections are compared line for
line. The pypdfbox-write direction (verb ``open`` on a pypdfbox-encrypted file,
including ``/EncryptMetadata false``) closes the interop loop the other way.

Both sides agree byte-for-byte on every case here; no production bug was found
on the decrypt-on-load path this wave — these tests pin the agreement so a
future regression in per-object key derivation, /Info string decryption, the
owner-vs-user role resolution, or the empty-password open surfaces immediately.

Honest divergence note: with the all-allowed default permission set PDFBox's
``isOwnerPermission()`` returns ``true`` even for a USER-role open (the bit set
is indistinguishable from owner). To make the role observable the restricted
cases disable print (``canPrint=false``) so the user role is provably distinct
from the owner role. pypdfbox mirrors this exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.invalid_password_exception import (
    InvalidPasswordException,
)
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "ownerpw"
_USER_PW = "userpw"

# Mirror the probe's constants so the pypdfbox-build side projects the same
# /Info /Title PDFBox's ``make`` writes (the title is the decrypted-string proof
# for the Java-encrypts direction).
_TITLE = "Confidential © 2026 — decrypt me"

# (id, key_length_bits, prefer_aes) — same matrix as the interop oracle.
_ALGORITHMS = [
    ("rc4_40", 40, False),
    ("rc4_128", 128, False),
    ("aes_128", 128, True),
    ("aes_256", 256, True),
]


# --------------------------------------------------------------------- helpers


def _esc(s: str | None) -> str:
    """Match the probe's ``esc`` so projections compare verbatim."""
    if s is None:
        return "<null>"
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("|", "\\p")
    )


def _py_open_projection(path: Path, password: str) -> str:
    """Open ``path`` with pypdfbox and project the probe's ``open`` grammar.

    Uses a ``with`` block so the document + its source handle close before any
    caller reopens/overwrites the file (Windows file-lock safety)."""
    try:
        with PDDocument.load(str(path), password=password) as doc:
            ap = doc.get_current_access_permission()
            info = doc.get_document_information()
            title = info.get_title() if info is not None else None
            text = PDFTextStripper().get_text(doc) or ""
            first_line = text.splitlines()[0].strip() if text.strip() else ""
            return (
                f"OK|owner={str(ap.is_owner_permission()).lower()}"
                f"|title={_esc(title)}"
                f"|text={_esc(first_line)}"
                f"|canprint={str(ap.can_print()).lower()}"
            )
    except InvalidPasswordException:
        return "ERR:InvalidPasswordException"
    except Exception as exc:  # noqa: BLE001 — project the class for parity
        return "ERR:" + type(exc).__name__


def _java_make(
    out_dir: Path,
    name: str,
    key_length: int,
    prefer_aes: bool,
    owner_pw: str,
    user_pw: str,
    *,
    restrict_print: bool = False,
) -> Path:
    """Build a PDFBox-encrypted file via the probe and return its path."""
    args = [
        "make",
        str(out_dir),
        name,
        str(key_length),
        "true" if prefer_aes else "false",
        owner_pw,
        user_pw,
    ]
    if restrict_print:
        args.append("noprint")
    run_probe("DecryptOnLoadFuzzProbe", *args)
    return out_dir / f"{name}.pdf"


def _java_open_projection(path: Path, password: str) -> str:
    """Run the probe's ``open`` verb and return its single projection line."""
    raw = run_probe_text("DecryptOnLoadFuzzProbe", "open", str(path), password)
    return raw.strip()


def _py_encrypt_fixture(
    out: Path,
    key_length: int,
    prefer_aes: bool,
    owner_pw: str,
    user_pw: str,
    *,
    restrict_print: bool = False,
    encrypt_metadata: bool = True,
) -> None:
    """Encrypt the plaintext fixture with pypdfbox, setting a known /Info /Title.

    Used for the pypdfbox-writes → Java-reads direction (and the
    ``/EncryptMetadata false`` case PDFBox 3.0.7 can't author itself)."""
    doc = PDDocument.load(str(_FIXTURE))
    try:
        doc.get_document_information().set_title(_TITLE)
        perms = AccessPermission()
        if restrict_print:
            perms.set_can_print(False)
        policy = StandardProtectionPolicy(
            owner_password=owner_pw,
            user_password=user_pw,
            permissions=perms,
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        policy.set_encrypt_metadata(encrypt_metadata)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


# =================================================== Java encrypts → both open
# The core cross-impl decrypt-on-load parity: PDFBox authors the ciphertext,
# pypdfbox and PDFBox each open it and must project the SAME recovered tuple.


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
@pytest.mark.parametrize(
    "password", [_USER_PW, _OWNER_PW], ids=["user", "owner"]
)
def test_decrypt_on_load_matches_pdfbox(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    password: str,
    tmp_path: Path,
) -> None:
    """pypdfbox recovers the SAME /Info /Title + first text line + auth role +
    print permission PDFBox does, from a PDFBox-encrypted file, for every
    algorithm with both the user and owner password."""
    _fixture_present()
    enc = _java_make(
        tmp_path, algo_id, key_length, prefer_aes, _OWNER_PW, _USER_PW
    )
    java = _java_open_projection(enc, password)
    py = _py_open_projection(enc, password)
    assert py == java
    # Sanity: the projection really decrypted the title + a stream line.
    assert "title=" + _esc(_TITLE) in java
    assert "text=Hello encrypted world." in java


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_decrypt_on_load_owner_vs_user_role(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """With print restricted, the owner-vs-user ROLE the open resolves is
    observable: the user-role open keeps ``canprint=false`` / ``owner=false``;
    the owner-role open gets ``owner=true`` / ``canprint=true``. pypdfbox's
    role resolution matches PDFBox's for both passwords."""
    _fixture_present()
    enc = _java_make(
        tmp_path,
        algo_id,
        key_length,
        prefer_aes,
        _OWNER_PW,
        _USER_PW,
        restrict_print=True,
    )
    for password in (_USER_PW, _OWNER_PW):
        java = _java_open_projection(enc, password)
        py = _py_open_projection(enc, password)
        assert py == java, f"{algo_id}/{password}: {py!r} != {java!r}"
    # The user role really is restricted and distinct from the owner role.
    user_proj = _java_open_projection(enc, _USER_PW)
    owner_proj = _java_open_projection(enc, _OWNER_PW)
    assert "owner=false" in user_proj and "canprint=false" in user_proj
    assert "owner=true" in owner_proj and "canprint=true" in owner_proj


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_decrypt_on_load_wrong_password(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """A wrong password rejects on load. PDFBox's probe reports
    ``ERR:InvalidPasswordException``; pypdfbox raises
    ``InvalidPasswordException`` (same class name) — the projection lines
    match exactly."""
    _fixture_present()
    enc = _java_make(
        tmp_path, algo_id, key_length, prefer_aes, _OWNER_PW, _USER_PW
    )
    java = _java_open_projection(enc, "definitely-wrong")
    py = _py_open_projection(enc, "definitely-wrong")
    assert java == "ERR:InvalidPasswordException"
    assert py == java


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_decrypt_on_load_empty_user_password(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """An owner-protected file with an EMPTY user password opens with the empty
    string (the common "anyone can read, owner controls perms" pattern). Both
    the empty user password AND the owner password recover the content; pypdfbox
    agrees with PDFBox on the projection for both."""
    _fixture_present()
    enc = _java_make(
        tmp_path, algo_id, key_length, prefer_aes, _OWNER_PW, ""
    )
    for password in ("", _OWNER_PW):
        java = _java_open_projection(enc, password)
        py = _py_open_projection(enc, password)
        assert py == java, f"{algo_id}/{password!r}: {py!r} != {java!r}"
    assert _java_open_projection(enc, "").startswith("OK|")


# =================================================== pypdfbox encrypts → both open
# Closes the interop loop the other way: pypdfbox authors the ciphertext (the
# fixture + a known /Info /Title), then PDFBox and pypdfbox each open it and must
# agree on the recovered tuple — including the /EncryptMetadata-false case that
# PDFBox 3.0.7's StandardProtectionPolicy cannot author itself.


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
@pytest.mark.parametrize(
    "password", [_USER_PW, _OWNER_PW], ids=["user", "owner"]
)
def test_pypdfbox_encrypts_pdfbox_decrypts_on_load(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    password: str,
    tmp_path: Path,
) -> None:
    """PDFBox opens a pypdfbox-encrypted file and recovers the same /Info /Title
    + first text line pypdfbox does, for every algorithm and both passwords."""
    _fixture_present()
    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt_fixture(enc, key_length, prefer_aes, _OWNER_PW, _USER_PW)
    java = _java_open_projection(enc, password)
    py = _py_open_projection(enc, password)
    assert py == java
    assert "title=" + _esc(_TITLE) in java


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    [a for a in _ALGORITHMS if a[1] >= 128],
    ids=[a[0] for a in _ALGORITHMS if a[1] >= 128],
)
def test_encrypt_metadata_false_still_decrypts_on_load(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """A pypdfbox-encrypted file with ``/EncryptMetadata false`` still opens and
    decrypts the body content (strings + streams) on load — the cleartext
    metadata stream does not break the per-object decrypt of everything else.
    PDFBox and pypdfbox agree on the recovered /Info /Title + page text."""
    _fixture_present()
    enc = tmp_path / f"py_nometa_{algo_id}.pdf"
    _py_encrypt_fixture(
        enc, key_length, prefer_aes, _OWNER_PW, _USER_PW, encrypt_metadata=False
    )
    java = _java_open_projection(enc, _USER_PW)
    py = _py_open_projection(enc, _USER_PW)
    assert py == java
    assert "title=" + _esc(_TITLE) in java


@requires_oracle
def test_pypdfbox_encrypts_pdfbox_rejects_wrong_password_on_load(
    tmp_path: Path,
) -> None:
    """A wrong password is rejected on load of a pypdfbox-encrypted file by both
    PDFBox (``InvalidPasswordException`` → non-zero probe exit) and pypdfbox."""
    _fixture_present()
    enc = tmp_path / "py_reject.pdf"
    _py_encrypt_fixture(enc, 256, True, _OWNER_PW, _USER_PW)
    # PDFBox's probe catches the exception and prints the class name.
    java = _java_open_projection(enc, "definitely-wrong")
    assert java == "ERR:InvalidPasswordException"
    assert _py_open_projection(enc, "definitely-wrong") == java


# A non-oracle smoke so a fresh clone without the JAR still exercises the
# pypdfbox decrypt-on-load projection (no Java required).


def test_pypdfbox_decrypt_on_load_smoke(tmp_path: Path) -> None:
    """pypdfbox-only: encrypt the fixture, reopen with both passwords, and
    confirm the /Info /Title + page text decrypt and the role flags are sane —
    runs even without the live oracle so the decrypt-on-load path stays guarded
    on machines lacking the JAR."""
    _fixture_present()
    enc = tmp_path / "smoke.pdf"
    _py_encrypt_fixture(
        enc, 128, True, _OWNER_PW, _USER_PW, restrict_print=True
    )
    user = _py_open_projection(enc, _USER_PW)
    owner = _py_open_projection(enc, _OWNER_PW)
    assert user.startswith("OK|") and owner.startswith("OK|")
    assert "title=" + _esc(_TITLE) in user
    assert "owner=false" in user and "canprint=false" in user
    assert "owner=true" in owner and "canprint=true" in owner
    # Wrong password rejects.
    assert _py_open_projection(enc, "nope") == "ERR:InvalidPasswordException"
