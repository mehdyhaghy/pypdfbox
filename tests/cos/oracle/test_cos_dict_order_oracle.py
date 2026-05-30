"""Live PDFBox differential parity for ``COSDictionary`` key-insertion-order
preservation + typed/raw getters.

PDFBox backs ``COSDictionary`` with a ``LinkedHashMap``, so ``keySet`` iterates
in insertion order; overwriting an existing key keeps its original position,
while removing a key (via ``setItem(key, null)``) and re-inserting it moves it
to the end. Python's built-in ``dict`` has identical ordering semantics, which
this probe pins exactly. The getter surface covered is ``getCOSName`` /
``getCOSArray`` (typed, wrong-type → default), the two-key
``getDictionaryObject(firstKey, secondKey)`` lookup, ``getItem`` (raw) vs
``getDictionaryObject`` (dereferenced), and ``setItem(key, null)`` removing the
key (absent-key removal is a no-op).

The ``CosDictOrderProbe`` Java oracle drives PDFBox 3.0.7 directly and emits a
per-scenario ``<scenario>=<signal>`` line.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from tests.oracle.harness import requires_oracle, run_probe_text


def _tok(b: object) -> str:
    """Mirror the Java probe's ``tok`` rendering of a single value."""
    if b is None:
        return "null"
    if isinstance(b, COSInteger):
        return f"int:{b.value}"
    if isinstance(b, COSName):
        return f"name:{b.get_name()}"
    if isinstance(b, COSArray):
        return f"array:size={b.size()}"
    if isinstance(b, COSDictionary):
        return f"dict:size={b.size()}"
    return type(b).__name__


def _keys(d: COSDictionary) -> str:
    return "[" + ",".join(k.get_name() for k in d.key_set()) + "]"


def _jbool(value: bool) -> str:
    """Render a Python bool the way Java ``String.valueOf(boolean)`` does."""
    return "true" if value else "false"


def _signal(scenario: str) -> str:
    try:
        return _run(scenario)
    except Exception as e:  # noqa: BLE001 — mirror the probe's catch-all
        return f"throws:{type(e).__name__}"


def _run(scenario: str) -> str:  # noqa: PLR0911, C901 — flat dispatch mirrors the probe
    if scenario == "order_insert":
        d = COSDictionary()
        d.set_item("A", COSInteger.get(1))
        d.set_item("C", COSInteger.get(2))
        d.set_item("B", COSInteger.get(3))
        return _keys(d)
    if scenario == "order_overwrite_keeps_position":
        d = COSDictionary()
        d.set_item("A", COSInteger.get(1))
        d.set_item("B", COSInteger.get(2))
        d.set_item("C", COSInteger.get(3))
        d.set_item("A", COSInteger.get(99))
        return _keys(d) + f"|A={_tok(d.get_dictionary_object('A'))}"
    if scenario == "order_remove_via_null":
        d = COSDictionary()
        d.set_item("A", COSInteger.get(1))
        d.set_item("B", COSInteger.get(2))
        d.set_item("C", COSInteger.get(3))
        d.set_item("B", None)
        return _keys(d) + f"|size={d.size()}"
    if scenario == "order_remove_then_reinsert":
        d = COSDictionary()
        d.set_item("A", COSInteger.get(1))
        d.set_item("B", COSInteger.get(2))
        d.set_item("C", COSInteger.get(3))
        d.set_item("B", None)
        d.set_item("B", COSInteger.get(22))
        return _keys(d)
    if scenario == "getCOSName_present":
        d = COSDictionary()
        d.set_item("Type", COSName.get_pdf_name("Page"))
        return _tok(d.get_cos_name(COSName.TYPE))
    if scenario == "getCOSName_wrongtype":
        d = COSDictionary()
        d.set_item("Type", COSInteger.get(5))
        return _tok(d.get_cos_name(COSName.TYPE))
    if scenario == "getCOSName_default":
        d = COSDictionary()
        return _tok(d.get_cos_name(COSName.TYPE, COSName.get_pdf_name("Fallback")))
    if scenario == "getCOSArray_present":
        d = COSDictionary()
        a = COSArray()
        a.add(COSInteger.get(1))
        a.add(COSInteger.get(2))
        d.set_item("Kids", a)
        return _tok(d.get_cos_array("Kids"))
    if scenario == "getCOSArray_wrongtype":
        d = COSDictionary()
        d.set_item("Kids", COSInteger.get(5))
        return _tok(d.get_cos_array("Kids"))
    if scenario == "getCOSArray_absent":
        d = COSDictionary()
        return _tok(d.get_cos_array("Kids"))
    if scenario == "twokey_firstpresent":
        d = COSDictionary()
        d.set_item("W", COSInteger.get(1))
        d.set_item("Width", COSInteger.get(2))
        return _tok(d.get_dictionary_object("Width", COSName.get_pdf_name("W")))
    if scenario == "twokey_firstabsent":
        d = COSDictionary()
        d.set_item("W", COSInteger.get(7))
        return _tok(d.get_dictionary_object("Width", COSName.get_pdf_name("W")))
    if scenario == "twokey_bothabsent":
        d = COSDictionary()
        return _tok(d.get_dictionary_object("Width", COSName.get_pdf_name("W")))
    if scenario == "getItem_vs_getDictionaryObject_direct":
        d = COSDictionary()
        d.set_item("X", COSInteger.get(42))
        raw = d.get_item("X")
        deref = d.get_dictionary_object("X")
        return f"raw={_tok(raw)}|deref={_tok(deref)}"
    if scenario == "setItem_null_removes":
        d = COSDictionary()
        d.set_item("X", COSInteger.get(1))
        before = d.contains_key("X")
        d.set_item("X", None)
        after = d.contains_key("X")
        return f"before={_jbool(before)}|after={_jbool(after)}|size={d.size()}"
    if scenario == "setItem_null_absent_noop":
        d = COSDictionary()
        d.set_item("A", COSInteger.get(1))
        d.set_item("Z", None)
        return _keys(d) + f"|size={d.size()}"
    return "UNKNOWN_SCENARIO"


_SCENARIOS: list[str] = [
    "order_insert",
    "order_overwrite_keeps_position",
    "order_remove_via_null",
    "order_remove_then_reinsert",
    "getCOSName_present",
    "getCOSName_wrongtype",
    "getCOSName_default",
    "getCOSArray_present",
    "getCOSArray_wrongtype",
    "getCOSArray_absent",
    "twokey_firstpresent",
    "twokey_firstabsent",
    "twokey_bothabsent",
    "getItem_vs_getDictionaryObject_direct",
    "setItem_null_removes",
    "setItem_null_absent_noop",
]


@requires_oracle
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=_SCENARIOS)
def test_cos_dict_order_matches_pdfbox(scenario: str) -> None:
    """Each ``COSDictionary`` ordering/getter scenario matches PDFBox 3.0.7."""
    java = run_probe_text("CosDictOrderProbe", scenario).strip()
    expected = f"{scenario}={_signal(scenario)}"
    assert expected == java


def test_overwrite_keeps_insertion_position() -> None:
    """Regression pin (no oracle): overwriting an existing key keeps its
    original position (PDFBox's ``LinkedHashMap`` / Python ``dict`` semantics);
    remove-then-reinsert moves it to the end."""
    d = COSDictionary()
    d.set_item("A", COSInteger.get(1))
    d.set_item("B", COSInteger.get(2))
    d.set_item("C", COSInteger.get(3))
    d.set_item("A", COSInteger.get(99))
    assert [k.get_name() for k in d.key_set()] == ["A", "B", "C"]
    d.set_item("B", None)
    d.set_item("B", COSInteger.get(22))
    assert [k.get_name() for k in d.key_set()] == ["A", "C", "B"]
