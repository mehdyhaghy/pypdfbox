"""Live PDFBox differential parity for COSArray + COSDictionary CONTAINER
operations under MALFORMED / EDGE input — the fuzz complement to the existing
``CosArray*`` / ``CosDict*`` oracle suites.

Drives Apache PDFBox 3.0.7 (via the ``CosContainerOpsFuzzProbe`` Java oracle)
across the container-operation corners those suites do not exercise, then
asserts pypdfbox produces byte-identical results:

* **COSArray deref ASYMMETRY** — ``get_int`` / ``get_name`` / ``get_string``
  read the *raw* entry (an indirect ``COSObject`` falls through to the default),
  while ``get_object`` and ``to_float_array`` dereference it. Upstream
  ``COSArray`` has NO ``getFloat(int)`` / ``getBoolean(int)`` (verified against
  the 3.0.7 jar bytecode: only ``getInt`` / ``getName`` / ``getString`` typed
  index-accessors exist), so pypdfbox's ``get_float`` / ``get_boolean`` are
  extensions and are pinned Python-side only with a divergence note below.
* **growToSize corner sizes** — smaller-than-current (no shrink), equal,
  zero / negative (no-op), null padding read back through ``get_int`` (default)
  and ``get_object`` (``None``), and an explicit fill instance read back.
* **mutation edges** — ``remove(int)`` out-of-range throws ``IndexError``
  (Java ``IndexOutOfBoundsException``); ``remove(COSBase)`` of an indirect
  element matches on the *raw* entry only (the inner target of a ``COSObject``
  wrapper is NOT removed); ``set_int`` past the end throws (no auto-grow);
  ``set(i, None)`` reads back as a ``None`` slot.
* **COSDictionary numeric coercion** — ``get_int`` / ``get_long`` / ``get_float``
  over an INDIRECT ``COSObject`` wrapping a ``COSFloat`` (deref + truncate /
  narrow toward zero); a numeric-looking ``COSString`` is NOT coerced.
* **COSDictionary container accessors** — ``get_cos_array`` returns ``None`` for
  a single (non-array) value but the array for a direct or indirect array;
  ``get_cos_dictionary`` returns ``None`` for an array; ``get_cos_name`` returns
  the explicit default when absent.
* **flags / dates** — ``set_flag`` / ``get_flag`` round-trip on a previously
  absent key; ``get_flag`` over a missing key is ``False``; ``get_date`` over
  wrong-type values (int, name) returns ``None`` while a real PDF-date
  ``COSString`` parses.

Floats are compared as their IEEE-754 single-precision bit pattern so the
assertion is repr-independent.
"""

from __future__ import annotations

import json
import struct

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text

_OBJ = 1  # rolling object number for indirect COSObject wrappers


def _ind(resolved: COSBase) -> COSObject:
    """Build a dereferenced indirect ``COSObject`` wrapping ``resolved``."""
    global _OBJ
    _OBJ += 1
    return COSObject(_OBJ, 0, resolved=resolved)


def _fbits_hex(value: float) -> str:
    """IEEE-754 single-precision bit pattern, lowercase hex with no leading
    zeros — matches Java ``Integer.toHexString(Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", float(value)))[0]
    return f"{bits:x}"


def _f32(value: float) -> float:
    """Round a Python double to float32 so coercions through ``COSFloat`` match
    the single-precision values upstream reads back."""
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def _type_tag(b: COSBase | None) -> str:
    """Coarse type tag mirroring the Java probe's ``typeTag``."""
    if b is None:
        return "null"
    if isinstance(b, COSObject):
        return "object"
    # COSNull handled by identity in pypdfbox; the probe never emits cosnull here.
    if isinstance(b, COSInteger):
        return f"int:{b.long_value()}"
    if isinstance(b, COSFloat):
        return f"float:{_fbits_hex(b.float_value())}"
    if isinstance(b, COSString):
        return f"string:{b.get_string()}"
    if isinstance(b, COSName):
        return f"name:{b.name}"
    if isinstance(b, COSBoolean):
        return f"bool:{str(b.value).lower()}"
    if isinstance(b, COSArray):
        return "array"
    if isinstance(b, COSDictionary):
        return "dict"
    return f"other:{type(b).__name__}"


def _tok(b: COSBase | None) -> str:
    """Raw-entry token mirroring the Java probe's ``tok`` (used by ``dump``)."""
    if b is None:
        return "null"
    if isinstance(b, COSInteger):
        return f"int:{b.long_value()}"
    if isinstance(b, COSFloat):
        return f"float:{_fbits_hex(b.float_value())}"
    if isinstance(b, COSName):
        return f"name:{b.name}"
    if isinstance(b, COSString):
        return f"str:{b.get_string()}"
    return type(b).__name__


def _dump(a: COSArray) -> str:
    return "[" + ",".join(_tok(a.get(i)) for i in range(a.size())) + "]"


def _array_deref_asym() -> dict[str, object]:
    a = COSArray()
    a.add(_ind(COSInteger.get(77)))            # 0 indirect -> int
    a.add(_ind(COSFloat(_f32(2.5))))           # 1 indirect -> float
    a.add(_ind(COSBoolean.TRUE))               # 2 indirect -> bool
    a.add(_ind(COSString("ind")))              # 3 indirect -> string
    a.add(_ind(COSName.get_pdf_name("N")))     # 4 indirect -> name
    a.add(COSName.get_pdf_name("Bare"))        # 5 wrong type
    out: dict[str, object] = {}
    for i in range(a.size()):
        out[str(i)] = {
            "getInt": a.get_int(i),
            "getName": a.get_name(i),
            "getString": a.get_string(i),
            "get": _type_tag(a.get(i)),
            "getObject": _type_tag(a.get_object(i)),
        }
    out["toFloatArray"] = [_fbits_hex(v) for v in a.to_float_array()]
    return out


def _array_grow() -> dict[str, object]:
    a = COSArray()
    a.add(COSInteger.get(5))
    a.grow_to_size(3)
    rec: dict[str, object] = {
        "nullPad_size": a.size(),
        "nullPad_getInt_tail": a.get_int(2),
        "nullPad_getInt_tail_def": a.get_int(2, 8),
        "nullPad_getObject_tail": _type_tag(a.get_object(2)),
    }
    a.grow_to_size(3)
    rec["equal_size"] = a.size()
    a.grow_to_size(1)
    rec["smaller_size"] = a.size()

    z = COSArray()
    z.grow_to_size(0)
    rec["zero_size"] = z.size()
    z.grow_to_size(-4)
    rec["negative_size"] = z.size()

    f = COSArray()
    f.grow_to_size(2, COSInteger.get(9))
    rec["fill_size"] = f.size()
    rec["fill_getInt0"] = f.get_int(0)
    rec["fill_getInt1"] = f.get_int(1)
    rec["fill_tail_tag"] = _type_tag(f.get(1))
    return rec


def _array_mutate() -> dict[str, object]:
    rec: dict[str, object] = {}

    a = COSArray()
    a.add(COSInteger.get(1))
    try:
        a.remove_at(5)
        rec["removeInt_oob"] = "no-throw"
    except IndexError:
        rec["removeInt_oob"] = "throws:oob"  # IndexError ~ IndexOutOfBoundsException

    b = COSArray()
    b.add(COSInteger.get(1))
    b.add(COSInteger.get(2))
    b.add(COSInteger.get(3))
    removed = b.remove_at(1)
    rec["removeInt_ret"] = _type_tag(removed)
    rec["removeInt_after"] = _dump(b)

    # remove(COSBase) matches the raw entry only — the inner target of a
    # COSObject wrapper is NOT dereferenced, so removing the inner int misses.
    c = COSArray()
    inner = COSInteger.get(42)
    c.add(_ind(inner))
    rec["removeObj_innerOfIndirect"] = c.remove(inner)
    rec["removeObj_innerOfIndirect_size"] = c.size()

    d = COSArray()
    wrap = _ind(COSInteger.get(7))
    d.add(wrap)
    rec["removeObj_wrapper"] = d.remove(wrap)
    rec["removeObj_wrapper_size"] = d.size()

    e = COSArray()
    e.add(COSInteger.get(0))
    try:
        e.set_int(3, 9)
        rec["setInt_pastEnd"] = "no-throw|" + _dump(e)
    except IndexError:
        rec["setInt_pastEnd"] = "throws:oob"

    g = COSArray()
    g.add(COSInteger.get(1))
    g.set(0, None)  # type: ignore[arg-type]
    rec["setNull_get"] = _type_tag(g.get(0))
    rec["setNull_getInt"] = g.get_int(0)
    return rec


def _dict_numeric() -> dict[str, object]:
    d = COSDictionary()
    d.set_item("IndFloat", _ind(COSFloat(_f32(3.9))))
    d.set_item("IndNegFloat", _ind(COSFloat(_f32(-3.9))))
    d.set_item("IndInt", _ind(COSInteger.get(123)))
    d.set_item("NumStr", COSString("456"))
    d.set_item("DirFloat", COSFloat(_f32(7.6)))
    return {
        "indFloat_getInt": d.get_int("IndFloat"),
        "indFloat_getLong": d.get_long("IndFloat"),
        "indFloat_getFloat": _fbits_hex(d.get_float("IndFloat")),
        "indNegFloat_getInt": d.get_int("IndNegFloat"),
        "indInt_getInt": d.get_int("IndInt"),
        "numStr_getInt": d.get_int("NumStr"),
        "numStr_getInt_def": d.get_int("NumStr", 11),
        "numStr_getFloat": _fbits_hex(d.get_float("NumStr")),
        "dirFloat_getInt": d.get_int("DirFloat"),
    }


def _dict_containers() -> dict[str, object]:
    d = COSDictionary()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    d.set_item("Arr", arr)
    d.set_item("Single", COSInteger.get(5))
    d.set_item("Sub", COSDictionary())
    d.set_item("IndArr", _ind(arr))
    return {
        "getCOSArray_arr": "null" if d.get_cos_array("Arr") is None else "array",
        "getCOSArray_single": "null" if d.get_cos_array("Single") is None else "array",
        "getCOSArray_absent": "null" if d.get_cos_array("Absent") is None else "array",
        "getCOSArray_indArr": "null" if d.get_cos_array("IndArr") is None else "array",
        "getCOSDictionary_sub": "null" if d.get_cos_dictionary("Sub") is None else "dict",
        "getCOSDictionary_arr": "null" if d.get_cos_dictionary("Arr") is None else "dict",
        "getCOSName_single": "null" if d.get_cos_name("Single") is None else "name",
        "getCOSName_absent_def": (
            None
            if d.get_cos_name("Absent", COSName.get_pdf_name("FALLBACK")) is None
            else d.get_cos_name("Absent", COSName.get_pdf_name("FALLBACK")).name
        ),
    }


def _dict_flags_date() -> dict[str, object]:
    d = COSDictionary()
    d.set_flag("F", 0x04, True)
    rec: dict[str, object] = {
        "setFlag_value": d.get_int("F"),
        "getFlag_set": d.get_flag("F", 0x04),
        "getFlag_unset": d.get_flag("F", 0x02),
    }
    d.set_flag("F", 0x04, False)
    rec["setFlag_clear_value"] = d.get_int("F")
    rec["getFlag_missing"] = d.get_flag("Missing", 0x01)

    dd = COSDictionary()
    dd.set_item("NotDate", COSInteger.get(20240101))
    dd.set_item("NameDate", COSName.get_pdf_name("D:20240101"))
    dd.set_item("GoodDate", COSString("D:20240101120000Z"))
    rec["getDate_int"] = "null" if dd.get_date("NotDate") is None else "date"
    rec["getDate_name"] = "null" if dd.get_date("NameDate") is None else "date"
    rec["getDate_good"] = "null" if dd.get_date("GoodDate") is None else "date"
    rec["getDate_absent"] = "null" if dd.get_date("Absent") is None else "date"
    return rec


def _pypdfbox_payload() -> dict[str, object]:
    return {
        "_arrayDerefAsym": _array_deref_asym(),
        "_arrayGrow": _array_grow(),
        "_arrayMutate": _array_mutate(),
        "_dictNumeric": _dict_numeric(),
        "_dictContainers": _dict_containers(),
        "_dictFlagsDate": _dict_flags_date(),
    }


@requires_oracle
def test_cos_container_ops_fuzz_matches_pdfbox() -> None:
    java = json.loads(run_probe_text("CosContainerOpsFuzzProbe"))
    py = _pypdfbox_payload()
    assert py == java


def test_array_get_float_boolean_extension_pinned() -> None:
    """``COSArray.get_float`` / ``get_boolean`` are pypdfbox extensions (upstream
    ``COSArray`` has neither — verified against the 3.0.7 bytecode), so they have
    no Java oracle. Unlike the raw-entry ``get_int`` / ``get_name`` /
    ``get_string`` they dereference an indirect ``COSObject`` (mirroring
    ``get_object``), so an indirect numeric / boolean resolves through them.
    """
    a = COSArray()
    a.add(_ind(COSFloat(_f32(2.5))))    # 0 indirect -> float
    a.add(_ind(COSBoolean.TRUE))        # 1 indirect -> bool
    a.add(COSName.get_pdf_name("Bare")) # 2 wrong type
    # get_float / get_boolean deref the indirect holder.
    assert a.get_float(0) == pytest.approx(2.5)
    assert a.get_boolean(1) is True
    # wrong type / out of range fall back to the documented defaults.
    assert a.get_float(2) == -1.0
    assert a.get_boolean(2) is False
    assert a.get_float(9, 3.0) == 3.0
    assert a.get_boolean(9, True) is True
