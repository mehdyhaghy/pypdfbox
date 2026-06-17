"""Live Apache PDFBox differential FUZZ of ``AccessPermission`` (wave 1537).

The existing ``test_access_permission_oracle.py`` (driven by ``PermProbe``)
checks only the eight ``canXxx`` predicates plus ``isReadOnly`` /
``isOwnerPermission`` for a small ``/P`` sweep, and round-trips a single
restrictive set through encryption. It does NOT exercise the deeper bit-layout
surface that a malformed ``/P`` integer reaches:

* ``getPermissionBytes()`` — the verbatim stored int (Java signed-int
  semantics: an explicit ``-1`` stays ``-1``, NOT the no-arg DEFAULT ``-4``).
* ``getPermissionBytesForPublicKey()`` — the in-place mutation that sets bit 1,
  clears bits 7/8 and bits 13–32, then returns the raw int.
* ``setReadOnly()`` then a battery of ``setCanXxx`` flips (must be a no-op).
* the same ``setCanXxx`` flips WITHOUT the read-only lock (each mutates).

That is this wave's surface, driven by ``oracle/probes/AccessPermissionFuzzProbe``
across a wide battery of ``/P`` ints (zero, all-bits ``-1``, the common ``-44`` /
``-4``, single-bit patterns, the signed-int boundaries, reserved-bit combos).
Each Java line is ground truth; the pypdfbox ``AccessPermission`` built from the
same int must match every projected field.

Real bug fixed this wave (CHANGES.md): pypdfbox's constructor treated an
explicit ``-1`` as the no-arg DEFAULT sentinel and stored ``~3 == -4``, so
``AccessPermission(-1).get_permission_bytes()`` returned ``-4`` where PDFBox's
``new AccessPermission(-1)`` keeps ``-1``. The constructor now distinguishes the
no-arg case (``-4``) from an explicit integer (verbatim) via a private sentinel,
matching upstream's two separate constructors. With the fix the entire battery
is byte-for-byte identical — NO remaining divergence.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from tests.oracle.harness import requires_oracle, run_probe_text

# /P battery within Java's 32-bit signed int range (a real /P is read as a COS
# integer and used as a Java int upstream): all-bits, common Acrobat values,
# single-bit isolations, reserved-bit combos, and the signed boundaries.
_P_VALUES = [
    0,
    -1,
    -2,
    -3,
    -4,
    -44,
    4,
    8,
    16,
    32,
    64,
    128,
    192,
    256,
    512,
    1024,
    1536,
    2048,
    2052,
    -1024,
    -1052,
    -1537,
    -1900,
    -3904,
    -3905,
    7,
    1,
    3,
    255,
    65535,
    -256,
    -512,
    -65536,
    2147483647,
    -2147483648,
]

_SET_METHODS = [
    "print",
    "modify",
    "extract_content",
    "modify_annotations",
    "fill_in_form",
    "extract_for_accessibility",
    "assemble_document",
    "print_faithful",
]


def _py_projection(p: int) -> dict[str, str]:
    """Mirror AccessPermissionFuzzProbe's emission for a pypdfbox instance."""
    ap = AccessPermission(p)
    fields: list[tuple[str, object]] = [
        ("bytes", ap.get_permission_bytes()),
        ("canPrint", ap.can_print()),
        ("canModify", ap.can_modify()),
        ("canExtractContent", ap.can_extract_content()),
        ("canModifyAnnotations", ap.can_modify_annotations()),
        ("canFillInForm", ap.can_fill_in_form()),
        ("canExtractForAccessibility", ap.can_extract_for_accessibility()),
        ("canAssembleDocument", ap.can_assemble_document()),
        ("canPrintFaithful", ap.can_print_faithful()),
        ("isOwnerPermission", ap.is_owner_permission()),
        ("isReadOnly", ap.is_read_only()),
    ]

    pk = AccessPermission(p)
    fields.append(("pubKeyBytes", pk.get_permission_bytes_for_public_key()))

    ro = AccessPermission(p)
    ro.set_read_only()
    for name in _SET_METHODS:
        getattr(ro, f"set_can_{name}")(not getattr(ro, f"can_{name}")())
    fields.append(("roMutateBytes", ro.get_permission_bytes()))
    fields.append(("roStillReadOnly", ro.is_read_only()))

    rw = AccessPermission(p)
    for name in _SET_METHODS:
        getattr(rw, f"set_can_{name}")(not getattr(rw, f"can_{name}")())
    fields.append(("rwMutateBytes", rw.get_permission_bytes()))

    out: dict[str, str] = {}
    for key, value in fields:
        out[key] = ("true" if value else "false") if isinstance(value, bool) else str(value)
    return out


def _parse_probe(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


@requires_oracle
@pytest.mark.parametrize("p_value", _P_VALUES, ids=[str(p) for p in _P_VALUES])
def test_access_permission_fuzz_matches_pdfbox(p_value: int) -> None:
    """Every projected field of pypdfbox's ``AccessPermission`` equals Apache
    PDFBox's for the same ``/P`` int — bit decode, ``getPermissionBytes``,
    ``getPermissionBytesForPublicKey``, the read-only lock no-op, and the
    read-write ``setCanXxx`` mutations."""
    java = _parse_probe(run_probe_text("AccessPermissionFuzzProbe", str(p_value)))
    py = _py_projection(p_value)
    assert java, "probe produced no output"
    assert py == java, f"/P={p_value}: pypdfbox {py} != PDFBox {java}"
