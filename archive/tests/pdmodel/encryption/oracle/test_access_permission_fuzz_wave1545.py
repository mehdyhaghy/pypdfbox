"""Live Apache PDFBox differential fuzz of the ``PDEncryption`` integer
accessors (``/V /R /Length /P``) + the ``AccessPermission`` factory / byte[]
surface (wave 1545, agent B).

This wave's surface is DISTINCT from the two adjacent encryption fuzz tests:

* ``test_access_permission_fuzz_wave1537.py`` (driven by
  ``AccessPermissionFuzzProbe``) deep-fuzzes a single ``AccessPermission(int)``
  bit layout + the read-only lock — it never touches a ``PDEncryption`` dict.
* ``test_encrypt_dict_fuzz_wave1511.py`` (driven by ``EncryptDictFuzzProbe``)
  is FILE-based: it writes mutated ``/Encrypt`` PDFs to disk and compares the
  whole open contract.

Here we drive ``EncryptDictAccessorFuzzProbe`` IN-PROCESS to pin the DECODE
layer those skip: how ``PDEncryption``'s integer accessors coerce a malformed
``/V /R /Length /P`` COS value, how the decoded ``/P`` flows into an
``AccessPermission``, and the factory + byte-array constructors
(``get_owner_access_permission``, no-arg, ``from_bytes``) that wave 1537 never
projected.

Findings pinned BOTH-SIDES (Java == Python on every case):

* ``/P`` as a ``COSFloat`` truncates toward zero (``-3.9 -> -3``, ``2052.8 ->
  2052``) — Python's ``get_int`` routes ``COSFloat`` through ``int_value()``
  which matches Java's ``COSNumber.intValue()``.
* a 64-bit ``/P`` / ``/R`` / ``/V`` wraps to a Java 32-bit signed int
  (``9999999999 -> 1410065407``) — Python's ``get_int`` applies the same
  ``((v + 2**31) % 2**32) - 2**31`` fold.
* a wrong-typed ``/P`` / ``/V`` / ``/Length`` / ``/R`` (name, bool, string)
  falls back to the spec default (``/P`` -> 0, ``/V`` -> 0, ``/R`` -> 0,
  ``/Length`` -> 40) on BOTH sides.
* ``AccessPermission(byte[])`` reads exactly the first four bytes MSB-first and
  IGNORES any trailing bytes (``{0,0,0,4,9} -> 4``; ``{0,0,0,0,0,0,0,4} ->
  0``); ``from_bytes`` slices ``b[:4]`` and matches.

HONEST DIVERGENCE (one, exception class only — both sides still REJECT):
a byte buffer shorter than 4 bytes is rejected by both, but Java raises
``ArrayIndexOutOfBoundsException`` while pypdfbox's ``from_bytes`` raises
``ValueError`` (it length-checks before slicing). The probe emits
``status=ERR:<class>`` so the cross-runtime class name differs; the test
therefore compares only the boolean "did it reject", not the class name.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from tests.oracle.harness import requires_oracle, run_probe_text


def _set(d: COSDictionary, key: str, value: object) -> None:
    d.set_item(COSName.get_pdf_name(key), value)


def _build_dict(name: str) -> COSDictionary:
    """Re-create the EncryptDictAccessorFuzzProbe DICT corpus in pypdfbox."""
    d = COSDictionary()
    if name == "empty":
        return d
    if name == "well_formed_r4":
        _set(d, "V", COSInteger.get(4))
        _set(d, "R", COSInteger.get(4))
        _set(d, "Length", COSInteger.get(128))
        _set(d, "P", COSInteger.get(-44))
    elif name == "p_all_clear":
        _set(d, "P", COSInteger.get(0))
    elif name == "p_all_set":
        _set(d, "P", COSInteger.get(-1))
    elif name == "p_default_minus4":
        _set(d, "P", COSInteger.get(-4))
    elif name == "p_only_print":
        _set(d, "P", COSInteger.get(4))
    elif name == "p_only_modify":
        _set(d, "P", COSInteger.get(8))
    elif name == "p_reserved_bits":
        _set(d, "P", COSInteger.get(3))
    elif name == "p_float_neg44":
        _set(d, "P", COSFloat(-44.0))
    elif name == "p_float_frac":
        _set(d, "P", COSFloat(-3.9))
    elif name == "p_float_pos_frac":
        _set(d, "P", COSFloat(2052.8))
    elif name == "p_huge_64bit":
        _set(d, "P", COSInteger.get(9999999999))
    elif name == "p_name_wrongtype":
        _set(d, "P", COSName.get_pdf_name("foo"))
    elif name == "p_bool_wrongtype":
        _set(d, "P", COSBoolean.TRUE)
    elif name == "p_string_wrongtype":
        _set(d, "P", COSString("123"))
    elif name == "v_float":
        _set(d, "V", COSFloat(4.0))
    elif name == "v_name_wrongtype":
        _set(d, "V", COSName.get_pdf_name("Standard"))
    elif name == "v_huge_64bit":
        _set(d, "V", COSInteger.get(9999999999))
    elif name == "length_float":
        _set(d, "Length", COSFloat(128.0))
    elif name == "length_frac":
        _set(d, "Length", COSFloat(127.6))
    elif name == "length_zero":
        _set(d, "Length", COSInteger.get(0))
    elif name == "length_name_wrongtype":
        _set(d, "Length", COSName.get_pdf_name("128"))
    elif name == "r_float":
        _set(d, "R", COSFloat(6.0))
    elif name == "r_huge_64bit":
        _set(d, "R", COSInteger.get(9999999999))
    elif name == "r_string_wrongtype":
        _set(d, "R", COSString("6"))
    elif name == "all_wrongtype":
        _set(d, "V", COSName.get_pdf_name("x"))
        _set(d, "R", COSBoolean.FALSE)
        _set(d, "Length", COSString("y"))
        _set(d, "P", COSName.get_pdf_name("z"))
    else:  # pragma: no cover - defensive
        raise AssertionError(f"unknown dict case {name}")
    return d


_DICT_CASES = [
    "empty",
    "well_formed_r4",
    "p_all_clear",
    "p_all_set",
    "p_default_minus4",
    "p_only_print",
    "p_only_modify",
    "p_reserved_bits",
    "p_float_neg44",
    "p_float_frac",
    "p_float_pos_frac",
    "p_huge_64bit",
    "p_name_wrongtype",
    "p_bool_wrongtype",
    "p_string_wrongtype",
    "v_float",
    "v_name_wrongtype",
    "v_huge_64bit",
    "length_float",
    "length_frac",
    "length_zero",
    "length_name_wrongtype",
    "r_float",
    "r_huge_64bit",
    "r_string_wrongtype",
    "all_wrongtype",
]


def _b(v: bool) -> str:
    return "true" if v else "false"


def _ap_matrix(ap: AccessPermission) -> list[tuple[str, str]]:
    return [
        ("canPrint", _b(ap.can_print())),
        ("canModify", _b(ap.can_modify())),
        ("canExtractContent", _b(ap.can_extract_content())),
        ("canModifyAnnotations", _b(ap.can_modify_annotations())),
        ("canFillInForm", _b(ap.can_fill_in_form())),
        ("canExtractForAccessibility", _b(ap.can_extract_for_accessibility())),
        ("canAssembleDocument", _b(ap.can_assemble_document())),
        ("canPrintFaithful", _b(ap.can_print_faithful())),
        ("isOwnerPermission", _b(ap.is_owner_permission())),
    ]


def _py_dict_projection(name: str) -> dict[str, str]:
    enc = PDEncryption(_build_dict(name))
    p = enc.get_permissions()
    ap = AccessPermission(p)
    fields: list[tuple[str, object]] = [
        ("V", enc.get_version()),
        ("R", enc.get_revision()),
        ("Length", enc.get_length()),
        ("P", p),
        ("bytes", ap.get_permission_bytes()),
        *_ap_matrix(ap),
    ]
    return {k: str(v) for k, v in fields}


def _parse(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


@requires_oracle
@pytest.mark.parametrize("case", _DICT_CASES, ids=_DICT_CASES)
def test_encryption_dict_accessor_fuzz_matches_pdfbox(case: str) -> None:
    """Every ``PDEncryption`` integer accessor + the decoded ``/P`` ->
    ``AccessPermission`` predicate matrix equals Apache PDFBox's for a malformed
    ``/Encrypt`` dictionary."""
    java = _parse(run_probe_text("EncryptDictAccessorFuzzProbe", "DICT", case))
    assert java, f"probe produced no output for {case}"
    py = _py_dict_projection(case)
    assert py == java, f"DICT {case}: pypdfbox {py} != PDFBox {java}"


# ---------------------------------------------------------------- AP factories

# The "byte_empty" / "byte_one" / "byte_three" cases REJECT on both sides but
# with a different exception class (see module docstring) — they are handled by
# the status-only assertion below, not the full-projection one.
_AP_OK_CASES = [
    "owner_factory",
    "no_arg",
    "byte_fffffffc",
    "byte_zero",
    "byte_ffffffff",
    "byte_only_print",
    "byte_7fffffff",
    "byte_80000000",
    "byte_five_extra",
    "byte_eight",
]

_AP_REJECT_CASES = ["byte_empty", "byte_one", "byte_three"]

# Map each AP case to a thunk that builds the pypdfbox AccessPermission the
# probe builds. byte_* cases go through from_bytes (the AccessPermission(byte[])
# mirror); the short ones raise and are exercised separately.
_AP_BYTES = {
    "byte_fffffffc": bytes([0xFF, 0xFF, 0xFF, 0xFC]),
    "byte_zero": bytes([0, 0, 0, 0]),
    "byte_ffffffff": bytes([0xFF, 0xFF, 0xFF, 0xFF]),
    "byte_only_print": bytes([0, 0, 0, 4]),
    "byte_7fffffff": bytes([0x7F, 0xFF, 0xFF, 0xFF]),
    "byte_80000000": bytes([0x80, 0, 0, 0]),
    "byte_five_extra": bytes([0, 0, 0, 4, 9]),
    "byte_eight": bytes([0, 0, 0, 0, 0, 0, 0, 4]),
    "byte_empty": bytes([]),
    "byte_one": bytes([0x04]),
    "byte_three": bytes([0, 0, 4]),
}


def _py_ap(case: str) -> AccessPermission:
    if case == "owner_factory":
        return AccessPermission.get_owner_access_permission()
    if case == "no_arg":
        return AccessPermission()
    return AccessPermission.from_bytes(_AP_BYTES[case])


def _py_ap_projection(case: str) -> dict[str, str]:
    ap = _py_ap(case)
    fields: list[tuple[str, str]] = [
        ("status", "ok"),
        ("bytes", str(ap.get_permission_bytes())),
        ("canPrint", _b(ap.can_print())),
        ("canModify", _b(ap.can_modify())),
        ("canExtractContent", _b(ap.can_extract_content())),
        ("canAssembleDocument", _b(ap.can_assemble_document())),
        ("canPrintFaithful", _b(ap.can_print_faithful())),
        ("isOwnerPermission", _b(ap.is_owner_permission())),
    ]
    return dict(fields)


@requires_oracle
@pytest.mark.parametrize("case", _AP_OK_CASES, ids=_AP_OK_CASES)
def test_access_permission_factory_matches_pdfbox(case: str) -> None:
    """``getOwnerAccessPermission`` / no-arg / ``AccessPermission(byte[])``
    project byte-for-byte identically to Apache PDFBox — including the byte[]
    ctor reading exactly the first four bytes and ignoring the rest."""
    java = _parse(run_probe_text("EncryptDictAccessorFuzzProbe", "AP", case))
    assert java, f"probe produced no output for {case}"
    # The factory cases emit no `status` line; normalise so the two dicts align.
    java.setdefault("status", "ok")
    py = _py_ap_projection(case)
    assert py == java, f"AP {case}: pypdfbox {py} != PDFBox {java}"


@requires_oracle
@pytest.mark.parametrize("case", _AP_REJECT_CASES, ids=_AP_REJECT_CASES)
def test_access_permission_short_bytes_rejected_both_sides(case: str) -> None:
    """A byte buffer shorter than four bytes is REJECTED on both sides.

    Honest divergence (exception class only): Java's ``AccessPermission(byte[])``
    indexes past the end -> ``ArrayIndexOutOfBoundsException``; pypdfbox's
    ``from_bytes`` length-checks first -> ``ValueError``. Both REJECT, which is
    the contract under test; the class name legitimately differs across
    runtimes, so we assert only that each side raised."""
    java = _parse(run_probe_text("EncryptDictAccessorFuzzProbe", "AP", case))
    assert java.get("status", "").startswith("ERR:"), (
        f"AP {case}: expected PDFBox to reject, got {java}"
    )
    with pytest.raises((ValueError, IndexError)):
        AccessPermission.from_bytes(_AP_BYTES[case])
