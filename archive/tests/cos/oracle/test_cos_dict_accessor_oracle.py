"""Live PDFBox differential parity for COSDictionary typed-accessor semantics.

Drives Apache PDFBox 3.0.7's ``COSDictionary`` accessor surface (via the
``CosDictAccessorProbe`` Java oracle) over a single dictionary carrying every
value shape — integer, float, whole-valued float, negative float, string,
name, both booleans, array, sub-dict, explicit ``COSNull``, an indirect
``COSObject`` wrapping an integer, an indirect ``COSObject`` wrapping
``COSNull`` — then asserts pypdfbox produces byte-identical results for:

* ``get_int`` / ``get_long`` / ``get_float`` numeric coercion of any
  ``COSNumber`` (truncation toward zero) plus the ``-1`` / explicit default on
  absent / wrong-type / ``COSNull`` entries;
* ``get_string`` decoding **only** a ``COSString`` (a ``COSName`` returns the
  default — upstream parity, fixed in this wave);
* ``get_cos_name`` returning the name only for ``COSName``;
* ``get_boolean`` returning the primitive only for ``COSBoolean``;
* ``get_dictionary_object`` dereferencing an indirect ``COSObject`` and
  collapsing ``COSNull`` (direct and indirect) to ``None``;
* ``get_item`` returning the raw, un-dereferenced entry (an indirect
  ``COSObject`` stays a reference; a direct ``COSNull`` stays ``COSNull``);
* the two-key overloads falling back to the second key only when the first is
  absent.

Floats are compared as their IEEE-754 single-precision bit pattern so the
assertion is repr-independent.
"""

from __future__ import annotations

import json
import struct

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.cos.cos_boolean import COSBoolean
from pypdfbox.cos.cos_dictionary import COSDictionary
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
    """Round a Python double to float32, mirroring Java's ``float`` storage so
    coercions through ``COSFloat`` match the single-precision values upstream
    reads back."""
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def _build_dict() -> COSDictionary:
    """Reconstruct the exact fixture dictionary the Java probe builds."""
    d = COSDictionary()
    d.set_item("Int", COSInteger.get(42))
    d.set_item("Float", COSFloat(_f32(3.5)))
    d.set_item("WholeFloat", COSFloat(_f32(7.0)))
    d.set_item("NegFloat", COSFloat(_f32(-2.9)))
    d.set_item("Str", COSString("hello"))
    d.set_item("Name", COSName.get_pdf_name("Foo"))
    d.set_item("BoolT", COSBoolean.TRUE)
    d.set_item("BoolF", COSBoolean.FALSE)
    d.set_item("Arr", COSArray())
    d.set_item("Sub", COSDictionary())
    d.set_item("Null", COSNull.NULL)
    d.set_item("IndInt", COSObject(1, 0, resolved=COSInteger.get(99)))
    d.set_item("IndNull", COSObject(2, 0, resolved=COSNull.NULL))
    return d


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
    if isinstance(b, COSBoolean):
        return f"bool:{str(b.value).lower()}"
    if isinstance(b, COSArray):
        return "array"
    if isinstance(b, COSDictionary):
        return "dict"
    return f"other:{type(b).__name__}"


def _record(d: COSDictionary, key: str) -> dict[str, object]:
    cn = d.get_cos_name(key)
    return {
        "getInt": d.get_int(key),
        "getIntDef5": d.get_int(key, 5),
        "getLong": d.get_long(key),
        "getFloat": _fbits_hex(d.get_float(key)),
        "getFloatDef": _fbits_hex(d.get_float(key, _f32(2.5))),
        "getString": d.get_string(key),
        "getStringDef": d.get_string(key, "DEF"),
        "getCOSName": cn.name if cn is not None else None,
        "getBoolFalse": d.get_boolean(key, False),
        "getBoolTrue": d.get_boolean(key, True),
        "getDictObj": _type_tag(d.get_dictionary_object(key)),
        "getItem": _type_tag(d.get_item(key)),
    }


def _pypdfbox_payload() -> dict[str, object]:
    d = _build_dict()
    keys = [
        "Int", "Float", "WholeFloat", "NegFloat", "Str", "Name",
        "BoolT", "BoolF", "Arr", "Sub", "Null", "IndInt", "IndNull",
        "Absent",
    ]
    payload: dict[str, object] = {k: _record(d, k) for k in keys}
    payload["_twoKey"] = {
        "firstPresent": _type_tag(d.get_dictionary_object("Int", "Float")),
        "firstAbsent": _type_tag(d.get_dictionary_object("Nope", "Float")),
        "bothAbsent": _type_tag(d.get_dictionary_object("Nope", "Nope2")),
        "itemFirstPresent": _type_tag(d.get_item("IndInt", "Int")),
        "itemFirstAbsent": _type_tag(d.get_item("Nope", "IndInt")),
        "intFirstAbsent": d.get_int("Nope", "Int", 7),
        "intBothAbsent": d.get_int("Nope", "Nope2", 7),
        "boolFirstAbsent": d.get_boolean("Nope", "BoolT", False),
    }
    return payload


@requires_oracle
def test_cos_dictionary_accessors_match_pdfbox() -> None:
    java = json.loads(run_probe_text("CosDictAccessorProbe"))
    py = _pypdfbox_payload()
    assert py == java
