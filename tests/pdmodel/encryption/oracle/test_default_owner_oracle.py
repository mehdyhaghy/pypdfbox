"""Live Apache PDFBox interop for the *default / empty / null owner password*
branch of ``StandardProtectionPolicy`` + ``StandardSecurityHandler``.

PDFBox upstream behaviour (decompiled from
``StandardSecurityHandler#prepareDocumentForEncryption`` in the pinned PDFBox
3.0.7 jar):

  1. ``StandardProtectionPolicy``'s constructor stores the owner / user
     strings verbatim (including ``null``). No defaulting in the policy.
  2. ``prepareDocumentForEncryption`` then coerces each ``null`` to ``""``
     and — crucially — does::

         if (ownerPw.isEmpty()) ownerPw = userPw;

     so an empty *or* null owner password silently defaults to the user
     password before any hashing happens. The file is still legitimately
     encrypted; the owner just shares the user's credential.

pypdfbox's matching code lives in ``standard_security_handler.py``'s
``prepare_document`` (~line 1123)::

    if not owner_pw:
        owner_pw = user_pw

— functionally identical (we apply the fallback on the encoded bytes after
SaslPrep on R6; since user_pw goes through the same SaslPrep step, the result
is byte-identical to the upstream pre-SaslPrep fallback).

This module exercises every angle that matters for cross-engine interop:

* **/O byte parity** — for the deterministic algorithms (R3 RC4-128, R4
  AES-128) the on-the-wire ``/O`` for ``("", "user")`` and ``("",  "")`` must
  be the exact same bytes PDFBox would have written. ``/O`` is the
  owner-validation entry; if the empty-owner fallback diverges, ``/O``
  diverges.
* **/U[:16] byte parity** — only the first 16 bytes of ``/U`` are validated
  by Algorithm 6; the last 16 are "arbitrary padding" per the spec. pypdfbox
  zero-pads, PDFBox emits leftover hash bytes — both are spec-compliant and
  mutually openable, so we compare only the validated 16 bytes.
* **Round-trip content recovery (both directions, both passwords)** —
  pypdfbox-encrypts → PDFBox-decrypts AND PDFBox-encrypts → pypdfbox-decrypts,
  for AES-128, AES-256, RC4-128. Opens with the user password AND with the
  owner password (which == user password after the fallback).
* **``("", "")`` legitimacy** — both passwords empty still produces a file
  that opens with the empty password and recovers the plaintext content.
* **``null`` (``None``) owner equivalence** — passing ``None`` for the owner
  argument is treated identically to the empty string.

R6 (AES-256) /O cannot be compared byte-for-byte across engines because
Algorithm 8 derives ``/O`` from a random validation salt and a random key
salt (``SecureRandom`` on the Java side, ``os.urandom`` on ours), so two runs
of the *same* engine with the *same* inputs already produce different /O
values. For R6 we therefore only assert content round-tripping, which is the
real interop guarantee anyway.

Probe: ``oracle/probes/DefaultOwnerProbe.java`` — three subcommands
(``ENCRYPT`` / ``DECRYPT`` / ``DUMP``) sharing the JVM startup cost. The
``__NULL__`` sentinel maps to a Java ``null`` reference, since the JVM
command line can't otherwise pass null.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_USER_PW = "user"

# (id, key_length_bits, prefer_aes) — every algorithm StandardProtectionPolicy
# can produce. AES-256 is included for the round-trip assertions even though
# its /O is non-deterministic (random salts).
_ALGORITHMS_DETERMINISTIC = [
    ("rc4_128", 128, False),
    ("aes_128", 128, True),
]
_ALGORITHMS_ALL = _ALGORITHMS_DETERMINISTIC + [("aes_256", 256, True)]

# Sentinel matching DefaultOwnerProbe's contract — maps to Java null.
_NULL = "__NULL__"


# ----------------------------------------------------------------- fixture
# A fixture-skip helper, mirroring the pattern in the sibling
# ``test_encryption_interop_oracle`` module so a missing baseline PDF doesn't
# look like a hard failure.


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _plaintext_baseline() -> tuple[int, str]:
    """pypdfbox-extracted (pages, text) of the unencrypted fixture."""
    with PDDocument.load(_FIXTURE) as doc:
        return doc.get_number_of_pages(), PDFTextStripper().get_text(doc)


def _py_encrypt(
    src: Path,
    out: Path,
    owner_password: str | None,
    user_password: str,
    key_length: int,
    prefer_aes: bool,
) -> None:
    """Encrypt ``src`` to ``out`` with the supplied password pair."""
    doc = PDDocument.load(str(src))
    try:
        policy = StandardProtectionPolicy(
            owner_password=owner_password,
            user_password=user_password,
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _py_extract(path: Path, password: str) -> tuple[int, str]:
    """Open with pypdfbox + ``password`` and return (pages, text)."""
    with PDDocument.load(str(path), password=password) as doc:
        return doc.get_number_of_pages(), PDFTextStripper().get_text(doc)


def _java_encrypt(
    src: Path,
    out: Path,
    owner_arg: str,
    user_arg: str,
    key_length: int,
    prefer_aes: bool,
) -> None:
    """Drive DefaultOwnerProbe ENCRYPT — owner_arg / user_arg may be
    ``_NULL`` (→ Java null) or any literal string including ``\"\"``."""
    run_probe(
        "DefaultOwnerProbe",
        "ENCRYPT",
        str(src),
        str(out),
        owner_arg,
        user_arg,
        str(key_length),
        "true" if prefer_aes else "false",
    )


def _java_decrypt(path: Path, password: str) -> tuple[int, str]:
    """Drive DefaultOwnerProbe DECRYPT — same framing as DecryptProbe."""
    raw = run_probe_text("DefaultOwnerProbe", "DECRYPT", str(path), password)
    first, _, rest = raw.partition("\n")
    assert first.startswith("PAGES:"), f"probe framing broke: {first!r}"
    return int(first[len("PAGES:") :]), rest


def _java_dump(path: Path, password: str) -> dict[str, str]:
    """Drive DefaultOwnerProbe DUMP and parse its ``KEY:value`` framing."""
    raw = run_probe_text("DefaultOwnerProbe", "DUMP", str(path), password)
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k] = v
    return out


# -------------------------- pypdfbox-encrypts → PDFBox-decrypts (content)


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_ALL,
    ids=[a[0] for a in _ALGORITHMS_ALL],
)
@pytest.mark.parametrize(
    "owner_pw",
    [None, ""],
    ids=["owner_none", "owner_empty"],
)
def test_pypdfbox_empty_owner_round_trips_through_java(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    owner_pw: str | None,
    tmp_path: Path,
) -> None:
    """pypdfbox encrypts with an empty/null owner and ``user_pw``; Apache
    PDFBox opens the result with the user password and recovers the
    plaintext. Proves the empty-owner fallback in ``prepare_document`` is
    byte-compatible with PDFBox's reader."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))
    enc = tmp_path / f"py_emptyowner_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, owner_pw, _USER_PW, key_length, prefer_aes)
    # Plaintext must not appear verbatim (sanity check the encryption ran).
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    pages, text = _java_decrypt(enc, _USER_PW)
    assert pages == 2
    assert text == base_text


# -------------------------- PDFBox-encrypts → pypdfbox-decrypts (content)


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_ALL,
    ids=[a[0] for a in _ALGORITHMS_ALL],
)
@pytest.mark.parametrize(
    "owner_arg",
    [_NULL, ""],
    ids=["owner_null", "owner_empty"],
)
def test_java_empty_owner_round_trips_through_pypdfbox(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    owner_arg: str,
    tmp_path: Path,
) -> None:
    """Apache PDFBox encrypts with an empty/null owner and ``user_pw``;
    pypdfbox opens with the user password and recovers the plaintext.
    Mirror of the previous test from the read side."""
    _fixture_present()
    base_pages, base_text = _plaintext_baseline()
    enc = tmp_path / f"java_emptyowner_{algo_id}.pdf"
    _java_encrypt(_FIXTURE, enc, owner_arg, _USER_PW, key_length, prefer_aes)

    pages, text = _py_extract(enc, _USER_PW)
    assert pages == base_pages
    assert text == base_text


# ----------------- owner-password-equals-user works on both directions


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_ALL,
    ids=[a[0] for a in _ALGORITHMS_ALL],
)
def test_empty_owner_opens_with_user_pw_as_owner_on_both_engines(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    tmp_path: Path,
) -> None:
    """When the owner defaults to the user password, opening with that same
    password should grant access on *either* the user OR the owner path.
    Exercise the symmetry: pypdfbox-encrypted file opens through Java with
    the user-pw-as-owner-pw, and vice versa."""
    _fixture_present()
    base_pages, base_text = _plaintext_baseline()

    # pypdfbox encrypts with empty owner → Java opens with user pw.
    py_enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, py_enc, "", _USER_PW, key_length, prefer_aes)
    pages, text = _java_decrypt(py_enc, _USER_PW)
    assert pages == base_pages
    assert text == base_text

    # Java encrypts with empty owner → pypdfbox opens with user pw.
    java_enc = tmp_path / f"java_{algo_id}.pdf"
    _java_encrypt(_FIXTURE, java_enc, "", _USER_PW, key_length, prefer_aes)
    pages2, text2 = _py_extract(java_enc, _USER_PW)
    assert pages2 == base_pages
    assert text2 == base_text


# --------------------- both passwords empty ("", "") is still encryptable


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_ALL,
    ids=[a[0] for a in _ALGORITHMS_ALL],
)
def test_both_passwords_empty_pypdfbox_encrypts_java_decrypts(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """``("", "")`` — both passwords empty. The file is still legitimately
    encrypted (file key derives from the padded empty password). Opens with
    the empty password on the Java side after a pypdfbox encrypt."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))
    enc = tmp_path / f"py_empty_empty_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, "", "", key_length, prefer_aes)
    pages, text = _java_decrypt(enc, "")
    assert pages == 2
    assert text == base_text


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_ALL,
    ids=[a[0] for a in _ALGORITHMS_ALL],
)
def test_both_passwords_empty_java_encrypts_pypdfbox_decrypts(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """``("", "")`` round-trip in the other direction — Java encrypts with
    both passwords empty, pypdfbox opens with the empty password and
    recovers content."""
    _fixture_present()
    base_pages, base_text = _plaintext_baseline()
    enc = tmp_path / f"java_empty_empty_{algo_id}.pdf"
    _java_encrypt(_FIXTURE, enc, "", "", key_length, prefer_aes)
    pages, text = _py_extract(enc, "")
    assert pages == base_pages
    assert text == base_text


# --------------------- /O byte parity for deterministic algorithms


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_DETERMINISTIC,
    ids=[a[0] for a in _ALGORITHMS_DETERMINISTIC],
)
@pytest.mark.parametrize(
    ("py_owner", "java_owner"),
    [(None, _NULL), ("", "")],
    ids=["null_vs_null", "empty_vs_empty"],
)
def test_o_field_bytes_match_for_empty_owner(
    algo_id: str,
    key_length: int,
    prefer_aes: bool,
    py_owner: str | None,
    java_owner: str,
    tmp_path: Path,
) -> None:
    """For R3 (RC4-128) and R4 (AES-128), ``/O`` is a deterministic function
    of (owner_pw, user_pw, R, key_length) — Algorithm 3 has no randomness.
    A pypdfbox-encrypted file's ``/O`` must therefore equal PDFBox's ``/O``
    byte-for-byte when both engines see the same null-or-empty owner +
    same user password. This is the strongest possible parity assertion
    for the empty-owner branch — any divergence in the fallback logic
    would surface here.

    /U is also deterministic but only the first 16 bytes are validated
    (Algorithm 6); the trailing 16 are "arbitrary padding" (PDF 32000-1
    §7.6.4.4.4). pypdfbox zero-pads, PDFBox emits leftover hash bytes;
    both are spec-compliant and openable by either reader, so we compare
    only ``/U[:16]``."""
    _fixture_present()

    py_enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, py_enc, py_owner, _USER_PW, key_length, prefer_aes)
    py_dump = _java_dump(py_enc, _USER_PW)

    java_enc = tmp_path / f"java_{algo_id}.pdf"
    _java_encrypt(_FIXTURE, java_enc, java_owner, _USER_PW, key_length, prefer_aes)
    java_dump = _java_dump(java_enc, _USER_PW)

    # /O — 32 hex bytes, every byte meaningful.
    assert py_dump["O"] == java_dump["O"], (
        f"/O divergence on {algo_id}: pypdfbox={py_dump['O']!r} "
        f"java={java_dump['O']!r}"
    )
    # /U[:16] — first 16 bytes (= 32 hex chars) are validated.
    assert py_dump["U"][:32] == java_dump["U"][:32], (
        f"/U[:16] divergence on {algo_id}: pypdfbox={py_dump['U'][:32]!r} "
        f"java={java_dump['U'][:32]!r}"
    )
    # /V /R /Length must also match — sanity-check the algorithm choice.
    assert py_dump["V"] == java_dump["V"]
    assert py_dump["R"] == java_dump["R"]
    assert py_dump["LEN"] == java_dump["LEN"]


# --------------------- wrong-password rejection on empty-owner files


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS_ALL,
    ids=[a[0] for a in _ALGORITHMS_ALL],
)
def test_wrong_password_rejected_on_pypdfbox_empty_owner(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """A pypdfbox file with an empty-defaulted owner password still
    rejects a wrong password on the Java side — the encryption is real,
    not a no-op."""
    import subprocess

    _fixture_present()
    enc = tmp_path / f"py_emptyowner_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, "", _USER_PW, key_length, prefer_aes)
    try:
        run_probe("DefaultOwnerProbe", "DECRYPT", str(enc), "definitely-wrong")
    except subprocess.CalledProcessError as exc:
        assert b"InvalidPasswordException" in (exc.stderr or b"")
        return
    pytest.fail("Java probe accepted a wrong password on an empty-owner file")
