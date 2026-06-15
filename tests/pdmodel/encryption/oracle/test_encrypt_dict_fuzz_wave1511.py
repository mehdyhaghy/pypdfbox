"""Live Apache PDFBox differential fuzz of the ``/Encrypt``-dictionary
construction + decryption-bootstrap leniency surface (wave 1511 / 1512).

The well-formed encryption oracle suite (``test_aes256_r6_oracle``,
``test_crypt_routing_oracle``, ``test_strf_default_oracle``, …) only exercises
syntactically valid ``/Encrypt`` dicts. This probe targets the MALFORMED subset
that a buggy / hostile producer can emit: a missing or unknown ``/Filter``,
``/V`` and ``/R`` sweeps and mismatches, odd / mistyped ``/Length``, missing or
mistyped ``/O`` ``/U`` ``/OE`` ``/UE`` ``/Perms``, a missing ``/P`` or ``/P`` as
a real number, a missing ``/CF`` for V4/V6, an unknown ``/CFM``,
``/EncryptMetadata`` variants, and an empty-user-password open against a mutated
``/U``.

Strategy: encrypt the shared ``unencrypted.pdf`` fixture with pypdfbox at each
``/V`` family (RC4-40 V1/R2-3, RC4-128 V2/R3, AES-128 V4/R4, AES-256 V5/R6) to
obtain a *known-good* encrypted PDF whose user password is empty, then perform
byte-level edits inside the serialised ``/Encrypt`` dict. Both libraries run a
broken-xref recovery pass, so length-changing edits reparse cleanly on both
sides — the open contract stays directly comparable. The deterministic corpus
plus a ``manifest.txt`` (one case name per line, in order) is written to a tmp
dir and the ``EncryptDictFuzzProbe`` loads each ``<case>.pdf`` with an EMPTY
password via ``Loader.loadPDF(file, "")``.

Validation, not blind pinning: the Java line is ground truth. For every case we
assert pypdfbox's load contract — *opens vs raises* (canonicalised across the
Java/Python exception vocabularies), the ``isEncrypted`` flag, and the first
non-blank line of extracted text — matches Java. The probe's ``handler=`` /
``keybits=`` fields are recorded for context but NOT asserted: pypdfbox installs
the resolved handler on each ``COSStream`` (lazy per-object decrypt) rather than
back onto the ``PDEncryption`` object, so ``PDEncryption.get_security_handler()``
raises post-load where upstream returns the cached handler. That is a
long-standing structural difference in where the handler is cached, independent
of the open contract this probe validates, and is pinned in CHANGES.md.
"""

from __future__ import annotations

import io
import re
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
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"


# --------------------------------------------------------------- known-good gen


def _encrypt(key_len_bits: int, prefer_aes: bool) -> bytes:
    """Encrypt the fixture at the requested algorithm with an EMPTY user
    password (owner password ``"o"``) and return the serialised PDF bytes."""
    doc = PDDocument.load(str(_FIXTURE))
    try:
        policy = StandardProtectionPolicy(
            owner_password="o",
            user_password="",
            permissions=AccessPermission(-4),
        )
        policy.set_encryption_key_length(key_len_bits)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


# --------------------------------------------------------------- byte mutators


def _flip_first_hex(data: bytes, key: bytes) -> bytes:
    """Flip the first hex digit of the angle-bracketed value of ``key``
    (``/U <ABCD...>``), corrupting the stored hash while keeping the COS hex
    string syntactically valid."""
    i = data.find(key)
    assert i != -1, f"missing {key!r}"
    lt = data.index(b"<", i)
    pos = lt + 1
    out = bytearray(data)
    out[pos] = ord(b"F") if out[pos] != ord(b"F") else ord(b"0")
    return bytes(out)


def _drop_entry(data: bytes, key: bytes) -> bytes:
    """Delete a ``/Key <hexvalue>`` entry from the /Encrypt dict (value is the
    angle-bracketed hex string that follows). Length-changing; relies on xref
    recovery to reparse."""
    i = data.find(key)
    assert i != -1, f"missing {key!r}"
    lt = data.index(b"<", i)
    gt = data.index(b">", lt)
    # Swallow the leading newline before the key too, keeping the dict tidy.
    start = i
    if start > 0 and data[start - 1] in (ord(b"\n"), ord(b" ")):
        start -= 1
    return data[:start] + data[gt + 1 :]


def _drop_name_entry(data: bytes, entry: bytes) -> bytes:
    """Delete a literal ``entry`` byte run (e.g. ``b'/StmF /StdCF'``) verbatim."""
    i = data.find(entry)
    assert i != -1, f"missing {entry!r}"
    start = i
    if start > 0 and data[start - 1] in (ord(b"\n"), ord(b" ")):
        start -= 1
    return data[:start] + data[i + len(entry) :]


def _truncate_hex(data: bytes, key: bytes, keep: int) -> bytes:
    """Truncate the hex value of ``key`` to ``keep`` hex digits."""
    i = data.find(key)
    assert i != -1, f"missing {key!r}"
    lt = data.index(b"<", i)
    gt = data.index(b">", lt)
    return data[: lt + 1] + data[lt + 1 : gt][:keep] + data[gt:]


def _extend_hex(data: bytes, key: bytes, extra: bytes) -> bytes:
    """Append ``extra`` hex digits to the value of ``key`` (over-long buffer)."""
    i = data.find(key)
    assert i != -1, f"missing {key!r}"
    gt = data.index(b">", data.index(b"<", i))
    return data[:gt] + extra + data[gt:]


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, bytes]:
    """Deterministic, seed-free mutated-/Encrypt corpus, ordered by name."""
    rc4_40 = _encrypt(40, False)
    rc4_128 = _encrypt(128, False)
    aes_128 = _encrypt(128, True)
    aes_256 = _encrypt(256, True)

    cases: dict[str, bytes] = {}

    # ----- baselines: each family must open clean (control group) -----
    cases["good_rc4_40"] = rc4_40
    cases["good_rc4_128"] = rc4_128
    cases["good_aes_128"] = aes_128
    cases["good_aes_256"] = aes_256

    # ----- /Filter mutations -----
    cases["filter_unknown"] = rc4_128.replace(b"/Filter /Standard", b"/Filter /Bogus12", 1)
    cases["filter_pubsec"] = rc4_128.replace(
        b"/Filter /Standard", b"/Filter /Adobe.PubSec", 1
    )
    cases["filter_missing"] = _drop_name_entry(rc4_128, b"/Filter /Standard")
    cases["filter_unknown_aes256"] = aes_256.replace(
        b"/Filter /Standard", b"/Filter /Bogus12", 1
    )

    # ----- /V sweeps and mismatches -----
    cases["v_zero"] = rc4_128.replace(b"/V 2", b"/V 0", 1)
    cases["v_unknown_high"] = rc4_128.replace(b"/V 2", b"/V 9", 1)
    cases["v_3"] = rc4_128.replace(b"/V 2", b"/V 3", 1)
    cases["v6_on_aes256"] = aes_256.replace(b"/V 5", b"/V 6", 1)
    cases["v_real"] = rc4_128.replace(b"/V 2", b"/V 2.5", 1)

    # ----- /R sweeps and mismatches -----
    cases["r_zero"] = rc4_128.replace(b"/R 3", b"/R 0", 1)
    cases["r2_on_v2"] = rc4_128.replace(b"/R 3", b"/R 2", 1)
    cases["r5_on_aes256"] = aes_256.replace(b"/R 6", b"/R 5", 1)
    cases["r4_on_aes256"] = aes_256.replace(b"/R 6", b"/R 4", 1)
    cases["r_unknown_high"] = rc4_128.replace(b"/R 3", b"/R 9", 1)

    # ----- /Length oddities -----
    cases["length_odd_56"] = rc4_128.replace(b"/Length 128", b"/Length 56", 1)
    cases["length_zero"] = rc4_128.replace(b"/Length 128", b"/Length 0", 1)
    cases["length_real"] = rc4_128.replace(b"/Length 128", b"/Length 128.0", 1)
    cases["length_missing"] = _drop_name_entry(rc4_128, b"/Length 128")
    cases["length_huge"] = rc4_128.replace(b"/Length 128", b"/Length 4096", 1)

    # ----- /O /U mutations (R2-4) -----
    cases["o_flipped_rc4"] = _flip_first_hex(rc4_128, b"/O ")
    cases["u_flipped_rc4"] = _flip_first_hex(rc4_128, b"/U ")
    cases["o_missing_rc4"] = _drop_entry(rc4_128, b"/O ")
    cases["u_missing_rc4"] = _drop_entry(rc4_128, b"/U ")
    cases["o_truncated_rc4"] = _truncate_hex(rc4_128, b"/O ", 40)
    cases["u_extended_rc4"] = _extend_hex(rc4_128, b"/U ", b"AABBCCDD")
    cases["o_extended_rc4"] = _extend_hex(rc4_128, b"/O ", b"AABBCCDD")

    # ----- /O /U /OE /UE /Perms mutations (R6) -----
    cases["u_flipped_aes256"] = _flip_first_hex(aes_256, b"/U ")
    cases["o_missing_aes256"] = _drop_entry(aes_256, b"/O ")
    cases["u_missing_aes256"] = _drop_entry(aes_256, b"/U ")
    cases["oe_missing_aes256"] = _drop_entry(aes_256, b"/OE ")
    cases["ue_missing_aes256"] = _drop_entry(aes_256, b"/UE ")
    cases["oe_ue_missing_aes256"] = _drop_entry(
        _drop_entry(aes_256, b"/OE "), b"/UE "
    )
    cases["perms_missing_aes256"] = _drop_entry(aes_256, b"/Perms ")
    cases["perms_flipped_aes256"] = _flip_first_hex(aes_256, b"/Perms ")
    cases["perms_truncated_aes256"] = _truncate_hex(aes_256, b"/Perms ", 8)

    # ----- /P mutations -----
    cases["p_missing_rc4"] = _drop_name_entry(rc4_128, b"/P -4")
    cases["p_real_rc4"] = rc4_128.replace(b"/P -4", b"/P -4.0", 1)
    cases["p_zero_rc4"] = rc4_128.replace(b"/P -4", b"/P 0", 1)

    # ----- /CF and /CFM mutations (V4/V6) -----
    # The /CF crypt-filter reference object number is assigned by the writer at
    # save time (wave 1530 made the classic full-save path renumber objects
    # contiguously like upstream COSWriter), so locate it dynamically rather
    # than hard-coding a number that drifts when the writer renumbers.
    _cf_ref = re.search(rb"/CF \d+ 0 R", aes_128)
    assert _cf_ref is not None, "AES-128 /Encrypt dict has no indirect /CF reference"
    cases["cf_missing_aes128"] = _drop_name_entry(aes_128, _cf_ref.group(0))
    cases["cfm_unknown_aes128"] = aes_128.replace(b"/CFM /AESV2", b"/CFM /BogusXX", 1)
    cases["stmf_unknown_aes128"] = aes_128.replace(b"/StmF /StdCF", b"/StmF /NoCF", 1)

    # ----- /EncryptMetadata variants -----
    cases["encmeta_false_rc4"] = rc4_128.replace(
        b"/P -4", b"/P -4\n/EncryptMetadata false", 1
    )
    cases["encmeta_false_aes256"] = aes_256.replace(
        b"/P -4", b"/P -4\n/EncryptMetadata false", 1
    )
    cases["encmeta_true_aes256"] = aes_256.replace(
        b"/P -4", b"/P -4\n/EncryptMetadata true", 1
    )

    return cases


# --------------------------------------------------------------- contract calc

_TEXT_SAMPLE_PREFIX = "Lorem ipsum"


def _canon_exc(exc: BaseException) -> str:
    """Canonicalise a Python load exception into a category token comparable
    with the Java exception simple-name the probe reports."""
    if isinstance(exc, InvalidPasswordException):
        return "BADPW"
    if isinstance(exc, OSError):
        return "IO"
    return "OTHER"


def _canon_java_exc(simple_name: str) -> str:
    """Canonicalise the Java exception simple-name into the same token space."""
    if simple_name == "InvalidPasswordException":
        return "BADPW"
    if simple_name in ("IOException", "FileSystemException"):
        return "IO"
    return "OTHER"


def _norm_text(token: str | None) -> str:
    """Collapse a first-line text token to TEXT (the readable fixture body was
    recovered), NOTEXT (nothing / unreadable), or the literal otherwise."""
    if not token or token == "NOTEXT":
        return "NOTEXT"
    if token.startswith(_TEXT_SAMPLE_PREFIX):
        return "TEXT"
    return token


def _text_token(text: str | None) -> str:
    """First non-blank line of extracted text, or ``NOTEXT`` — matching the
    probe's ``textSample``."""
    if not text:
        return "NOTEXT"
    for line in text.split("\n"):
        s = line.strip()
        if s:
            return s
    return "NOTEXT"


def _py_contract(pdf: Path) -> tuple[str, str | None, str | None]:
    """Return pypdfbox's load contract for ``pdf`` opened with an empty
    password: (status, enc_flag, text_token).

    ``status`` is ``"ok"`` on a clean load else ``"ERR:<token>"``. ``enc_flag``
    and ``text_token`` are ``None`` when the load failed.
    """
    doc = None
    try:
        doc = PDDocument.load(str(pdf), password="")
    except Exception as exc:  # noqa: BLE001 - contract probe, any failure counts
        return (f"ERR:{_canon_exc(exc)}", None, None)
    try:
        enc = "1" if doc.is_encrypted() else "0"
        try:
            text = PDFTextStripper().get_text(doc)
        except Exception:  # noqa: BLE001 - mirror probe's NOTEXT-on-error
            text = None
        return ("ok", enc, _text_token(text))
    finally:
        doc.close()


def _parse_java_line(line: str) -> tuple[str, str, str | None, str | None]:
    """Parse one probe line into (name, status, enc_flag, text_token).

    Grammar:
      CASE <name> open=ERR:<Exc>
      CASE <name> open=ok enc=<0|1> handler=<h> keybits=<k> text=<sample>
    """
    assert line.startswith("CASE "), line
    rest = line[len("CASE ") :]
    name, _, body = rest.partition(" ")
    if body.startswith("open=ERR:"):
        simple = body[len("open=ERR:") :].strip()
        return (name, f"ERR:{_canon_java_exc(simple)}", None, None)
    # open=ok enc=N handler=H keybits=K text=...
    assert body.startswith("open=ok "), body
    fields = body[len("open=ok ") :]
    enc = fields.split("enc=", 1)[1].split(" ", 1)[0]
    text = fields.split("text=", 1)[1] if "text=" in fields else "NOTEXT"
    return (name, "ok", enc, text.strip() or "NOTEXT")


# ----------------------------------------- focused R5/R6 missing-key auth pins
#
# These don't need the live oracle: they pin the wave-1511/1512 fix to
# ``_compute_encryption_key_r5_r6`` directly, since the corpus's delete-based
# /OE-missing case is masked by an unrelated xref-recovery divergence (a
# length-changing edit to the /Encrypt dict shifts later object offsets and
# pypdfbox's broken-xref recovery raises before auth — pinned separately). The
# fix mirrors upstream ``computeEncryptedKeyRev56``: the role is decided from
# the /O,/U hashes first, then the *authenticating* role's encryption key
# (/OE owner, /UE user) is required — a missing one is an ``OSError`` ("…entry
# is missing"), NOT a silent password mismatch.


def _r6_key_material() -> tuple[bytes, bytes, bytes, bytes]:
    """Build a real pypdfbox R6 file and pull (/O, /U, /OE, /UE) raw bytes."""
    data = _encrypt(256, True)
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    doc = PDDocument.load(io.BytesIO(data))
    try:
        enc = PDEncryption(doc._document.get_encryption_dictionary())
        return (enc.get_o(), enc.get_u(), enc.get_oe(), enc.get_ue())
    finally:
        doc.close()


def test_r6_owner_auth_missing_oe_raises_not_badpw() -> None:
    """Owner password authenticates (hash matches /O) but /OE is absent →
    ``OSError`` ("/Encrypt/OE entry is missing"), mirroring upstream's
    IOException, not a None/InvalidPasswordException mismatch."""
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardSecurityHandler,
    )

    o, u, _oe, ue = _r6_key_material()
    with pytest.raises(OSError, match="OE entry is missing"):
        StandardSecurityHandler._compute_encryption_key_r5_r6(
            b"o", o, u, None, ue, b"", 6
        )


def test_r6_user_auth_missing_ue_raises_not_badpw() -> None:
    """Empty user password authenticates (hash matches /U) but /UE is absent →
    ``OSError`` ("/Encrypt/UE entry is missing"), not a silent mismatch."""
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardSecurityHandler,
    )

    o, u, oe, _ue = _r6_key_material()
    with pytest.raises(OSError, match="UE entry is missing"):
        StandardSecurityHandler._compute_encryption_key_r5_r6(
            b"", o, u, oe, None, b"", 6
        )


def test_r6_other_role_key_absent_still_opens() -> None:
    """A document missing the *non*-authenticating role's encryption key still
    yields a 32-byte file key: empty user password unwraps /UE even when /OE is
    gone (and the owner password unwraps /OE even when /UE is gone)."""
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardSecurityHandler,
    )

    o, u, oe, ue = _r6_key_material()
    user_key = StandardSecurityHandler._compute_encryption_key_r5_r6(
        b"", o, u, None, ue, b"", 6
    )
    owner_key = StandardSecurityHandler._compute_encryption_key_r5_r6(
        b"o", o, u, oe, None, b"", 6
    )
    assert user_key is not None and len(user_key) == 32
    assert owner_key is not None and len(owner_key) == 32


def test_r6_wrong_password_returns_none() -> None:
    """A password matching neither role returns None (→ caller raises
    InvalidPasswordException) — the security check is intact."""
    from pypdfbox.pdmodel.encryption.standard_security_handler import (
        StandardSecurityHandler,
    )

    o, u, oe, ue = _r6_key_material()
    assert (
        StandardSecurityHandler._compute_encryption_key_r5_r6(
            b"definitely-not-it", o, u, oe, ue, b"", 6
        )
        is None
    )


# --------------------------------------------------------------------- the test


@requires_oracle
def test_encrypt_dict_fuzz_open_contract_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated-/Encrypt case loads (or fails to load) identically on
    pypdfbox and Apache PDFBox 3.0.7: same open status (ok vs canonicalised
    error category), same ``isEncrypted`` flag, and same first-line text
    sample. Divergences are pinned explicitly in ``_PINNED_DIVERGENCES`` with a
    reason (and a matching CHANGES.md row) rather than silently tolerated."""
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")

    corpus = _build_corpus()
    for name, data in corpus.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("EncryptDictFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )

    mismatches: list[str] = []
    for line in java_lines:
        name, j_status, j_enc, j_text = _parse_java_line(line)
        p_status, p_enc, p_text = _py_contract(tmp_path / f"{name}.pdf")

        # Text token is normalised to TEXT (recovered the readable fixture body),
        # NOTEXT (nothing / garbled), or the literal otherwise — the meaningful
        # distinction is "decrypted to readable content" vs not, not the exact
        # line, which both libs reproduce identically when they recover it.
        contract_py = (p_status, p_enc, _norm_text(p_text))
        contract_java = (j_status, j_enc, _norm_text(j_text))

        if name in _PINNED_DIVERGENCES:
            expected_py = _PINNED_DIVERGENCES[name]
            if contract_py != expected_py:
                mismatches.append(
                    f"{name}: PINNED py expected {expected_py} got {contract_py} "
                    f"(java {contract_java})"
                )
            continue

        if contract_py != contract_java:
            mismatches.append(
                f"{name}: py {contract_py} != java {contract_java}  [{line}]"
            )

    assert not mismatches, "open-contract divergence(s):\n" + "\n".join(mismatches)


# Pinned, intentional divergences from the Java open-contract. Each entry maps a
# case name to the (status, enc_flag, text_token) pypdfbox is asserted to
# produce, with a justification. Populated empirically against the live oracle
# and cross-checked against upstream source; see CHANGES.md (wave 1512). Every
# entry is one of: (a) pypdfbox failing a load Java also fails but with a
# different exception *category* (Java NPE / IllegalArgument vs pypdfbox's clean
# InvalidPasswordException — pypdfbox is strictly better, never an NPE), or
# (b) pypdfbox tolerating a malformed dict Java rejects (more lenient recovery),
# or (c) a content-recovery difference on an /R or /CF mismatch where the two
# pick different cipher fallbacks. None weakens a security check: a wrong
# password is still rejected on both sides in every case here.
_PINNED_DIVERGENCES: dict[str, tuple[str, str | None, str | None]] = {
    # --- /V mismatch:
    # * /V 9 (unknown, on a V2/RC4 file): pypdfbox rejects the unknown
    #   algorithm version (a clean error before any plaintext is exposed) where
    #   Java opens with a no-op cipher and yields no readable text. Both refuse
    #   to expose the plaintext; pypdfbox fails closed, Java fails open to
    #   garbage — pypdfbox is the safer of the two. Since wave 1532 the AES
    #   decrypt path raises ``OSError`` (was an ``OTHER``-category error) when it
    #   meets the malformed/short ciphertext produced under the unknown version,
    #   so the category is now ``IO`` — still a clean fail-closed.
    # * /V 6 forced on an AES-256 file: pypdfbox keeps the /CF-derived routing
    #   and recovers text; Java's V6 path can't and yields NOTEXT. Both open.
    "v_unknown_high": ("ERR:IO", None, "NOTEXT"),
    "v6_on_aes256": ("ok", "1", "TEXT"),
    # --- /R mismatch: both libs reject the (now-inconsistent) /R, but pypdfbox
    # surfaces a clean InvalidPasswordException where Java throws IOException.
    "r_zero": ("ERR:BADPW", None, "NOTEXT"),
    "r4_on_aes256": ("ERR:BADPW", None, "NOTEXT"),
    "r_unknown_high": ("ERR:BADPW", None, "NOTEXT"),
    # --- /Length 0 / huge: Java validates the key length and throws
    # (IllegalArgumentException / IOException); pypdfbox ignores the bogus
    # /Length (the real key size comes from /V and /CF) and opens. More lenient.
    "length_zero": ("ok", "1", "TEXT"),
    "length_huge": ("ok", "1", "TEXT"),
    # --- /O or /U missing: Java dereferences the null key buffer and throws
    # NullPointerException; pypdfbox guards up front and raises a clean
    # InvalidPasswordException. Same outcome (no open), better diagnostics.
    "o_missing_rc4": ("ERR:BADPW", None, "NOTEXT"),
    "u_missing_rc4": ("ERR:BADPW", None, "NOTEXT"),
    "o_missing_aes256": ("ERR:BADPW", None, "NOTEXT"),
    "u_missing_aes256": ("ERR:BADPW", None, "NOTEXT"),
    # --- /OE missing on AES-256: deleting /OE length-shifts every later object
    # offset; pypdfbox's broken-xref recovery raises ``OSError`` ("expected
    # integer …") BEFORE reaching auth, where PDFBox's brute-force xref rebuild
    # recovers and opens via the empty-user password (/UE present, owner /OE
    # irrelevant to the user). A parser-recovery-robustness divergence in the
    # xref rebuilder, NOT in the StandardSecurityHandler auth path this wave
    # owns — the auth-side /OE/UE-missing contract is pinned directly by the
    # parser-independent ``test_r6_*`` unit tests above. (/O missing, /UE
    # missing, and /OE+/UE missing all land on the same contract as Java's
    # category once recovery completes; only this one diverges on the rebuild.)
    "oe_missing_aes256": ("ERR:IO", None, "NOTEXT"),
    # --- /Perms missing or truncated: Java's validatePerms feeds the
    # null/short buffer to AES and throws (NPE / IOException); pypdfbox treats
    # /Perms as the post-auth integrity check it is — a bad/absent /Perms only
    # logs a warning and the file opens on the valid password (PDFBox parity
    # with the *intent* of validatePerms, which is warn-not-reject for a present
    # /Perms). More robust; the password itself was still validated.
    "perms_missing_aes256": ("ok", "1", "TEXT"),
    "perms_truncated_aes256": ("ok", "1", "TEXT"),
    # --- unknown /StmF name: Java falls back to a cipher that recovers the
    # text; pypdfbox routes the unknown crypt-filter name to Identity (no
    # per-stream decrypt) so the stream stays ciphered and text=NOTEXT. Both
    # open enc=1; a content-recovery-leniency difference in crypt-filter routing
    # (not in the StandardSecurityHandler auth path this wave owns).
    "stmf_unknown_aes128": ("ok", "1", "NOTEXT"),
}
