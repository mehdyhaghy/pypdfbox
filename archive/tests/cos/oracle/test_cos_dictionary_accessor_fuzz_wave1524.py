"""Live PDFBox differential parity for COSDictionary typed-accessor coercion
under MALFORMED / EDGE input — the fuzz complement to
``test_cos_dict_accessor_oracle.py`` (which pins the common-shape matrix).

Drives Apache PDFBox 3.0.7's ``COSDictionary`` accessor surface (via the
``CosDictionaryAccessorFuzzProbe`` Java oracle) across the corners the basic
probe does not exercise, then asserts pypdfbox produces byte-identical results:

* a wrong-type coercion **matrix** — ``get_int`` / ``get_long`` / ``get_float``
  / ``get_boolean`` / ``get_cos_name`` / ``get_name_as_string`` / ``get_string``
  each driven over every mismatched value shape (string, numeric-looking
  string, name, both booleans, array, sub-dict, explicit ``COSNull``, absent),
  confirming the ``-1`` / explicit default / ``None`` sentinel for every
  mismatch and that ``get_name_as_string`` coerces a ``COSString`` to text while
  ``get_string`` does not coerce a ``COSName``;
* numeric **overflow / wrap** — ``get_int`` over ``COSInteger`` values at and
  beyond the signed-32-bit boundary (``2**31``, ``2**31-1``, ``-2**31``,
  ``-(2**31+1)``, ``Long.MAX``, ``Long.MIN``) where ``int_value`` does the
  ``(int)`` narrowing-cast wrap; ``get_long`` / ``get_float`` on the same; and
  ``get_int`` / ``get_long`` over huge / tiny ``COSFloat`` values where the
  ``f2i`` / ``f2l`` narrowing saturates / truncates toward zero;
* indirect ``COSObject`` resolution plus the two-key fallback when the first key
  resolves to ``COSNull`` (direct and indirect) — it must fall through to the
  second key, and ``get_item`` keeps the raw holder while
  ``get_dictionary_object`` collapses it to ``None``;
* ``COSName``-key vs ``str``-key overload equivalence (every accessor takes both
  and they must agree, including on a missing key).

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


def _wrong_type_payload() -> dict[str, object]:
    d = COSDictionary()
    d.set_item("Str", COSString("hello"))
    d.set_item("NumStr", COSString("123"))
    d.set_item("Name", COSName.get_pdf_name("Foo"))
    d.set_item("BoolT", COSBoolean.TRUE)
    d.set_item("BoolF", COSBoolean.FALSE)
    d.set_item("Arr", COSArray())
    d.set_item("Sub", COSDictionary())
    d.set_item("Null", COSNull.NULL)
    keys = ["Str", "NumStr", "Name", "BoolT", "BoolF", "Arr", "Sub", "Null", "Absent"]
    out: dict[str, object] = {}
    for k in keys:
        cn = d.get_cos_name(k)
        out[k] = {
            "getInt": d.get_int(k),
            "getIntDef7": d.get_int(k, 7),
            "getLong": d.get_long(k),
            "getFloat": _fbits_hex(d.get_float(k)),
            "getBoolDefT": d.get_boolean(k, True),
            "getCOSName": cn.name if cn is not None else None,
            "getNameAsString": d.get_name_as_string(k),
            "getString": d.get_string(k),
        }
    return out


def _numeric_payload() -> dict[str, object]:
    n = COSDictionary()
    n.set_item("I_2p31", COSInteger.get(2147483648))
    n.set_item("I_2p31m1", COSInteger.get(2147483647))
    n.set_item("I_neg2p31", COSInteger.get(-2147483648))
    n.set_item("I_neg2p31m1", COSInteger.get(-2147483649))
    n.set_item("I_longmax", COSInteger.get(2**63 - 1))
    n.set_item("I_longmin", COSInteger.get(-(2**63)))
    n.set_item("F_huge", COSFloat(_f32(1.0e30)))
    n.set_item("F_neghuge", COSFloat(_f32(-1.0e30)))
    n.set_item("F_tiny", COSFloat(_f32(0.4)))
    n.set_item("F_negtiny", COSFloat(_f32(-0.4)))
    keys = [
        "I_2p31", "I_2p31m1", "I_neg2p31", "I_neg2p31m1", "I_longmax",
        "I_longmin", "F_huge", "F_neghuge", "F_tiny", "F_negtiny",
    ]
    out: dict[str, object] = {}
    for k in keys:
        out[k] = {
            "getInt": n.get_int(k),
            "getLong": n.get_long(k),
            "getFloat": _fbits_hex(n.get_float(k)),
        }
    return out


def _indirect_payload() -> dict[str, object]:
    ind = COSDictionary()
    ind.set_item("IndInt", COSObject(1, 0, resolved=COSInteger.get(55)))
    ind.set_item("IndNull", COSObject(2, 0, resolved=COSNull.NULL))
    ind.set_item("DirNull", COSNull.NULL)
    ind.set_item("Real", COSInteger.get(9))
    return {
        "getInt_indInt": ind.get_int("IndInt"),
        "dictObj_indNull": _type_tag(ind.get_dictionary_object("IndNull")),
        "dictObj_dirNull": _type_tag(ind.get_dictionary_object("DirNull")),
        "item_indNull": _type_tag(ind.get_item("IndNull")),
        "item_dirNull": _type_tag(ind.get_item("DirNull")),
        "twoKey_dirNullThenReal": _type_tag(
            ind.get_dictionary_object("DirNull", "Real")
        ),
        "twoKey_indNullThenReal": _type_tag(
            ind.get_dictionary_object("IndNull", "Real")
        ),
        "getInt_twoKey_dirNull": ind.get_int("DirNull", "Real", 3),
    }


def _overload_payload() -> dict[str, object]:
    o = COSDictionary()
    o.set_item("K", COSInteger.get(17))
    return {
        "byName": o.get_int(COSName.get_pdf_name("K")),
        "byString": o.get_int("K"),
        "nameMissing": o.get_int(COSName.get_pdf_name("X")),
        "stringMissing": o.get_int("X"),
    }


def _pypdfbox_payload() -> dict[str, object]:
    return {
        "_wrongType": _wrong_type_payload(),
        "_numeric": _numeric_payload(),
        "_indirect": _indirect_payload(),
        "_overload": _overload_payload(),
    }


@requires_oracle
def test_cos_dictionary_accessor_fuzz_matches_pdfbox() -> None:
    java = json.loads(run_probe_text("CosDictionaryAccessorFuzzProbe"))
    py = _pypdfbox_payload()
    assert py == java
