"""Live Apache PDFBox differential parity for ``AccessPermission``.

The ``/P`` permission integer (PDF 32000-1 Table 22) is decoded bit-by-bit into
the eight can-* predicates plus the derived ``isOwnerPermission`` /
``isReadOnly`` flags. This module pins pypdfbox's decode against Apache PDFBox's
own ``AccessPermission(int)`` for a sweep of representative ``/P`` values, and
additionally round-trips a restrictive permission set through a pypdfbox
encryption so PDFBox reads back the exact same bits — proving ``/P`` is *written*
correctly, not merely decoded.

Two probe modes drive the oracle (``oracle/probes/PermProbe.java``):

* ``decode <pInt>`` — ``new AccessPermission(pInt)`` → canonical
  ``predicate=true|false`` lines.
* ``readback <file> <password>`` — open the encrypted PDF and emit
  ``doc.getCurrentAccessPermission()`` predicates.

Documented divergence: pypdfbox's ``AccessPermission(-1)`` stores ``~3`` (the
no-arg DEFAULT bits) rather than the literal ``-1`` PDFBox keeps for the
``int`` constructor. Every predicate is identical (both have all defined bits
set), only ``get_permission_bytes()`` differs; the predicate-set comparison
below is therefore exact for ``-1`` too. See CHANGES.md.
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

# Representative /P sweep: all-allowed (-1), the canonical "print + extract but
# no modify/annotate" value Acrobat writes (-44), nothing allowed (0), the
# DEFAULT bits (-3), and a handful of single-/mixed-bit patterns spanning the
# revision-2 and revision-3 bits.
_P_VALUES = [
    -1,
    -44,
    0,
    -3,
    -3904,  # only some high bits cleared
    -1052,  # print + extract, no modify, no annotations
    4,  # bit 3 only (print)
    2048,  # bit 12 only (faithful print)
    -2,  # all bits except reserved bit 1
    -4,
    -1900,
    2052,  # print + faithful only
]

# The predicate names PermProbe emits, in emission order.
_PREDICATES = [
    "canPrint",
    "canModify",
    "canExtractContent",
    "canFillInForm",
    "canAssembleDocument",
    "canPrintFaithful",
    "canExtractForAccessibility",
    "canModifyAnnotations",
    "isReadOnly",
    "isOwnerPermission",
]


def _py_predicates(ap: AccessPermission) -> dict[str, bool]:
    """Mirror PermProbe's predicate emission from a pypdfbox AccessPermission."""
    return {
        "canPrint": ap.can_print(),
        "canModify": ap.can_modify(),
        "canExtractContent": ap.can_extract_content(),
        "canFillInForm": ap.can_fill_in_form(),
        "canAssembleDocument": ap.can_assemble_document(),
        "canPrintFaithful": ap.can_print_faithful(),
        "canExtractForAccessibility": ap.can_extract_for_accessibility(),
        "canModifyAnnotations": ap.can_modify_annotations(),
        "isReadOnly": ap.is_read_only(),
        "isOwnerPermission": ap.is_owner_permission(),
    }


def _parse_probe(raw: str) -> dict[str, bool]:
    """Parse PermProbe's ``name=true|false`` lines into a predicate dict
    (drops the leading ``permissionBytes=`` line, which is not a predicate)."""
    out: dict[str, bool] = {}
    for line in raw.splitlines():
        if not line or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name in _PREDICATES:
            out[name] = value == "true"
    return out


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


# --------------------------------------------------------------- bit decode


@requires_oracle
@pytest.mark.parametrize("p_value", _P_VALUES, ids=[str(p) for p in _P_VALUES])
def test_access_permission_decode_matches_pdfbox(p_value: int) -> None:
    """For every representative ``/P`` value, pypdfbox's predicate set equals
    Apache PDFBox's ``AccessPermission(int)`` predicate set exactly."""
    java = _parse_probe(run_probe_text("PermProbe", "decode", str(p_value)))
    py = _py_predicates(AccessPermission(p_value))
    assert set(java) == set(_PREDICATES)
    assert py == java, f"/P={p_value}: pypdfbox {py} != PDFBox {java}"


# ------------------------------------------------------------- /P round-trip


@requires_oracle
def test_restrictive_permissions_round_trip_to_pdfbox(tmp_path: Path) -> None:
    """End-to-end: pypdfbox encrypts with a restrictive permission set; Apache
    PDFBox reloads and reports the SAME predicates — proves ``/P`` is written
    correctly, not just decoded.

    Restriction profile: deny modify, deny content extraction, deny annotation
    edits, deny assembly; allow print + form fill + accessibility extraction.
    """
    _fixture_present()

    perms = AccessPermission()
    perms.set_can_modify(False)
    perms.set_can_extract_content(False)
    perms.set_can_modify_annotations(False)
    perms.set_can_assemble_document(False)
    perms.set_can_print(True)
    perms.set_can_fill_in_form(True)
    perms.set_can_extract_for_accessibility(True)
    perms.set_can_print_faithful(True)

    expected = _py_predicates(perms)

    enc = tmp_path / "restricted.pdf"
    doc = PDDocument.load(str(_FIXTURE))
    try:
        policy = StandardProtectionPolicy(
            owner_password="ownerpw",
            user_password="userpw",
            permissions=perms,
        )
        policy.set_encryption_key_length(128)
        policy.set_prefer_aes(True)
        doc.protect(policy)
        doc.save(str(enc))
    finally:
        doc.close()

    # PDFBox opens with the USER password — the user view reflects the written
    # /P bits (the owner password would unlock full owner permissions).
    java = _parse_probe(run_probe_text("PermProbe", "readback", str(enc), "userpw"))

    # The eight can-* predicates must round-trip identically. isOwnerPermission
    # is a derived flag and, under the user password on a restricted file, is
    # naturally False on both sides; isReadOnly is set by PDFBox on the loaded
    # document (it is the already-applied policy) and is not part of the /P
    # wire value, so it is excluded from the round-trip comparison.
    can_keys = [k for k in _PREDICATES if k.startswith("can")]
    java_can = {k: java[k] for k in can_keys}
    expected_can = {k: expected[k] for k in can_keys}
    assert java_can == expected_can, (
        f"round-trip /P mismatch: PDFBox {java_can} != written {expected_can}"
    )


@requires_oracle
def test_all_allowed_round_trip_to_pdfbox(tmp_path: Path) -> None:
    """A default (all-allowed) permission set written by pypdfbox reads back in
    PDFBox with every can-* predicate true under the owner password."""
    _fixture_present()

    enc = tmp_path / "allowed.pdf"
    doc = PDDocument.load(str(_FIXTURE))
    try:
        policy = StandardProtectionPolicy(
            owner_password="ownerpw",
            user_password="userpw",
            permissions=AccessPermission(),
        )
        policy.set_encryption_key_length(128)
        policy.set_prefer_aes(True)
        doc.protect(policy)
        doc.save(str(enc))
    finally:
        doc.close()

    java = _parse_probe(run_probe_text("PermProbe", "readback", str(enc), "ownerpw"))
    can_keys = [k for k in _PREDICATES if k.startswith("can")]
    assert all(java[k] for k in can_keys), f"expected all-allowed, got {java}"
    # Owner password → owner permission view.
    assert java["isOwnerPermission"] is True
