"""Live PDFBox differential parity for name/number-tree ``getValue`` descent.

Pins :meth:`PDNameTreeNode.get_value` / :meth:`PDNumberTreeNode.get_value`
``/Limits`` binary-descent narrowing against Apache PDFBox 3.0.7 on shapes the
existing ``test_name_number_tree_oracle`` deliberately does NOT exercise. The
Java side is ``oracle/probes/NameNumTreeRangeProbe.java``.

The earlier probe used "dense" leaves whose ``/Limits`` exactly bracket their
only two keys, so every query either matched a leaf's whole span or fell into a
between-leaf gap. This probe targets the harder narrowing cases:

* **Sparse leaves** — a leaf's ``/Limits`` span is wide but the leaf holds keys
  strictly inside the span that are absent (a hole). A query for a hole key
  lands inside exactly one kid's range, descends, misses and must return
  ``None`` without spuriously matching a sibling.
* **Boundary keys** equal to a kid's lower OR upper ``/Limits`` value.
* **Adjacent (touching) ranges** — one kid's upper limit (``20``) abuts the
  next kid's lower limit (``21``): the descent must pick the right kid.
* **Negative keys** and keys spanning the negative/zero boundary, to pin signed
  integer comparison in the number-tree descent.

Both libraries carry explicit ``/Limits`` on every non-root node here, so this
is a well-formed-input parity pin (no malformed-input divergence is involved).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode
from tests.oracle.harness import requires_oracle, run_probe_text

_NAMES = COSName.get_pdf_name("Names")
_NUMS = COSName.get_pdf_name("Nums")
_LIMITS = COSName.get_pdf_name("Limits")
_KIDS = COSName.KIDS


# ---------- value-typed node subclasses (mirror the Java probe) ----------


class _StrNode(PDNameTreeNode[str]):
    def convert_cos_to_value(self, base: COSBase) -> str:
        assert isinstance(base, COSString)
        return base.get_string()

    def convert_value_to_cos(self, value: str) -> COSBase:
        return COSString(value)

    def create_child_node(self, dic: COSDictionary) -> _StrNode:
        return _StrNode(dic)


class _IntNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        assert isinstance(base, COSInteger)
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNode:
        return _IntNode(dic)


# ---------- COS builders (explicit /Limits so leaves can be sparse) ----------


def _name_leaf(pairs: list[tuple[str, str]], lo: str, hi: str) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for key, val in pairs:
        arr.add(COSString(key))
        arr.add(COSString(val))
    d.set_item(_NAMES, arr)
    lim = COSArray()
    lim.add(COSString(lo))
    lim.add(COSString(hi))
    d.set_item(_LIMITS, lim)
    return d


def _name_intermediate(children: list[COSDictionary], lo: str, hi: str) -> COSDictionary:
    d = COSDictionary()
    kids = COSArray()
    for child in children:
        kids.add(child)
    d.set_item(_KIDS, kids)
    lim = COSArray()
    lim.add(COSString(lo))
    lim.add(COSString(hi))
    d.set_item(_LIMITS, lim)
    return d


def _num_leaf(pairs: list[tuple[int, int]], lo: int, hi: int) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for key, val in pairs:
        arr.add(COSInteger.get(key))
        arr.add(COSInteger.get(val))
    d.set_item(_NUMS, arr)
    lim = COSArray()
    lim.add(COSInteger.get(lo))
    lim.add(COSInteger.get(hi))
    d.set_item(_LIMITS, lim)
    return d


def _num_intermediate(children: list[COSDictionary], lo: int, hi: int) -> COSDictionary:
    d = COSDictionary()
    kids = COSArray()
    for child in children:
        kids.add(child)
    d.set_item(_KIDS, kids)
    lim = COSArray()
    lim.add(COSInteger.get(lo))
    lim.add(COSInteger.get(hi))
    d.set_item(_LIMITS, lim)
    return d


# ---------- canonical report builders (mirror NameNumTreeRangeProbe output) ----------


def _lim(value: object) -> str:
    return "null" if value is None else str(value)


def _dump_name_limits(node: PDNameTreeNode[str], depth: int, lines: list[str]) -> None:
    indent = "  " * depth
    lines.append(f"  {indent}{_lim(node.get_lower_limit())}..{_lim(node.get_upper_limit())}")
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _dump_name_limits(kid, depth + 1, lines)


def _report_name(node: _StrNode, keys: list[str]) -> str:
    lines = ["limits"]
    _dump_name_limits(node, 0, lines)
    lines.append("get")
    for key in keys:
        val = node.get_value(key)
        lines.append(f"  get({key}) = {'null' if val is None else val}")
    return "\n".join(lines) + "\n"


def _dump_num_limits(node: PDNumberTreeNode[int], depth: int, lines: list[str]) -> None:
    indent = "  " * depth
    lines.append(f"  {indent}{_lim(node.get_lower_limit())}..{_lim(node.get_upper_limit())}")
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _dump_num_limits(kid, depth + 1, lines)


def _report_num(node: _IntNode, keys: list[int]) -> str:
    lines = ["limits"]
    _dump_num_limits(node, 0, lines)
    lines.append("get")
    for key in keys:
        val = node.get_value(key)
        lines.append(f"  get({key}) = {'null' if val is None else val}")
    return "\n".join(lines) + "\n"


# ---------- tree fixtures (identical shapes to the Java probe) ----------


def _name_sparse() -> _StrNode:
    leaf_a = _name_leaf([("alpha", "1"), ("charlie", "3"), ("golf", "7")], "alpha", "golf")
    leaf_b = _name_leaf([("india", "9"), ("mike", "13"), ("zulu", "26")], "india", "zulu")
    return _StrNode(_name_intermediate([leaf_a, leaf_b], "alpha", "zulu"))


def _num_sparse() -> _IntNode:
    leaf_p = _num_leaf([(-10, 100), (0, 200), (5, 250), (20, 300)], -10, 20)
    leaf_q = _num_leaf([(21, 310), (30, 400), (50, 500)], 21, 50)
    return _IntNode(_num_intermediate([leaf_p, leaf_q], -10, 50))


_NAME_SPARSE_KEYS = [
    "alpha", "charlie", "golf", "india", "mike", "zulu",
    "bravo", "delta", "echo", "foxtrot",
    "hotel",
    "aaa", "zzzz",
]
_NUM_SPARSE_KEYS = [
    -10, 0, 5, 20, 21, 30, 50,
    -5, 3, 10, 19, 22, 40,
    -11, 51, 1000,
]


@requires_oracle
def test_name_number_tree_range_matches_pdfbox() -> None:
    """Sparse-leaf / touching-range / negative-key descent matches PDFBox."""
    java = run_probe_text("NameNumTreeRangeProbe")

    sections = {
        "# name sparse": _report_name(_name_sparse(), _NAME_SPARSE_KEYS),
        "# num sparse": _report_num(_num_sparse(), _NUM_SPARSE_KEYS),
    }
    py = "".join(f"{header}\n{body}" for header, body in sections.items())
    assert py == java, (
        "name/number-tree range descent diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
