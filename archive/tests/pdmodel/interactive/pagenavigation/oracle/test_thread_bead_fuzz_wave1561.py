"""Article-thread/bead RING TRAVERSAL + catalog /Threads + /I differential fuzz.

Complements ``test_thread_bead_cycle_fuzz_wave1521`` (shape matrix, per-accessor
results, append, raw-pointer cycle walk, setters). This wave fuzzes the angles
that probe does not:

* forward ring ORDER over proper / broken / cyclic-to-middle / self-referencing
  ``/N`` chains, plus ``count_beads`` (our recursion-guarded iterator);
* the backward ``/V`` chain order;
* ``PDDocumentCatalog.get_threads()`` over malformed ``/Threads`` arrays — where
  PDFBox hard-casts every entry to ``COSDictionary`` and so raises on a
  non-dictionary / null / dangling entry, while our port skips them defensively;
* ``PDThread.get_thread_info()`` reading a ``/Title`` from ``/I``.

Both sides are pinned against the live Apache PDFBox 3.0.7 oracle
(``ThreadBeadFuzzProbe``); honest-divergence cases carry their own comment +
``_INTENTIONAL_*`` membership so a future re-sync sees exactly why pypdfbox and
PDFBox print different strings.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread, PDThreadBead
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------------------------------------------------------------------------
# Java gold, captured from ThreadBeadFuzzProbe against PDFBox 3.0.7. Kept inline
# so the value-based assertions stand even on a machine without the oracle jar.
# ---------------------------------------------------------------------------
_JAVA_GOLD = {
    "ring_fwd": "a-b-c",
    "ring_bwd": "a-c-b",
    "ring_count": "3",
    "broken_fwd": "a-b-c|wrap_null",
    "broken_count": "3",
    "cyclemid_fwd": "a-b-c",
    "cyclemid_count": "3",
    "selfref_fwd": "a",
    "selfref_count": "1",
    "single_fwd": "a|wrap_null",
    "single_count": "1",
    "midwrong_fwd": "a-b|wrap_null",
    "midwrong_count": "2",
    "indring_fwd": "a-b",
    "indring_count": "2",
    "bwd_two": "a-b",
    "threads_absent": "n=0",
    "threads_two": "n=2;title=One;title=Two",
    "threads_nondict": "ERR:ClassCastException",
    "threads_null": "ERR:NullPointerException",
    "threads_indirect": "n=1;title=Indirect",
    "threads_dangling": "ERR:NullPointerException",
    "threads_noinfo": "n=1;noinfo",
    "info_title": "Hi",
    "info_wrong": "null",
    "info_absent": "null",
}

# Cases where pypdfbox deliberately prints a different string than PDFBox.
#
# * The ``*_fwd`` boundary cases: PDFBox ``getNextBead()`` ALWAYS returns a new
#   PDThreadBead wrapping ``getCOSDictionary(/N)`` (which can be null when /N is
#   absent or non-dict), so a forward walk emits a final "wrap_null" sentinel.
#   pypdfbox ``get_next_bead`` returns ``None`` instead of a null-backed wrapper
#   (Python cannot expose a null COSObject safely), so the walk stops one step
#   earlier with no sentinel. The bead COUNT is identical on both sides — only
#   the printed sentinel differs.
# * The ``threads_*`` error cases: PDFBox ``getThreads()`` hard-casts every
#   ``/Threads`` entry to COSDictionary (ClassCastException on a non-dict,
#   NullPointerException on a resolved-null / dangling entry). pypdfbox skips
#   non-dictionary entries defensively (documented in get_threads' docstring),
#   returning a shorter list rather than raising.
_INTENTIONAL_FWD = {"broken_fwd", "single_fwd", "midwrong_fwd"}
_INTENTIONAL_THREADS = {"threads_nondict", "threads_null", "threads_dangling"}

# pypdfbox values for the intentional-divergence cases (pinned independently).
_PY_DIVERGENCE = {
    "broken_fwd": "a-b-c",
    "single_fwd": "a",
    "midwrong_fwd": "a-b",
    "threads_nondict": "n=2;title=One;title=Three",
    "threads_null": "n=1;title=One",
    "threads_dangling": "n=0",
}


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _result(accessor: Callable[[], str]) -> str:
    try:
        return accessor()
    except Exception as exc:  # noqa: BLE001 - mirrors the Java Throwable arm
        return f"ERR:{type(exc).__name__}"


def _indirect(value: COSObject | COSDictionary | COSInteger | COSNull) -> COSObject:
    return COSObject(1, resolved=value)


def _node(label: str) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_item(_name("Type"), _name("Bead"))
    dictionary.set_item(_name("L"), COSString(label))
    return dictionary


def _label(dictionary: COSDictionary) -> str:
    value = dictionary.get_dictionary_object(_name("L"))
    if isinstance(value, COSString):
        return value.get_string()
    return "?"


def _link(from_dict: COSDictionary, key: COSName, to_dict: COSDictionary) -> None:
    from_dict.set_item(key, to_dict)


# ---------- traversal helpers mirroring the Java probe ----------


def _forward_order(start: COSDictionary) -> str:
    seen: set[int] = set()
    order: list[str] = []
    current: PDThreadBead | None = PDThreadBead(start)
    while True:
        dictionary = current.get_cos_object()
        if dictionary is None:
            return "wrap_null" if not order else "-".join(order) + "|wrap_null"
        if id(dictionary) in seen:
            return "-".join(order)
        seen.add(id(dictionary))
        order.append(_label(dictionary))
        nxt = current.get_next_bead()
        if nxt is None:
            return "-".join(order)
        current = nxt


def _backward_order(start: COSDictionary) -> str:
    seen: set[int] = set()
    order: list[str] = []
    current: PDThreadBead | None = PDThreadBead(start)
    while True:
        dictionary = current.get_cos_object()
        if dictionary is None:
            return "wrap_null" if not order else "-".join(order) + "|wrap_null"
        if id(dictionary) in seen:
            return "-".join(order)
        seen.add(id(dictionary))
        order.append(_label(dictionary))
        prev = current.get_previous_bead()
        if prev is None:
            return "-".join(order)
        current = prev


def _count(start: COSDictionary) -> int:
    # Mirrors the Java probe's identity-guarded forward count; pypdfbox's own
    # PDThreadBead.count_beads() must agree with this for every case.
    seen: set[int] = set()
    current: PDThreadBead | None = PDThreadBead(start)
    while True:
        dictionary = current.get_cos_object()
        if dictionary is None or id(dictionary) in seen:
            return len(seen)
        seen.add(id(dictionary))
        nxt = current.get_next_bead()
        if nxt is None:
            return len(seen)
        current = nxt


# ---------- build the same battery the probe builds ----------


def _ring_cases() -> dict[str, str]:
    cases: dict[str, str] = {}

    a, b, c = _node("a"), _node("b"), _node("c")
    _link(a, _name("N"), b)
    _link(b, _name("N"), c)
    _link(c, _name("N"), a)
    _link(a, _name("V"), c)
    _link(b, _name("V"), a)
    _link(c, _name("V"), b)
    cases["ring_fwd"] = _result(lambda: _forward_order(a))
    cases["ring_bwd"] = _result(lambda: _backward_order(a))
    cases["ring_count"] = _result(lambda: str(_count(a)))

    a2, b2, c2 = _node("a"), _node("b"), _node("c")
    _link(a2, _name("N"), b2)
    _link(b2, _name("N"), c2)
    cases["broken_fwd"] = _result(lambda: _forward_order(a2))
    cases["broken_count"] = _result(lambda: str(_count(a2)))

    a3, b3, c3 = _node("a"), _node("b"), _node("c")
    _link(a3, _name("N"), b3)
    _link(b3, _name("N"), c3)
    _link(c3, _name("N"), b3)
    cases["cyclemid_fwd"] = _result(lambda: _forward_order(a3))
    cases["cyclemid_count"] = _result(lambda: str(_count(a3)))

    a4 = _node("a")
    _link(a4, _name("N"), a4)
    cases["selfref_fwd"] = _result(lambda: _forward_order(a4))
    cases["selfref_count"] = _result(lambda: str(_count(a4)))

    a5 = _node("a")
    cases["single_fwd"] = _result(lambda: _forward_order(a5))
    cases["single_count"] = _result(lambda: str(_count(a5)))

    a6, b6 = _node("a"), _node("b")
    _link(a6, _name("N"), b6)
    b6.set_item(_name("N"), COSInteger.ONE)
    cases["midwrong_fwd"] = _result(lambda: _forward_order(a6))
    cases["midwrong_count"] = _result(lambda: str(_count(a6)))

    a7, b7 = _node("a"), _node("b")
    a7.set_item(_name("N"), _indirect(b7))
    b7.set_item(_name("N"), _indirect(a7))
    cases["indring_fwd"] = _result(lambda: _forward_order(a7))
    cases["indring_count"] = _result(lambda: str(_count(a7)))

    a8, b8 = _node("a"), _node("b")
    _link(a8, _name("V"), b8)
    _link(b8, _name("V"), a8)
    cases["bwd_two"] = _result(lambda: _backward_order(a8))

    return cases


def _thread(title: str) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_item(_name("Type"), _name("Thread"))
    info = COSDictionary()
    info.set_item(_name("Title"), COSString(title))
    dictionary.set_item(_name("I"), info)
    return dictionary


def _threads_result(array: COSArray) -> str:
    doc = PDDocument()
    try:
        doc.get_document_catalog().get_cos_object().set_item(_name("Threads"), array)
        threads = doc.get_document_catalog().get_threads()
        parts = [f"n={len(threads)}"]
        for thread in threads:
            info = thread.get_thread_info()
            if info is None:
                parts.append("noinfo")
            else:
                parts.append(f"title={info.get_title()}")
        return ";".join(parts)
    finally:
        doc.close()


def _threads_cases() -> dict[str, str]:
    cases: dict[str, str] = {}

    doc = PDDocument()
    try:
        doc.get_document_catalog().get_cos_object().remove_item(_name("Threads"))
        cases["threads_absent"] = _result(
            lambda: f"n={len(doc.get_document_catalog().get_threads())}"
        )
    finally:
        doc.close()

    two = COSArray()
    two.add(_thread("One"))
    two.add(_thread("Two"))
    cases["threads_two"] = _result(lambda: _threads_result(two))

    nondict = COSArray()
    nondict.add(_thread("One"))
    nondict.add(COSInteger.ONE)
    nondict.add(_thread("Three"))
    cases["threads_nondict"] = _result(lambda: _threads_result(nondict))

    nullarr = COSArray()
    nullarr.add(_thread("One"))
    nullarr.add(COSNull.NULL)
    cases["threads_null"] = _result(lambda: _threads_result(nullarr))

    indirect = COSArray()
    indirect.add(_indirect(_thread("Indirect")))
    cases["threads_indirect"] = _result(lambda: _threads_result(indirect))

    dangling = COSArray()
    dangling.add(_indirect(COSNull.NULL))
    cases["threads_dangling"] = _result(lambda: _threads_result(dangling))

    noinfo = COSArray()
    bare = COSDictionary()
    bare.set_item(_name("Type"), _name("Thread"))
    noinfo.add(bare)
    cases["threads_noinfo"] = _result(lambda: _threads_result(noinfo))

    return cases


def _info_cases() -> dict[str, str]:
    cases: dict[str, str] = {}

    with_title = COSDictionary()
    info = COSDictionary()
    info.set_item(_name("Title"), COSString("Hi"))
    with_title.set_item(_name("I"), info)
    cases["info_title"] = _result(
        lambda: (
            "null"
            if (pdi := PDThread(with_title).get_thread_info()) is None
            else str(pdi.get_title())
        )
    )

    info_wrong = COSDictionary()
    info_wrong.set_item(_name("I"), COSInteger.ONE)
    cases["info_wrong"] = _result(
        lambda: "null" if PDThread(info_wrong).get_thread_info() is None else "info"
    )

    info_absent = COSDictionary()
    cases["info_absent"] = _result(
        lambda: "null" if PDThread(info_absent).get_thread_info() is None else "info"
    )

    return cases


def _py_cases() -> dict[str, str]:
    cases: dict[str, str] = {}
    cases.update(_ring_cases())
    cases.update(_threads_cases())
    cases.update(_info_cases())
    return cases


# ---------------------------------------------------------------------------
# Value-based parity (runs everywhere): pypdfbox matches the inline PDFBox gold
# on the agreeing cases, and matches the pinned divergence value on the rest.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(_JAVA_GOLD))
def test_thread_bead_fuzz_matches_pinned_pdfbox(case: str) -> None:
    py = _py_cases()[case]
    if case in _INTENTIONAL_FWD or case in _INTENTIONAL_THREADS:
        assert py == _PY_DIVERGENCE[case], (
            f"{case}: pypdfbox divergence value drifted "
            f"(PDFBox prints {_JAVA_GOLD[case]!r})"
        )
    else:
        assert py == _JAVA_GOLD[case], f"{case}: pypdfbox diverged from PDFBox 3.0.7"


def test_iter_api_count_matches_walk() -> None:
    """pypdfbox's own PDThreadBead.count_beads() must agree with the
    identity-guarded forward walk for every ring case — the recursion guard
    terminates on cycles and self-references alike."""
    a, b, c = _node("a"), _node("b"), _node("c")
    _link(a, _name("N"), b)
    _link(b, _name("N"), c)
    _link(c, _name("N"), a)
    assert PDThreadBead(a).count_beads() == 3

    a3, b3, c3 = _node("a"), _node("b"), _node("c")
    _link(a3, _name("N"), b3)
    _link(b3, _name("N"), c3)
    _link(c3, _name("N"), b3)
    assert PDThreadBead(a3).count_beads() == 3  # cycle-to-middle still terminates

    a4 = _node("a")
    _link(a4, _name("N"), a4)
    assert PDThreadBead(a4).count_beads() == 1  # self-reference

    a5 = _node("a")
    assert PDThreadBead(a5).count_beads() == 1  # single bead, no /N


def test_iter_beads_order_matches_forward_walk() -> None:
    """iter_beads emits the ring in /N order and stops at the wrap-back."""
    a, b, c = _node("a"), _node("b"), _node("c")
    _link(a, _name("N"), b)
    _link(b, _name("N"), c)
    _link(c, _name("N"), a)
    assert [_label(x.get_cos_object()) for x in PDThreadBead(a).iter_beads()] == [
        "a",
        "b",
        "c",
    ]


def test_get_threads_skips_nondict_entries() -> None:
    """pypdfbox skips non-dictionary /Threads entries instead of raising the
    ClassCastException PDFBox throws — documented defensive divergence."""
    array = COSArray()
    array.add(_thread("One"))
    array.add(COSInteger.ONE)
    array.add(_thread("Three"))
    assert _threads_result(array) == "n=2;title=One;title=Three"


# ---------------------------------------------------------------------------
# Live oracle: when the PDFBox jar is present, regenerate the gold and confirm
# the inline copy is current, plus re-verify each agreeing case end to end.
# ---------------------------------------------------------------------------


@requires_oracle
def test_live_oracle_matches_inline_gold() -> None:
    text = run_probe_text("ThreadBeadFuzzProbe")
    live: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("CASE "):
            continue
        _, name, value = line.split(" ", 2)
        live[name] = value
    assert live == _JAVA_GOLD, "inline PDFBox gold drifted from the live oracle"

    py = _py_cases()
    for case, java_value in live.items():
        if case in _INTENTIONAL_FWD or case in _INTENTIONAL_THREADS:
            continue
        assert py[case] == java_value, f"{case}: pypdfbox diverged from live PDFBox"
