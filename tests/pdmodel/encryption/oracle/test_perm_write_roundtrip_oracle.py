"""Live Apache PDFBox differential parity for the permission WRITE round-trip.

The sibling ``test_encryption_interop_oracle`` cross-encrypts only with the
DEFAULT (all-allowed) ``AccessPermission``, and ``test_perm_owner_user_oracle``
pins the owner/user *read* split for a pypdfbox-written AES-128 file. Neither
proves that the ``/Encrypt /P`` integer pypdfbox *writes* for a deliberately
RESTRICTED permission set is byte-identical to what Apache PDFBox writes for the
same set — nor that each side reads the other's restricted ``/P`` back to the
same per-permission predicates, across both AES-128 V4 and AES-256 R6.

This module pins exactly that. A fixed restricted permission set (deny print /
modify / extract / fill-form / faithful-print; allow annotate / accessibility /
assemble) is written by *both* implementations; the on-disk ``/P`` and its full
predicate decode are compared:

* pypdfbox WRITES → ``PermWriteProbe wirep`` (PDFBox READS) — the bits PDFBox
  recovers from a pypdfbox-encrypted file equal the bits the Python
  ``AccessPermission`` carried.
* PDFBox WRITES (``PermWriteProbe write``) → pypdfbox READS — and vice versa.
* Direct write-output equality: both libraries serialise the *same* restricted
  set to the *same* signed two's-complement ``/P`` integer (-2336).

``wirep`` decodes ``PDEncryption.getPermissions()`` (the raw wire ``/P``)
independent of which password unlocked the file, so there is no owner-bit
upgrade or read-only masking to confound the comparison — it is the canonical
WRITE view.

Probe ``oracle/probes/PermWriteProbe.java``:

* ``write <in> <out> <ownerPw> <userPw> <keyLen> <preferAES>`` — encrypt with
  the fixed restricted policy.
* ``wirep <file> <password>`` — emit ``WIRE_P:<int>`` plus every predicate of
  ``new AccessPermission(WIRE_P)``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "ownerpw"
_USER_PW = "userpw"

# (id, key_length_bits, prefer_aes) — AES-128 V4 and AES-256 R6.
_ALGORITHMS = [
    ("aes_128", 128, True),
    ("aes_256", 256, True),
]

# The signed two's-complement /P integer the fixed restricted set encodes.
# Bits cleared: 3 (print), 4 (modify), 5 (extract), 9 (fill-form),
# 12 (faithful print). Bits set: 6 (annotate), 10 (accessibility),
# 11 (assemble), plus all reserved high bits per the spec.
_EXPECTED_WIRE_P = -2336

# Canonical predicate decode of the restricted set, as PermWriteProbe emits it.
_EXPECTED_PREDICATES = {
    "WIRE_P": str(_EXPECTED_WIRE_P),
    "canPrint": "false",
    "canModify": "false",
    "canExtractContent": "false",
    "canModifyAnnotations": "true",
    "canFillInForm": "false",
    "canExtractForAccessibility": "true",
    "canAssembleDocument": "true",
    "canPrintFaithful": "false",
}


# --------------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _restricted() -> AccessPermission:
    """Mirror PermWriteProbe.restricted() exactly."""
    ap = AccessPermission()
    ap.set_can_print(False)
    ap.set_can_modify(False)
    ap.set_can_extract_content(False)
    ap.set_can_fill_in_form(False)
    ap.set_can_print_faithful(False)
    ap.set_can_modify_annotations(True)
    ap.set_can_extract_for_accessibility(True)
    ap.set_can_assemble_document(True)
    return ap


def _py_write(out: Path, key_length: int, prefer_aes: bool) -> None:
    """Encrypt the fixture with the fixed restricted policy via pypdfbox."""
    doc = PDDocument.load(str(_FIXTURE))
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=_restricted(),
        )
        policy.set_encryption_key_length(key_length)
        policy.set_prefer_aes(prefer_aes)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _java_write(out: Path, key_length: int, prefer_aes: bool) -> None:
    run_probe(
        "PermWriteProbe",
        "write",
        str(_FIXTURE),
        str(out),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
    )


def _java_wirep(path: Path, password: str) -> dict[str, str]:
    """Run PermWriteProbe wirep and parse its WIRE_P + predicate lines."""
    raw = run_probe_text("PermWriteProbe", "wirep", str(path), password)
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("WIRE_P:"):
            out["WIRE_P"] = line[len("WIRE_P:") :]
        elif "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _py_wirep(path: Path, password: str) -> dict[str, str]:
    """Mirror PermWriteProbe wirep from a pypdfbox reload: decode the raw wire
    /P (independent of which password unlocked) into the same predicate map."""
    doc = PDDocument.load(str(path), password)
    try:
        enc = doc.get_encryption()
        wire_p = enc.get_permissions() if enc is not None else 0
    finally:
        doc.close()
    ap = AccessPermission(wire_p)

    def b(value: bool) -> str:
        return "true" if value else "false"

    return {
        "WIRE_P": str(wire_p),
        "canPrint": b(ap.can_print()),
        "canModify": b(ap.can_modify()),
        "canExtractContent": b(ap.can_extract_content()),
        "canModifyAnnotations": b(ap.can_modify_annotations()),
        "canFillInForm": b(ap.can_fill_in_form()),
        "canExtractForAccessibility": b(ap.can_extract_for_accessibility()),
        "canAssembleDocument": b(ap.can_assemble_document()),
        "canPrintFaithful": b(ap.can_print_faithful()),
    }


# ------------------------------------------------ restricted set encodes -2336


def test_restricted_set_encodes_expected_wire_p() -> None:
    """Pure pypdfbox: the fixed restricted permission set serialises to the
    documented signed two's-complement /P integer. No oracle needed — pins the
    bit arithmetic the round-trip tests rely on."""
    assert _restricted().get_permission_bytes() == _EXPECTED_WIRE_P


# ------------------------------------------------ pypdfbox writes → PDFBox reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_pypdfbox_writes_pdfbox_reads_wire_p(
    algo_id: str, key_length: int, prefer_aes: bool, password: str, tmp_path: Path
) -> None:
    """pypdfbox encrypts the restricted set; Apache PDFBox recovers the exact
    /P integer and every predicate, with either password."""
    _fixture_present()
    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_write(enc, key_length, prefer_aes)

    java = _java_wirep(enc, password)
    assert java == _EXPECTED_PREDICATES, f"PDFBox read divergence: {java}"


# ------------------------------------------------ PDFBox writes → pypdfbox reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
@pytest.mark.parametrize("password", [_USER_PW, _OWNER_PW], ids=["user", "owner"])
def test_pdfbox_writes_pypdfbox_reads_wire_p(
    algo_id: str, key_length: int, prefer_aes: bool, password: str, tmp_path: Path
) -> None:
    """Apache PDFBox encrypts the restricted set; pypdfbox recovers the exact
    /P integer and every predicate, with either password."""
    _fixture_present()
    enc = tmp_path / f"java_{algo_id}.pdf"
    _java_write(enc, key_length, prefer_aes)

    py = _py_wirep(enc, password)
    assert py == _EXPECTED_PREDICATES, f"pypdfbox read divergence: {py}"


# ------------------------------------------ cross-implementation write equality


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _ALGORITHMS,
    ids=[a[0] for a in _ALGORITHMS],
)
def test_both_implementations_write_identical_wire_p(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """The /P integer (and full predicate decode) is identical whether the
    restricted set was written by pypdfbox or by Apache PDFBox — the canonical
    cross-implementation WRITE-parity assertion. Each side reads the OTHER's
    file, proving the write halves agree byte-for-byte on /P."""
    _fixture_present()

    py_file = tmp_path / f"py_{algo_id}.pdf"
    java_file = tmp_path / f"java_{algo_id}.pdf"
    _py_write(py_file, key_length, prefer_aes)
    _java_write(java_file, key_length, prefer_aes)

    # Cross-read: pypdfbox reads the Java file, PDFBox reads the Python file.
    java_reads_py = _java_wirep(py_file, _USER_PW)
    py_reads_java = _py_wirep(java_file, _USER_PW)

    assert java_reads_py == py_reads_java == _EXPECTED_PREDICATES
    assert java_reads_py["WIRE_P"] == py_reads_java["WIRE_P"] == str(_EXPECTED_WIRE_P)
