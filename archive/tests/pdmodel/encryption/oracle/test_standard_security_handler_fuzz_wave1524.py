"""Live Apache PDFBox differential fuzz of the StandardSecurityHandler KEY
DERIVATION + PASSWORD AUTHENTICATION algorithms (wave 1524).

The existing encryption oracle suites exercise the full document open path
(``Loader.loadPDF``) and the on-the-wire ``/Encrypt`` dictionary
(``EncryptDictFuzzProbe`` parse leniency, ``CryptFilterFuzzProbe`` decode
dispatch). NONE of them poke the raw algorithm-level instance methods —
``computeEncryptedKey`` (Algorithm 2 / 2.A), ``isUserPassword`` (Algorithm 6 /
11), ``isOwnerPassword`` (Algorithm 7 / 12) and ``getUserPassword`` (Algorithm 7
inverse) — with deliberately MALFORMED ``/O`` / ``/U`` / ``/OE`` / ``/UE`` byte
strings, out-of-range ``/R``, odd ``/Length`` and over-/under-length entries.

That is this wave's surface. The probe (``StandardSecurityHandlerFuzzProbe``)
drives PDFBox's instance methods with deterministic in-process byte inputs (no
random, no files) and projects the hex key / boolean / error-class. The Python
side builds byte-for-byte identical inputs and compares.

Validation, not blind pinning: the Java line is ground truth for every case.

Three real divergences were fixed in production to match upstream (CHANGES.md
wave 1524), all rooted in pypdfbox using ``>=`` revision tests where the 3.0.7
bytecode uses EXACT equalities:

1. ``computeEncryptedKey`` routed ``encRevision`` 7 / 99 into the AES-256 Rev56
   path (``revision >= 5``); upstream dispatches ONLY 5 / 6 there and falls all
   other revisions through to Algorithm 2 (Rev234), deriving a key.
2. ``computeEncryptedKeyRev234`` ran the 50-round MD5 re-hash on ``revision >=
   3`` and the ``0xFFFFFFFF`` metadata mix on ``revision >= 4``; upstream gates
   them on ``== 3 || == 4`` and ``== 4`` respectively, so an out-of-range
   revision reaching Algorithm 2 derives the plain rev-2 key.
3. ``getUserPassword`` ran the r3/r4 RC4 unwind for any revision below 5;
   upstream's ``getUserPassword234`` returns empty bytes for any revision not in
   {2,3,4}.

The remaining divergences are pinned both-sides (unalignable):

* Java ``IOException`` ↔ pypdfbox ``OSError`` (the project-wide I/O exception
  mapping) for unknown-revision validators and short r6 ``/O`` / ``/U``.
* Java ``IllegalArgumentException`` ↔ pypdfbox ``ValueError`` for a zero-length
  RC4 key.
* Java ``ArrayIndexOutOfBoundsException`` (an unguarded array-slice CRASH on a
  too-short ``/O`` or empty ``/U`` in the r6 path) ↔ pypdfbox's lenient slice,
  which returns a key / ``False`` instead of crashing.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler as _S,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# --- Deterministic baselines (PDFBox-verified to authenticate) ---------------
_PW = "736563726574"  # b"secret"
_ID = "000102030405060708090a0b0c0d0e0f"
# R3 / R4 128-bit /O /U (pypdfbox-derived; PDFBox authenticates them).
_O3 = "0e522925a3e4e874c3cfacbef511a73ac4ec2bd865dcd3d4627614917abfd7e4"
_U3 = "c5ae74abbea44f79cc0b3a703d26115f00000000000000000000000000000000"
# R2 40-bit /O /U.
_O2 = "e5a8d2687bd9d0cff946b7ac55f51081dcf0d116554c4bfcb0a5e446f69ea48a"
_U2 = "3650845352086f41360b3e32d48197c6690e479a9165100278a0f46b670ecee9"
# R6 256-bit /O /U /OE /UE (PDFBox-generated, password "secret").
_O6 = (
    "5d208e3070d37cc887ace1a56ab619ff85739d7865e8845ac91c67d45466ca59"
    "dcf74b5da92ce2c968cc81ade88a073a"
)
_U6 = (
    "9420193818f919da2087669f7f6ef1719f4710ffe7cb025aaa9ce899cde17e01"
    "2f72f3f5af6522a22e21547c5902636e"
)
_OE6 = "f2ffa73406d4329def64588acbfb6ea1c83a6bc239adac95410186d0dd32a8e9"
_UE6 = "0b85ff77144d4d076aac7a6a0f06ccc0fdcc1ce48091dd399d16f9db9c876c18"

_LONGPW = "61" * 40  # 40-byte password ("aaa…"), exercises 32-byte truncation


def _hx(s: str) -> bytes:
    if s in ("-", ""):
        return b""
    return bytes.fromhex(s)


# Each entry: (id, op, [probe-fields]).  Probe fields are strings; "-" means an
# empty byte string.  Field order matches the probe's per-op signature exactly.
#
#  key:     pw o u oe ue perms id rev keylen encmeta isowner
#  user:    pw u o perms id rev keylen encmeta
#  owner:   pw u o perms id rev keylen encmeta
#  getuser: owner o rev length
_PARITY_CASES = [
    # ---- computeEncryptedKey — well-formed + the THREE fixed revisions ----
    ("k_r3_user", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "3", "16", "true", "false"]),
    ("k_r3_owner", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "3", "16", "true", "true"]),
    ("k_r2_user", "key", [_PW, _O2, _U2, "-", "-", "-3904", _ID, "2", "5", "true", "false"]),
    ("k_r6_user", "key", [_PW, _O6, _U6, _OE6, _UE6, "-3904", "-", "6", "32", "true", "false"]),
    ("k_r6_owner", "key", [_PW, _O6, _U6, _OE6, _UE6, "-3904", "-", "6", "32", "true", "true"]),
    # out-of-range revision falls through to Algorithm 2 (bug #1/#2 fix)
    ("k_rev0", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "0", "16", "true", "false"]),
    ("k_rev7", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "7", "16", "true", "false"]),
    ("k_rev99", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "99", "16", "true", "false"]),
    # short / empty /O still derive a key (only first 32 bytes consumed)
    ("k_shortO", "key", [_PW, _O3[:32], _U3, "-", "-", "-3904", _ID, "3", "16", "true", "false"]),
    ("k_emptyO", "key", [_PW, "-", _U3, "-", "-", "-3904", _ID, "3", "16", "true", "false"]),
    # odd key lengths
    ("k_keylen5", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "3", "5", "true", "false"]),
    ("k_keylen0", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "3", "0", "true", "false"]),
    # r4 with /EncryptMetadata false (the 0xFFFFFFFF mix)
    ("k_r4_nometa", "key", [_PW, _O3, _U3, "-", "-", "-3904", _ID, "4", "16", "false", "false"]),
    ("k_emptyid", "key", [_PW, _O3, _U3, "-", "-", "-3904", "-", "3", "16", "true", "false"]),
    # r6 missing the NON-authenticating role's key still derives the key
    ("k_r6_noOE_own", "key", [_PW, _O6, _U6, "-", _UE6, "-3904", "-", "6", "32", "true", "true"]),
    ("k_r6_noUE_usr", "key", [_PW, _O6, _U6, _OE6, "-", "-3904", "-", "6", "32", "true", "false"]),
    # ---- isUserPassword ----
    ("u_valid", "user", [_PW, _U3, _O3, "-3904", _ID, "3", "16", "true"]),
    ("u_wrong", "user", ["deadbeef", _U3, _O3, "-3904", _ID, "3", "16", "true"]),
    ("u_empty_pw", "user", ["-", _U3, _O3, "-3904", _ID, "3", "16", "true"]),
    ("u_r2_valid", "user", [_PW, _U2, _O2, "-3904", _ID, "2", "5", "true"]),
    ("u_r6_valid", "user", [_PW, _U6, _O6, "-3904", "-", "6", "32", "true"]),
    ("u_r6_wrong", "user", ["deadbeef", _U6, _O6, "-3904", "-", "6", "32", "true"]),
    ("u_shortU", "user", [_PW, _U3[:32], _O3, "-3904", _ID, "3", "16", "true"]),
    ("u_emptyU", "user", [_PW, "-", _O3, "-3904", _ID, "3", "16", "true"]),
    ("u_overlongU", "user", [_PW, _U3 + "aabbcc", _O3, "-3904", _ID, "3", "16", "true"]),
    ("u_r6_shortU", "user", [_PW, _U6[:80], _O6, "-3904", "-", "6", "32", "true"]),
    ("u_longpw", "user", [_LONGPW, _U3, _O3, "-3904", _ID, "3", "16", "true"]),
    # ---- isOwnerPassword ----
    ("o_valid", "owner", [_PW, _U3, _O3, "-3904", _ID, "3", "16", "true"]),
    ("o_wrong", "owner", ["deadbeef", _U3, _O3, "-3904", _ID, "3", "16", "true"]),
    ("o_r2_valid", "owner", [_PW, _U2, _O2, "-3904", _ID, "2", "5", "true"]),
    ("o_r6_valid", "owner", [_PW, _U6, _O6, "-3904", "-", "6", "32", "true"]),
    ("o_r6_wrong", "owner", ["deadbeef", _U6, _O6, "-3904", "-", "6", "32", "true"]),
    ("o_shortO", "owner", [_PW, _U3, _O3[:32], "-3904", _ID, "3", "16", "true"]),
    ("o_emptyO", "owner", [_PW, _U3, "-", "-3904", _ID, "3", "16", "true"]),
    ("o_r2_keylen16", "owner", [_PW, _U2, _O2, "-3904", _ID, "2", "16", "true"]),
    # ---- getUserPassword ----
    ("g_r3", "getuser", [_PW, _O3, "3", "16"]),
    ("g_r2", "getuser", [_PW, _O2, "2", "5"]),
    ("g_r6", "getuser", [_PW, _O6, "6", "32"]),
    ("g_rev0", "getuser", [_PW, _O3, "0", "16"]),  # bug #3 fix: empty, not a hash
    ("g_rev7", "getuser", [_PW, _O3, "7", "16"]),
    ("g_emptyO", "getuser", [_PW, "-", "3", "16"]),
    ("g_shortO", "getuser", [_PW, _O3[:32], "3", "16"]),
    ("g_r2_keylen16", "getuser", [_PW, _O2, "2", "16"]),
]

# Pinned divergences — both sides raise / differ but the contract is unalignable.
# kind: "exc_map"  → Java raises any exception, pypdfbox raises the mapped type.
#       "java_crash"→ Java crashes (AIOOBE) on an unguarded slice; pypdfbox is
#                     lenient and returns a value.
_PINNED_CASES = [
    ("k_r6_shortU_own", "key",
     [_PW, _O6, _U6[:80], _OE6, _UE6, "-3904", "-", "6", "32", "true", "true"],
     "exc_map", OSError),
    ("u_rev0", "user", [_PW, _U3, _O3, "-3904", _ID, "0", "16", "true"], "exc_map", OSError),
    ("u_rev7", "user", [_PW, _U3, _O3, "-3904", _ID, "7", "16", "true"], "exc_map", OSError),
    ("u_rev99", "user", [_PW, _U3, _O3, "-3904", _ID, "99", "16", "true"], "exc_map", OSError),
    ("u_keylen0", "user", [_PW, _U3, _O3, "-3904", _ID, "3", "0", "true"], "exc_map", ValueError),
    ("o_r6_shortO", "owner",
     [_PW, _U6, _O6[:70], "-3904", "-", "6", "32", "true"], "exc_map", OSError),
    ("o_r6_emptyO", "owner", [_PW, _U6, "-", "-3904", "-", "6", "32", "true"], "exc_map", OSError),
    ("o_rev0", "owner", [_PW, _U3, _O3, "-3904", _ID, "0", "16", "true"], "exc_map", OSError),
    ("o_rev7", "owner", [_PW, _U3, _O3, "-3904", _ID, "7", "16", "true"], "exc_map", OSError),
    ("g_keylen0", "getuser", [_PW, _O3, "3", "0"], "exc_map", ValueError),
    # Java crashes (AIOOBE) on a too-short /O or empty /U in the r6 path;
    # pypdfbox slices leniently. Pinned: Java is the crash, pypdfbox the lenient
    # value — neither side is "wrong" for a malformed dict, so we record both.
    ("k_r6_shortO", "key",
     [_PW, _O6[:80], _U6, _OE6, _UE6, "-3904", "-", "6", "32", "true", "true"],
     "java_crash", None),
    ("u_r6_emptyU", "user", [_PW, "-", _O6, "-3904", "-", "6", "32", "true"], "java_crash", None),
]


def _py_eval(op: str, f: list[str]) -> str:
    """Project pypdfbox's result into the probe's line grammar (or ERR:<type>)."""
    try:
        if op == "key":
            pw, o, u, oe, ue, perms, idb, rev, keylen, em, iso = f
            key = _S.compute_encrypted_key(
                _hx(pw), _hx(o), _hx(u), _hx(oe), _hx(ue), int(perms),
                _hx(idb), int(rev), int(keylen), em == "true", iso == "true",
            )
            return "key=" + key.hex()
        if op == "user":
            pw, u, o, perms, idb, rev, keylen, em = f
            r = _S.is_user_password(
                _hx(pw), _hx(u), _hx(o), int(perms), _hx(idb),
                int(rev), int(keylen), em == "true",
            )
            return "user=" + ("1" if r else "0")
        if op == "owner":
            pw, u, o, perms, idb, rev, keylen, em = f
            r = _S.is_owner_password(
                _hx(pw), _hx(u), _hx(o), int(perms), _hx(idb),
                int(rev), int(keylen), em == "true",
            )
            return "owner=" + ("1" if r else "0")
        if op == "getuser":
            owner, o, rev, length = f
            r = _S.get_user_password(_hx(owner), _hx(o), int(rev), int(length))
            return "getuser=" + r.hex()
    except Exception as exc:  # noqa: BLE001 — projecting the exception class
        return "ERR:" + type(exc).__name__
    raise AssertionError(f"unknown op {op}")


def _run_java() -> dict[str, str]:
    """Run the probe over EVERY case and parse ``CASE <name> <result>`` lines."""
    specs = [
        "|".join([cid, op, *fields])
        for (cid, op, fields, *_) in (_PARITY_CASES + _PINNED_CASES)
    ]
    raw = run_probe_text("StandardSecurityHandlerFuzzProbe", *specs)
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("CASE "):
            _, name, val = line.split(" ", 2)
            out[name] = val
    return out


@pytest.fixture(scope="module")
def java_results() -> dict[str, str]:
    return _run_java()


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "op", "fields"),
    [(c[0], c[1], c[2]) for c in _PARITY_CASES],
    ids=[c[0] for c in _PARITY_CASES],
)
def test_key_derivation_parity(
    case_id: str, op: str, fields: list[str], java_results: dict[str, str]
) -> None:
    """pypdfbox's algorithm result matches PDFBox 3.0.7 byte-for-byte."""
    assert java_results[case_id] == _py_eval(op, fields)


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "op", "fields", "kind", "exc"),
    [(c[0], c[1], c[2], c[3], c[4]) for c in _PINNED_CASES],
    ids=[c[0] for c in _PINNED_CASES],
)
def test_pinned_divergences(
    case_id: str,
    op: str,
    fields: list[str],
    kind: str,
    exc: type[Exception] | None,
    java_results: dict[str, str],
) -> None:
    """Both sides are pinned: Java is ground truth, pypdfbox is the mapped /
    lenient behaviour. Asserting both halves keeps the divergence intentional —
    if either side's contract drifts, this test fails."""
    java = java_results[case_id]
    py = _py_eval(op, fields)
    if kind == "exc_map":
        # Java raised (any exception) and pypdfbox raised the mapped type.
        assert java.startswith("ERR:")
        assert py == "ERR:" + exc.__name__  # type: ignore[union-attr]
    elif kind == "java_crash":
        # Java crashed on an unguarded array slice; pypdfbox handled it.
        assert java == "ERR:ArrayIndexOutOfBoundsException"
        assert not py.startswith("ERR:")
    else:  # pragma: no cover - guard against a typo'd kind
        raise AssertionError(f"unknown pin kind {kind}")
