"""Live PDFBox differential parity for ``COSArray`` mutation + conversion
helpers — the surface covering ``setFloatArray`` / ``toFloatArray`` /
``setInt``, ``growToSize(int)`` (pads with Java ``null`` → Python ``None``,
NOT ``COSNull``), ``add`` / ``set`` / ``remove(int)`` / ``remove(COSBase)``,
``setName`` / ``getName``, and ``toList``.

The load-bearing contract pinned here is the **out-of-range setter** behaviour:
upstream ``COSArray.setName`` / ``setInt`` / ``set`` all delegate to
``List.set(index, obj)``, which raises ``IndexOutOfBoundsException`` when
``index >= size``. They do NOT auto-grow the array. pypdfbox's ``set_name``
previously auto-grew (via ``grow_to_size``); this wave routes it through
``set`` so an out-of-range index raises ``IndexError`` exactly as upstream
throws. The ``CosArrayOpsProbe`` Java oracle drives PDFBox 3.0.7 directly and
emits a per-scenario signal (``throws:<SimpleName>`` for the exception cases).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_null import COSNull
from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text


def _tok(b: object) -> str:
    """Mirror the Java probe's ``tok`` rendering of a raw entry."""
    if b is None:
        return "null"
    if b is COSNull.NULL:
        return "COSNull"
    if isinstance(b, COSInteger):
        return f"int:{b.value}"
    if isinstance(b, COSFloat):
        return f"float:{_jfloat(b.value)}"
    if isinstance(b, COSName):
        return f"name:{b.get_name()}"
    if isinstance(b, COSString):
        return f"str:{b.get_string()}"
    return type(b).__name__


def _jfloat(value: float) -> str:
    """Render a float the way Java ``String.valueOf(float)`` does for the
    plain magnitudes this probe uses (whole numbers keep a ``.0`` tail)."""
    if value == int(value):
        return f"{int(value)}.0"
    return repr(value)


def _jstr(value: str | None) -> str:
    """Mirror Java ``String.valueOf(s)`` — ``null`` renders as the literal
    ``"null"`` (Python ``str(None)`` would give ``"None"``)."""
    return "null" if value is None else value


def _dump(a: COSArray) -> str:
    return "[" + ",".join(_tok(a.get(i)) for i in range(a.size())) + "]"


def _floats(values: list[float]) -> str:
    return "[" + ",".join(_jfloat(v) for v in values) + "]"


def _signal(scenario: str) -> str:
    try:
        return _run(scenario)
    except Exception as e:  # noqa: BLE001 — mirror the probe's catch-all
        return f"throws:{_java_exc_name(e)}"


def _java_exc_name(e: Exception) -> str:
    """Map a Python exception to the Java SimpleName the probe would emit."""
    if isinstance(e, IndexError):
        return "IndexOutOfBoundsException"
    return type(e).__name__


def _run(scenario: str) -> str:  # noqa: PLR0911, PLR0912, C901 — flat dispatch mirrors the probe
    if scenario == "setFloatArray":
        a = COSArray()
        a.add(COSName.get_pdf_name("preexisting"))
        a.set_float_array([1.5, -2.25, 0.0, 100.0])
        return _dump(a) + f"|size={a.size()}"
    if scenario == "toFloatArray":
        a = COSArray()
        a.add(COSInteger.get(7))
        a.add(COSFloat(3.5))
        a.add(COSName.get_pdf_name("notnum"))
        a.add(COSNull.NULL)
        return _floats(a.to_float_array())
    if scenario == "toFloatArrayEmpty":
        return _floats(COSArray().to_float_array())
    if scenario == "growToSize_grow":
        a = COSArray()
        a.add(COSName.get_pdf_name("x"))
        a.grow_to_size(4)
        return _dump(a) + f"|size={a.size()}"
    if scenario == "growToSize_fill":
        a = COSArray()
        a.grow_to_size(3, COSInteger.get(9))
        return _dump(a) + f"|size={a.size()}"
    if scenario == "growToSize_noshrink":
        a = COSArray()
        for v in (1, 2, 3):
            a.add(COSInteger.get(v))
        a.grow_to_size(1)
        return _dump(a) + f"|size={a.size()}"
    if scenario == "add":
        a = COSArray()
        a.add(COSInteger.get(5))
        return _dump(a)
    if scenario == "set_inrange":
        a = COSArray()
        a.add(COSInteger.get(0))
        a.set(0, COSName.get_pdf_name("y"))
        return _dump(a)
    if scenario == "set_oob":
        a = COSArray()
        a.set(2, COSName.get_pdf_name("y"))
        return _dump(a)
    if scenario == "remove_int":
        a = COSArray()
        for v in (1, 2, 3):
            a.add(COSInteger.get(v))
        removed = a.remove_at(1)
        return f"removed={_tok(removed)}|{_dump(a)}"
    if scenario == "remove_int_oob":
        a = COSArray()
        a.add(COSInteger.get(1))
        a.remove_at(5)
        return _dump(a)
    if scenario == "remove_obj_present":
        a = COSArray()
        a.add(COSInteger.get(1))
        a.add(COSInteger.get(2))
        a.add(COSInteger.get(1))
        r = a.remove(COSInteger.get(1))
        return f"r={'true' if r else 'false'}|{_dump(a)}"
    if scenario == "remove_obj_absent":
        a = COSArray()
        a.add(COSInteger.get(1))
        r = a.remove(COSInteger.get(99))
        return f"r={'true' if r else 'false'}|{_dump(a)}"
    if scenario == "setName_inrange":
        a = COSArray()
        a.add(COSName.get_pdf_name("a"))
        a.add(COSName.get_pdf_name("b"))
        a.set_name(1, "z")
        return _dump(a)
    if scenario == "setName_oob":
        a = COSArray()
        a.add(COSName.get_pdf_name("a"))
        a.set_name(4, "z")
        return _dump(a)
    if scenario == "getName_present":
        a = COSArray()
        a.add(COSName.get_pdf_name("hello"))
        return _jstr(a.get_name(0))
    if scenario == "getName_default":
        a = COSArray()
        a.add(COSInteger.get(7))
        return a.get_name(0, "DEF")
    if scenario == "getName_oob":
        a = COSArray()
        return _jstr(a.get_name(5))
    if scenario == "toList":
        a = COSArray()
        a.add(COSInteger.get(1))
        a.add(COSName.get_pdf_name("n"))
        items = a.to_list()
        body = "[" + ",".join(_tok(x) for x in items) + "]"
        return body + f"|size={len(items)}"
    return "UNKNOWN_SCENARIO"


_SCENARIOS: list[str] = [
    "setFloatArray",
    "toFloatArray",
    "toFloatArrayEmpty",
    "growToSize_grow",
    "growToSize_fill",
    "growToSize_noshrink",
    "add",
    "set_inrange",
    "set_oob",
    "remove_int",
    "remove_int_oob",
    "remove_obj_present",
    "remove_obj_absent",
    "setName_inrange",
    "setName_oob",
    "getName_present",
    "getName_default",
    "getName_oob",
    "toList",
]


@requires_oracle
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_SCENARIOS)
def test_cos_array_ops_matches_pdfbox(scenario: str) -> None:
    """Each ``COSArray`` mutation/conversion scenario matches PDFBox 3.0.7."""
    java = run_probe_text("CosArrayOpsProbe", scenario).strip()
    expected = f"{scenario}={_signal(scenario)}"
    assert expected == java


def test_set_name_out_of_range_raises() -> None:
    """Regression pin (no oracle needed): ``set_name`` past the end raises
    ``IndexError`` — it must not auto-grow (upstream ``List.set`` throws)."""
    a = COSArray()
    a.add(COSName.get_pdf_name("a"))
    with pytest.raises(IndexError):
        a.set_name(4, "z")
    assert a.size() == 1
