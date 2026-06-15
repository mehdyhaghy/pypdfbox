"""Live PDFBox differential fuzz for PDMarkInfo (/MarkInfo) reads (wave 1533).

Drives PDMarkInfo's three boolean accessors (isMarked / isSuspect /
usesUserProperties over /Marked, /Suspects, /UserProperties — each default
false) across malformed value shapes (absent, present true/false, wrong type
int/name/string/array/dict/null, indirect refs), the empty/default dict, and
setter round-trips. The expected output is the live PDFBox 3.0.7 oracle
(MarkInfoFuzzProbe).

Divergence pinned both-sides: upstream ``setSuspect(boolean)`` ALWAYS writes
``false`` (a longstanding PDFBox bug — verified by decompiling 3.0.7, the
bytecode does ``iconst_0``). pypdfbox's ``set_suspect`` deliberately writes the
real argument (see CHANGES.md). The probe therefore exercises the *upstream*
``setSuspect`` and the Python dump below mirrors that upstream-bug result so the
read/coercion parity (the surface under test) is what is compared, not the
known mutator divergence.
"""

from __future__ import annotations

import json

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.documentinterchange.logicalstructure import PDMarkInfo
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_KEYS = ("Marked", "Suspects", "UserProperties")

_SHAPES = (
    "absent",
    "true",
    "false",
    "int1",
    "int0",
    "name_true",
    "string_true",
    "array",
    "dict",
    "null",
    "ind_true",
    "ind_false",
    "ind_null",
)


def _value(shape: str):
    if shape == "true":
        return COSBoolean.TRUE
    if shape == "false":
        return COSBoolean.FALSE
    if shape == "int1":
        return COSInteger.get(1)
    if shape == "int0":
        return COSInteger.get(0)
    if shape == "name_true":
        return _N("true")
    if shape == "string_true":
        return COSString("true")
    if shape == "array":
        return COSArray()
    if shape == "dict":
        return COSDictionary()
    if shape == "null":
        return COSNull.NULL
    if shape == "ind_true":
        return COSObject(1, 0, resolved=COSBoolean.TRUE)
    if shape == "ind_false":
        return COSObject(2, 0, resolved=COSBoolean.FALSE)
    if shape == "ind_null":
        return COSObject(3, 0, resolved=COSNull.NULL)
    raise AssertionError(f"unknown shape {shape}")


def _build_dict(shape: str) -> COSDictionary:
    d = COSDictionary()
    if shape != "absent":
        for key in _KEYS:
            d.set_item(_N(key), _value(shape))
    return d


def _read_record(mi: PDMarkInfo) -> dict:
    # is_suspect() reads /Suspects; uses_user_properties() reads /UserProperties.
    return {
        "isMarked": mi.is_marked(),
        "isSuspect": mi.is_suspect(),
        "usesUserProperties": mi.uses_user_properties(),
    }


def _py_dump() -> str:
    reads = {shape: _read_record(PDMarkInfo(_build_dict(shape))) for shape in _SHAPES}

    empty = PDMarkInfo()
    default = {
        "isMarked": empty.is_marked(),
        "isSuspect": empty.is_suspect(),
        "usesUserProperties": empty.uses_user_properties(),
        "cosEmpty": empty.get_cos_object().size() == 0,
    }

    setters = {}
    for value in (True, False):
        mi = PDMarkInfo()
        mi.set_marked(value)
        # Mirror the upstream setSuspect bug (always writes false) so the read
        # surface — not the known mutator divergence — is what's compared.
        mi.get_cos_object().set_boolean(_N("Suspects"), False)
        mi.set_user_properties(value)
        record = {
            "isMarked": mi.is_marked(),
            "isSuspect": mi.is_suspect(),
            "usesUserProperties": mi.uses_user_properties(),
        }
        mi.set_marked(not value)
        record["isMarkedFlip"] = mi.is_marked()
        setters[str(value).lower()] = record

    root = {"_default": default, "_reads": reads, "_setters": setters}
    return json.dumps(root, sort_keys=True, separators=(",", ":"))


@requires_oracle
def test_mark_info_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("MarkInfoFuzzProbe")
