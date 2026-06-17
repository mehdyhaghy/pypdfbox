"""Live PDFBox differential parity for COSArray index-accessor semantics.

Drives Apache PDFBox 3.0.7's ``COSArray`` index-accessor surface (via the
``CosArrayAccessorProbe`` Java oracle) over a single array carrying every
element shape — integer, whole-valued float, fractional float, negative float,
string, name, explicit ``COSNull``, and an indirect ``COSObject`` wrapping an
integer — then asserts pypdfbox produces byte-identical results for:

* ``get_int`` / ``get_int(default)`` — coerces any ``COSNumber`` *raw entry*
  (``get(i)``, NOT ``get_object(i)``) via ``int_value`` truncation toward zero;
  an indirect ``COSObject`` element therefore falls through to the default
  (upstream does **not** dereference here — fixed in this wave);
* ``get_name`` / ``get_name(default)`` — raw entry, ``COSName`` only;
* ``get_string`` / ``get_string(default)`` — raw entry, ``COSString`` only;
* ``get`` (raw, no deref) vs ``get_object`` (deref + ``COSNull`` -> ``None``);
* ``index_of`` (reference/value equality) vs ``index_of_object`` (also matches
  the dereferenced target of an indirect ``COSObject``);
* ``grow_to_size(n)`` null-padding and ``grow_to_size(n, fill)`` object-padding;
* ``to_float_array`` (deref, ``COSNumber`` -> float, else ``0.0``);
* ``set_float_array`` replacing contents with ``COSFloat`` entries.

Floats are compared as their IEEE-754 single-precision bit pattern so the
assertion is repr-independent.
"""

from __future__ import annotations

import json
import struct

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text


def _fbits_hex(value: float) -> str:
    """IEEE-754 single-precision bit pattern, lowercase hex with no leading
    zeros — matches Java ``Integer.toHexString(Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", float(value)))[0]
    return f"{bits:x}"


def _f32(value: float) -> float:
    """Round a Python double to float32, mirroring Java ``float`` storage."""
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def _build_array() -> COSArray:
    """Reconstruct the exact fixture array the Java probe builds."""
    a = COSArray()
    a.add(COSInteger.get(42))
    a.add(COSFloat(_f32(7.0)))
    a.add(COSFloat(_f32(3.9)))
    a.add(COSFloat(_f32(-2.9)))
    a.add(COSString("hello"))
    a.add(COSName.get_pdf_name("Foo"))
    a.add(COSNull.NULL)
    a.add(COSObject(1, 0, resolved=COSInteger.get(99)))
    return a


def _type_tag(b: COSBase | None) -> str:
    """Coarse type tag mirroring the Java probe's ``typeTag``."""
    if b is None:
        return "null"
    if isinstance(b, COSObject):
        return "object"
    if isinstance(b, COSNull):
        return "cosnull"
    if isinstance(b, COSInteger):
        return f"int:{b.long_value()}"
    if isinstance(b, COSFloat):
        return f"float:{_fbits_hex(b.float_value())}"
    if isinstance(b, COSString):
        return f"string:{b.get_string()}"
    if isinstance(b, COSName):
        return f"name:{b.name}"
    return f"other:{type(b).__name__}"


def _record(a: COSArray, i: int) -> dict[str, object]:
    rec: dict[str, object] = {
        "getInt": a.get_int(i),
        "getIntDef5": a.get_int(i, 5),
        "getName": a.get_name(i),
        "getNameDef": a.get_name(i, "DEF"),
        "getString": a.get_string(i),
        "getStringDef": a.get_string(i, "DEF"),
    }
    if i < a.size():
        rec["get"] = _type_tag(a.get(i))
        rec["getObject"] = _type_tag(a.get_object(i))
    else:
        rec["get"] = "oob"
        rec["getObject"] = "oob"
    return rec


def _pypdfbox_payload() -> dict[str, object]:
    a = _build_array()
    payload: dict[str, object] = {str(i): _record(a, i) for i in range(9)}

    int_elem = a.get(0)
    wrapped = COSInteger.get(99)
    payload["_index"] = {
        "indexOf_intElem": a.index_of(int_elem),
        "indexOf_wrapped99": a.index_of(wrapped),
        "indexOfObject_wrapped99": a.index_of_object(wrapped),
        "indexOfObject_intElem": a.index_of_object(int_elem),
        "indexOf_absent": a.index_of(COSName.get_pdf_name("Nope")),
        "indexOfObject_absent": a.index_of_object(COSName.get_pdf_name("Nope")),
    }

    payload["_toFloatArray"] = [_fbits_hex(f) for f in a.to_float_array()]

    g1 = COSArray()
    g1.add(COSInteger.get(1))
    g1.grow_to_size(4)
    grow: dict[str, object] = {
        "nullPad_size": g1.size(),
        "nullPad_tail": _type_tag(g1.get(3)),
    }
    g1.grow_to_size(2)
    grow["noop_size"] = g1.size()
    g2 = COSArray()
    g2.grow_to_size(3, COSInteger.get(8))
    grow["fill_size"] = g2.size()
    grow["fill_tail"] = _type_tag(g2.get(2))
    payload["_grow"] = grow

    sf = COSArray()
    sf.add(COSName.get_pdf_name("X"))
    sf.set_float_array([_f32(1.5), _f32(-2.0), _f32(0.0)])
    payload["_setFloatArray"] = {
        "size": sf.size(),
        "tags": [_type_tag(sf.get(i)) for i in range(sf.size())],
    }
    return payload


@requires_oracle
def test_cos_array_accessors_match_pdfbox() -> None:
    java = json.loads(run_probe_text("CosArrayAccessorProbe"))
    py = _pypdfbox_payload()
    assert py == java
