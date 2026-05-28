"""Live Apache PDFBox differential parity for the OWNER-vs-USER access split.

``StandardSecurityHandler#prepareForDecryption`` installs a different
``AccessPermission`` on the live document depending on *which* password
authenticated (PDF 32000-1 §7.6.4.4 / PDFBox):

* OWNER password  → ``AccessPermission.getOwnerAccessPermission()`` — every
  DEFAULT bit set (raw ``getPermissionBytes()`` == ``0xFFFFFFFC`` == ``-4``),
  ``isOwnerPermission()`` true, **not** read-only.
* USER password   → ``new AccessPermission(/P)`` with ``setReadOnly()`` applied
  — raw bytes equal the on-disk ``/P`` integer, ``isReadOnly()`` true,
  ``isOwnerPermission()`` reflects the actual ``/P`` bits.

The sibling ``test_access_permission_oracle`` pins the pure bit *decode* and a
*predicate-only* round-trip; it deliberately EXCLUDES the raw permission integer
and the ``isReadOnly`` / ``isOwnerPermission`` flags. This module pins exactly
those three excluded values, for both passwords, against the live oracle — so
pypdfbox's owner/user permission view matches Apache PDFBox byte-for-byte,
including the signed two's-complement ``/P`` written to the ``/Encrypt`` dict.

Probe ``oracle/probes/PermOwnerUserProbe.java``:

* ``inspect <file> <password>`` → ``WIRE_P``, ``CUR_BYTES``, ``CUR_READONLY``,
  ``CUR_OWNER`` lines from the reloaded encrypted document.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "ownerpw"
_USER_PW = "userpw"


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _parse_probe(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key] = value
    return out


def _make_restricted(tmp_path: Path) -> Path:
    """Encrypt the fixture with a deliberately restrictive /P so the owner and
    user views diverge: deny modify / extract / annotate / assemble, allow the
    rest."""
    perms = AccessPermission()
    perms.set_can_modify(False)
    perms.set_can_extract_content(False)
    perms.set_can_modify_annotations(False)
    perms.set_can_assemble_document(False)
    perms.set_can_print(True)
    perms.set_can_fill_in_form(True)
    perms.set_can_extract_for_accessibility(True)
    perms.set_can_print_faithful(True)

    enc = tmp_path / "owner_user.pdf"
    doc = PDDocument.load(str(_FIXTURE))
    try:
        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PW,
            user_password=_USER_PW,
            permissions=perms,
        )
        policy.set_encryption_key_length(128)
        policy.set_prefer_aes(True)
        doc.protect(policy)
        doc.save(str(enc))
    finally:
        doc.close()
    return enc


def _py_inspect(path: Path, password: str) -> dict[str, str]:
    """Mirror PermOwnerUserProbe's emission from a pypdfbox reload."""
    doc = PDDocument.load(str(path), password)
    try:
        enc = doc.get_encryption()
        wire_p = enc.get_permissions() if enc is not None else 0
        ap = doc.get_current_access_permission()
        return {
            "WIRE_P": str(wire_p),
            "CUR_BYTES": str(ap.get_permission_bytes()),
            "CUR_READONLY": "true" if ap.is_read_only() else "false",
            "CUR_OWNER": "true" if ap.is_owner_permission() else "false",
        }
    finally:
        doc.close()


# ----------------------------------------------------------- owner password


@requires_oracle
def test_owner_password_permission_view_matches_pdfbox(tmp_path: Path) -> None:
    """Under the OWNER password the live view is full DEFAULT bits (-4),
    owner-permission true, NOT read-only — and pypdfbox agrees with PDFBox on
    all four emitted values, including the raw on-disk /P."""
    _fixture_present()
    enc = _make_restricted(tmp_path)

    java = _parse_probe(run_probe_text("PermOwnerUserProbe", "inspect", str(enc), _OWNER_PW))
    py = _py_inspect(enc, _OWNER_PW)

    assert py == java, f"owner view mismatch: pypdfbox {py} != PDFBox {java}"
    # Pin the documented owner semantics explicitly.
    assert java["CUR_OWNER"] == "true"
    assert java["CUR_READONLY"] == "false"
    assert java["CUR_BYTES"] == "-4"


# ------------------------------------------------------------ user password


@requires_oracle
def test_user_password_permission_view_matches_pdfbox(tmp_path: Path) -> None:
    """Under the USER password the live view equals the on-disk /P bits,
    read-only true, owner-permission false (the /P is restrictive) — pypdfbox
    matches PDFBox on all four values."""
    _fixture_present()
    enc = _make_restricted(tmp_path)

    java = _parse_probe(run_probe_text("PermOwnerUserProbe", "inspect", str(enc), _USER_PW))
    py = _py_inspect(enc, _USER_PW)

    assert py == java, f"user view mismatch: pypdfbox {py} != PDFBox {java}"
    # Pin the documented user semantics explicitly.
    assert java["CUR_READONLY"] == "true"
    assert java["CUR_OWNER"] == "false"
    # User view raw bytes equal the wire /P value (no DEFAULT-bit upgrade).
    assert java["CUR_BYTES"] == java["WIRE_P"]


@requires_oracle
def test_wire_p_round_trips_for_both_passwords(tmp_path: Path) -> None:
    """The /Encrypt /P integer on disk is independent of the unlocking
    password: PDFBox reads the same WIRE_P with owner and user passwords, and
    pypdfbox writes/reads that same value."""
    _fixture_present()
    enc = _make_restricted(tmp_path)

    owner = _parse_probe(
        run_probe_text("PermOwnerUserProbe", "inspect", str(enc), _OWNER_PW)
    )
    user = _parse_probe(
        run_probe_text("PermOwnerUserProbe", "inspect", str(enc), _USER_PW)
    )
    assert owner["WIRE_P"] == user["WIRE_P"]

    py_owner = _py_inspect(enc, _OWNER_PW)
    py_user = _py_inspect(enc, _USER_PW)
    assert py_owner["WIRE_P"] == owner["WIRE_P"]
    assert py_user["WIRE_P"] == user["WIRE_P"]
