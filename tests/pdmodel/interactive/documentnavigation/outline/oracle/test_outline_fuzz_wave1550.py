"""Differential malformed-tree audit for the document-outline bookmark tree —
PDDocumentOutline + PDOutlineItem + PDOutlineNode (wave 1550).

Mirrors ``oracle/probes/OutlineFuzzProbe.java`` against the live Apache PDFBox
3.0.7 jar. Each case hand-builds a malformed/edge outline tree directly out of
COS objects (no PDF I/O), wraps the root in a ``PDDocumentOutline``, and
projects two surfaces:

* ``tree`` — walk the root's ``children()`` iterator and report how many
  children the recursion-guard actually yields on cyclic / self-cyclic /Next
  chains, the root's open count, and a per-child projection of
  title / has-dest / has-action / italic / bold / signed open count / colour.
* ``node`` — for a single hand-built item dictionary, project the pointer
  accessors (first/last/next/prev child titles) over broken
  /First-without-/Last and wrong-type-/First shapes plus the signed count.

Both sides build the identical dictionaries; the projected ``CASE`` line is
diffed byte-for-byte.

**Parity note on /C colour**: pypdfbox ``get_text_color()`` deliberately
returns ``None`` for a missing/malformed ``/C`` (documented divergence in
CHANGES.md — it avoids the materialise-default side-effect). The
upstream-shaped accessor that *does* mirror Java's ``getTextColor()`` is
``get_text_color_pd_color()``; this test uses that one so the projection lines
up with the live oracle's ``PDColor.getComponents()``.

**Parity note on /F flags**: upstream PDFBox 3.0.7 ``PDOutlineItem`` exposes
only ``isItalic()`` / ``isBold()`` (no ``getTextStyle`` / ``getCount``); the
probe and this test therefore project those two booleans plus the inherited
``getOpenCount()`` for the signed count.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_TITLE = _N("Title")
_FIRST = _N("First")
_LAST = _N("Last")
_NEXT = _N("Next")
_PREV = _N("Prev")
_DEST = _N("Dest")
_A = _N("A")
_C = _N("C")
_F = _N("F")
_S = _N("S")
_D = _N("D")
_TYPE = _N("Type")
_PARENT = _N("Parent")
_COUNT = _N("Count")
_OUTLINES = _N("Outlines")


def _item(title: str | None) -> COSDictionary:
    d = COSDictionary()
    if title is not None:
        d.set_item(_TITLE, COSString(title))
    return d


def _dest_fit() -> COSArray:
    a = COSArray()
    a.add(COSInteger.ZERO)
    a.add(_N("Fit"))
    return a


def _go_to_action() -> COSDictionary:
    a = COSDictionary()
    a.set_item(_S, _N("GoTo"))
    a.set_item(_D, _dest_fit())
    return a


def _color_triple(r: float, g: float, b: float) -> COSArray:
    a = COSArray()
    a.add(COSFloat(r))
    a.add(COSFloat(g))
    a.add(COSFloat(b))
    return a


# ---------------------------------------------------------------------------
# tree surface
# ---------------------------------------------------------------------------

_TREE_CASES = (
    "empty",
    "linear3",
    "cycle_next",
    "self_cycle",
    "first_without_last",
    "broken_prev",
    "title_variants",
    "dest_and_action",
    "action_wrong_type",
    "color_variants",
    "flag_variants",
    "count_open",
    "root_count_negative",
    "nested_children",
)


def _tree_root(name: str) -> COSDictionary:
    root = COSDictionary()
    root.set_item(_TYPE, _OUTLINES)
    if name == "empty":
        pass
    elif name == "linear3":
        a, b, c = _item("A"), _item("B"), _item("C")
        a.set_item(_NEXT, b)
        b.set_item(_PREV, a)
        b.set_item(_NEXT, c)
        c.set_item(_PREV, b)
        root.set_item(_FIRST, a)
        root.set_item(_LAST, c)
        root.set_item(_COUNT, COSInteger.get(3))
    elif name == "cycle_next":
        a, b = _item("A"), _item("B")
        a.set_item(_NEXT, b)
        b.set_item(_PREV, a)
        b.set_item(_NEXT, a)
        a.set_item(_PREV, b)
        root.set_item(_FIRST, a)
        root.set_item(_LAST, b)
    elif name == "self_cycle":
        a = _item("A")
        a.set_item(_NEXT, a)
        root.set_item(_FIRST, a)
        root.set_item(_LAST, a)
    elif name == "first_without_last":
        a, b = _item("A"), _item("B")
        a.set_item(_NEXT, b)
        b.set_item(_PREV, a)
        root.set_item(_FIRST, a)
    elif name == "broken_prev":
        a, b, c = _item("A"), _item("B"), _item("C")
        a.set_item(_NEXT, b)
        b.set_item(_NEXT, c)
        c.set_item(_PREV, b)
        root.set_item(_FIRST, a)
        root.set_item(_LAST, c)
    elif name == "title_variants":
        s = _item("Str")
        nm = COSDictionary()
        nm.set_item(_TITLE, _N("NameTitle"))
        miss = COSDictionary()
        s.set_item(_NEXT, nm)
        nm.set_item(_NEXT, miss)
        root.set_item(_FIRST, s)
        root.set_item(_LAST, miss)
    elif name == "dest_and_action":
        both = _item("Both")
        both.set_item(_DEST, _dest_fit())
        both.set_item(_A, _go_to_action())
        dest_only = _item("DestOnly")
        dest_only.set_item(_DEST, _dest_fit())
        act_only = _item("ActOnly")
        act_only.set_item(_A, _go_to_action())
        both.set_item(_NEXT, dest_only)
        dest_only.set_item(_NEXT, act_only)
        root.set_item(_FIRST, both)
        root.set_item(_LAST, act_only)
    elif name == "action_wrong_type":
        a = _item("A")
        a.set_item(_A, COSInteger.ONE)
        root.set_item(_FIRST, a)
        root.set_item(_LAST, a)
    elif name == "color_variants":
        good = _item("Good")
        good.set_item(_C, _color_triple(1.0, 0.0, 0.0))
        short = _item("Short")
        two = COSArray()
        two.add(COSFloat(0.5))
        two.add(COSFloat(0.5))
        short.set_item(_C, two)
        bad_elem = _item("BadElem")
        bad = COSArray()
        bad.add(COSFloat(0.25))
        bad.add(_N("X"))
        bad.add(COSFloat(0.75))
        bad_elem.set_item(_C, bad)
        not_arr = _item("NotArr")
        not_arr.set_item(_C, COSInteger.ONE)
        good.set_item(_NEXT, short)
        short.set_item(_NEXT, bad_elem)
        bad_elem.set_item(_NEXT, not_arr)
        root.set_item(_FIRST, good)
        root.set_item(_LAST, not_arr)
    elif name == "flag_variants":
        italic = _item("Italic")
        italic.set_item(_F, COSInteger.get(1))
        bold = _item("Bold")
        bold.set_item(_F, COSInteger.get(2))
        both = _item("BoldItalic")
        both.set_item(_F, COSInteger.get(3))
        float_flag = _item("Float")
        float_flag.set_item(_F, COSFloat(1.0))
        str_flag = _item("Str")
        str_flag.set_item(_F, COSString("1"))
        italic.set_item(_NEXT, bold)
        bold.set_item(_NEXT, both)
        both.set_item(_NEXT, float_flag)
        float_flag.set_item(_NEXT, str_flag)
        root.set_item(_FIRST, italic)
        root.set_item(_LAST, str_flag)
    elif name == "count_open":
        a = _item("Open")
        a.set_item(_COUNT, COSInteger.get(2))
        b = _item("Closed")
        b.set_item(_COUNT, COSInteger.get(-2))
        c = _item("Zero")
        c.set_item(_COUNT, COSInteger.ZERO)
        e = _item("NoCount")
        a.set_item(_NEXT, b)
        b.set_item(_NEXT, c)
        c.set_item(_NEXT, e)
        root.set_item(_FIRST, a)
        root.set_item(_LAST, e)
    elif name == "root_count_negative":
        a = _item("A")
        root.set_item(_FIRST, a)
        root.set_item(_LAST, a)
        root.set_item(_COUNT, COSInteger.get(-1))
    elif name == "nested_children":
        parent = _item("Parent")
        parent.set_item(_COUNT, COSInteger.get(2))
        kid1, kid2 = _item("Kid1"), _item("Kid2")
        kid1.set_item(_PARENT, parent)
        kid2.set_item(_PARENT, parent)
        kid1.set_item(_NEXT, kid2)
        kid2.set_item(_PREV, kid1)
        parent.set_item(_FIRST, kid1)
        parent.set_item(_LAST, kid2)
        parent.set_item(_PARENT, root)
        root.set_item(_FIRST, parent)
        root.set_item(_LAST, parent)
    else:  # pragma: no cover - defensive
        raise ValueError(name)
    return root


def _json_str(s: str | None) -> str:
    if s is None:
        return "null"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fmt(f: float) -> str:
    # Mirror the probe's Float.toString-ish formatting: integral floats render
    # as plain ints, others as the shortest round-trip-ish form.
    if f == int(f):
        return str(int(f))
    return repr(f)


def _color_cell(item: PDOutlineItem) -> str:
    # Use the upstream-mirroring accessor (materialises [0,0,0] default and
    # runs init_components), not get_text_color() which diverges by design.
    try:
        color = item.get_text_color_pd_color()
        comps = color.get_components()
        return "[" + ",".join(_fmt(c) for c in comps) + "]"
    except Exception as exc:  # noqa: BLE001 - mirror probe's generic catch
        return f"ERR:{type(exc).__name__}"


def _child_cell(item: PDOutlineItem) -> str:
    try:
        dest = str(item.get_destination() is not None).lower()
    except Exception as exc:  # noqa: BLE001 - mirror probe's generic catch
        dest = f"ERR:{type(exc).__name__}"
    return (
        f"title={_json_str(item.get_title())}"
        f" dest={dest}"
        f" act={str(item.get_action() is not None).lower()}"
        f" italic={str(item.is_italic()).lower()}"
        f" bold={str(item.is_bold()).lower()}"
        f" count={item.get_open_count()}"
        f" color={_color_cell(item)}"
    )


def _python_tree(name: str) -> str:
    root = _tree_root(name)
    outline = PDDocumentOutline(root)
    parts = [
        f"CASE {name}",
        f"root_open={str(outline.is_node_open()).lower()}",
        f"root_count={outline.get_open_count()}",
        f"has_children={str(outline.has_children()).lower()}",
    ]
    cells = []
    yielded = 0
    try:
        for child in outline.children():
            cells.append(f"[{_child_cell(child)}]")
            yielded += 1
            if yielded > 50:
                cells.append("[RUNAWAY]")
                break
        parts.append(f"yielded={yielded}")
        parts.extend(cells)
    except Exception as exc:  # noqa: BLE001 - mirror probe's generic catch
        parts.append(f"yielded=ERR:{type(exc).__name__}")
    return " ".join(parts)


@requires_oracle
@pytest.mark.parametrize("case_name", _TREE_CASES)
def test_tree_surface_matches(case_name: str) -> None:
    assert _python_tree(case_name) + "\n" == run_probe_text(
        "OutlineFuzzProbe", "tree", case_name
    )


# ---------------------------------------------------------------------------
# node surface
# ---------------------------------------------------------------------------

_NODE_CASES = (
    "bare",
    "first_only",
    "last_only",
    "first_last_same",
    "first_wrong_type",
    "next_prev",
    "count_negative",
    "count_positive",
)


def _node_dict(name: str) -> COSDictionary:
    d = _item("Self")
    if name == "bare":
        pass
    elif name == "first_only":
        c = _item("OnlyChild")
        c.set_item(_PARENT, d)
        d.set_item(_FIRST, c)
    elif name == "last_only":
        c = _item("OnlyChild")
        c.set_item(_PARENT, d)
        d.set_item(_LAST, c)
    elif name == "first_last_same":
        c = _item("OnlyChild")
        c.set_item(_PARENT, d)
        d.set_item(_FIRST, c)
        d.set_item(_LAST, c)
        d.set_item(_COUNT, COSInteger.ONE)
    elif name == "first_wrong_type":
        d.set_item(_FIRST, COSInteger.ONE)
    elif name == "next_prev":
        d.set_item(_NEXT, _item("Next"))
        d.set_item(_PREV, _item("Prev"))
    elif name == "count_negative":
        d.set_item(_COUNT, COSInteger.get(-3))
    elif name == "count_positive":
        d.set_item(_COUNT, COSInteger.get(3))
    else:  # pragma: no cover - defensive
        raise ValueError(name)
    return d


def _title_of(item: PDOutlineItem | None) -> str:
    if item is None:
        return "null"
    return item.get_title() if item.get_title() is not None else "null"


def _python_node(name: str) -> str:
    item = PDOutlineItem(_node_dict(name))
    return (
        f"CASE {name}"
        f" has_children={str(item.has_children()).lower()}"
        f" open_count={item.get_open_count()}"
        f" is_open={str(item.is_node_open()).lower()}"
        f" first={_title_of(item.get_first_child())}"
        f" last={_title_of(item.get_last_child())}"
        f" next={_title_of(item.get_next_sibling())}"
        f" prev={_title_of(item.get_previous_sibling())}"
        f" collapsed={str(item.get_open_count() < 0).lower()}"
    )


@requires_oracle
@pytest.mark.parametrize("case_name", _NODE_CASES)
def test_node_surface_matches(case_name: str) -> None:
    assert _python_node(case_name) + "\n" == run_probe_text(
        "OutlineFuzzProbe", "node", case_name
    )
