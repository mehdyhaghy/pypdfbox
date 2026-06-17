"""Live PDFBox differential parity for the generic name / number trees.

Pins :class:`PDNameTreeNode` and :class:`PDNumberTreeNode` traversal against
Apache PDFBox 3.0.7 on COS structures built **in-probe** (no PDF file is
loaded). The Java side is ``oracle/probes/NameNumTreeProbe.java``; the Python
side rebuilds the identical COS shapes and emits a string-for-string report.

Three fields are pinned, on single-level leaves and 2-3-deep balanced trees
with intermediate ``/Kids`` nodes carrying ``/Limits``:

* the **flattened, sorted key->value mapping** — pypdfbox bakes the whole-tree
  recursion into ``get_names`` / ``get_numbers``; the probe reproduces it by
  recursing through ``getKids`` (PDFBox's own ``getNames`` / ``getNumbers``
  are non-recursive and return ``null`` on an intermediate node — see the
  DIVERGENCE note below).
* each node's **lower / upper ``/Limits``**, walked in document order.
* the result of **``get(key)``** for present, absent and boundary keys — this
  exercises the ``/Limits`` binary-descent narrowing through intermediate
  nodes.

DIVERGENCE 1 (documented, not a bug): PDFBox ``getNames()`` / ``getNumbers()``
return only *this* node's leaf mapping (``null`` on a ``/Kids`` node), whereas
pypdfbox ``get_names`` / ``get_numbers`` recurse and flatten the whole subtree.
Both surfaces agree on a single-level leaf; the recursive flatten is asserted
against the probe's explicit getKids recursion (the same recursion
``EmbedFilesProbe`` performs). Recorded in CHANGES.md.

DIVERGENCE 2 (documented, not a bug — malformed input only): when an
intermediate node's kid is missing ``/Limits`` mid-list, the two libraries
diverge. PDFBox's number-tree ``getValue`` *throws NullPointerException*
(``PDNumberTreeNode.getValue`` line 166 dereferences a null lower limit); its
name-tree ``getValue`` searches the no-limit kid but then stops and does not
fall through to a later limited sibling. pypdfbox guards against the null
limit and continues the fall-through search (``pd_number_tree_node.py`` lines
246-250, ``pd_name_tree_node.py`` lines 214-218), so it neither crashes nor
loses the later sibling. A well-formed PDF name/number tree carries ``/Limits``
on every non-root node, so this only surfaces on malformed input. The oracle
crashes on the number case and stops-early on the name case, so these shapes
are NOT asserted here; the robust pypdfbox behaviour is pinned in
``test_no_limit_kid_*`` below. Recorded in CHANGES.md.
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


# ---------- COS builders (mirror the Java probe builders) ----------


def _name_leaf(pairs: list[tuple[str, str]], *, limits: bool = False) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for key, val in pairs:
        arr.add(COSString(key))
        arr.add(COSString(val))
    d.set_item(_NAMES, arr)
    if limits:
        lim = COSArray()
        lim.add(COSString(pairs[0][0]))
        lim.add(COSString(pairs[-1][0]))
        d.set_item(_LIMITS, lim)
    return d


def _name_intermediate(children: list[COSDictionary]) -> COSDictionary:
    d = COSDictionary()
    kids = COSArray()
    for child in children:
        kids.add(child)
    d.set_item(_KIDS, kids)
    first_lim = children[0].get_dictionary_object(_LIMITS)
    last_lim = children[-1].get_dictionary_object(_LIMITS)
    assert isinstance(first_lim, COSArray) and isinstance(last_lim, COSArray)
    lim = COSArray()
    lim.add(first_lim.get(0))
    lim.add(last_lim.get(1))
    d.set_item(_LIMITS, lim)
    return d


def _num_leaf(pairs: list[tuple[int, int]], *, limits: bool = False) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for key, val in pairs:
        arr.add(COSInteger.get(key))
        arr.add(COSInteger.get(val))
    d.set_item(_NUMS, arr)
    if limits:
        lim = COSArray()
        lim.add(COSInteger.get(pairs[0][0]))
        lim.add(COSInteger.get(pairs[-1][0]))
        d.set_item(_LIMITS, lim)
    return d


def _num_intermediate(children: list[COSDictionary]) -> COSDictionary:
    d = COSDictionary()
    kids = COSArray()
    for child in children:
        kids.add(child)
    d.set_item(_KIDS, kids)
    first_lim = children[0].get_dictionary_object(_LIMITS)
    last_lim = children[-1].get_dictionary_object(_LIMITS)
    assert isinstance(first_lim, COSArray) and isinstance(last_lim, COSArray)
    lim = COSArray()
    lim.add(first_lim.get(0))
    lim.add(last_lim.get(1))
    d.set_item(_LIMITS, lim)
    return d


# ---------- canonical report builders (mirror NameNumTreeProbe output) ----------


def _lim(value: object) -> str:
    return "null" if value is None else str(value)


def _collect_names(node: PDNameTreeNode[str], sink: dict[str, str]) -> None:
    """Whole-tree flatten via the same getKids recursion the probe performs.

    We must NOT call ``node.get_names()`` recursively here because pypdfbox's
    ``get_names`` already recurses; calling it on the root would double the
    work but, more importantly, we want to mirror the probe's explicit walk so
    the leaf-by-leaf merge order is identical. We read the leaf arm directly.
    """
    leaf = node.get_cos_object().get_dictionary_object(_NAMES)
    if isinstance(leaf, COSArray):
        own = node.get_names()
        if own:
            sink.update(own)
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _collect_names(kid, sink)


def _report_name(node: _StrNode, keys: list[str]) -> str:
    flat: dict[str, str] = {}
    _collect_names(node, flat)
    lines = [f"flatten {len(flat)}"]
    for key in sorted(flat):
        lines.append(f"  {key} -> {flat[key]}")
    lines.append("limits")
    _dump_name_limits(node, 0, lines)
    lines.append("get")
    for key in keys:
        val = node.get_value(key)
        lines.append(f"  get({key}) = {'null' if val is None else val}")
    return "\n".join(lines) + "\n"


def _dump_name_limits(node: PDNameTreeNode[str], depth: int, lines: list[str]) -> None:
    indent = "  " * depth
    lines.append(f"  {indent}{_lim(node.get_lower_limit())}..{_lim(node.get_upper_limit())}")
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _dump_name_limits(kid, depth + 1, lines)


def _collect_numbers(node: PDNumberTreeNode[int], sink: dict[int, int]) -> None:
    leaf = node.get_cos_object().get_dictionary_object(_NUMS)
    if isinstance(leaf, COSArray):
        own = node.get_numbers()
        if own:
            sink.update(own)
    kids = node.get_kids()
    if kids is not None:
        for kid in kids:
            _collect_numbers(kid, sink)


def _report_num(node: _IntNode, keys: list[int]) -> str:
    flat: dict[int, int] = {}
    _collect_numbers(node, flat)
    lines = [f"flatten {len(flat)}"]
    for key in sorted(flat):
        lines.append(f"  {key} -> {flat[key]}")
    lines.append("limits")
    _dump_num_limits(node, 0, lines)
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


# ---------- tree fixtures (identical shapes to the Java probe) ----------


def _name_single() -> _StrNode:
    return _StrNode(_name_leaf([("apple", "A"), ("mango", "M"), ("pear", "P")]))


def _name_multi2() -> _StrNode:
    return _StrNode(
        _name_intermediate(
            [
                _name_leaf([("alpha", "1"), ("bravo", "2")], limits=True),
                _name_leaf([("delta", "3"), ("echo", "4")], limits=True),
                _name_leaf([("golf", "5"), ("hotel", "6")], limits=True),
            ]
        )
    )


def _name_multi3() -> _StrNode:
    left = _name_intermediate(
        [
            _name_leaf([("ant", "a"), ("bee", "b")], limits=True),
            _name_leaf([("cat", "c"), ("dog", "d")], limits=True),
        ]
    )
    right = _name_intermediate(
        [
            _name_leaf([("eel", "e"), ("fox", "f")], limits=True),
            _name_leaf([("goat", "g"), ("hen", "h")], limits=True),
        ]
    )
    return _StrNode(_name_intermediate([left, right]))


def _num_single() -> _IntNode:
    return _IntNode(_num_leaf([(1, 100), (5, 500), (9, 900)]))


def _num_multi2() -> _IntNode:
    return _IntNode(
        _num_intermediate(
            [
                _num_leaf([(0, 1000), (2, 1002)], limits=True),
                _num_leaf([(10, 1010), (12, 1012)], limits=True),
                _num_leaf([(20, 1020), (25, 1025)], limits=True),
            ]
        )
    )


def _num_multi3() -> _IntNode:
    left = _num_intermediate(
        [
            _num_leaf([(1, 11), (3, 13)], limits=True),
            _num_leaf([(5, 15), (7, 17)], limits=True),
        ]
    )
    right = _num_intermediate(
        [
            _num_leaf([(10, 110), (14, 114)], limits=True),
            _num_leaf([(20, 120), (28, 128)], limits=True),
        ]
    )
    return _IntNode(_num_intermediate([left, right]))


_NAME_SINGLE_KEYS = ["apple", "mango", "pear", "kiwi", "aardvark", "zebra"]
_NAME_MULTI2_KEYS = [
    "alpha", "bravo", "delta", "echo", "golf", "hotel",
    "charlie", "foxtrot", "zulu", "aaa", "echo", "golf",
]
_NAME_MULTI3_KEYS = [
    "ant", "dog", "eel", "hen", "bee", "goat",
    "bird", "elk", "zzz", "aaa", "cat", "fox",
]
_NUM_SINGLE_KEYS = [1, 5, 9, 0, 3, 12, -1]
_NUM_MULTI2_KEYS = [0, 2, 10, 12, 20, 25, 1, 11, 15, 26, -5, 21]
_NUM_MULTI3_KEYS = [1, 7, 10, 28, 5, 20, 2, 8, 30, 0, 14, 100]


@requires_oracle
def test_name_number_tree_matches_pdfbox() -> None:
    """One probe run emits all six sections; assert each against pypdfbox."""
    java = run_probe_text("NameNumTreeProbe")

    sections = {
        "# name single": _report_name(_name_single(), _NAME_SINGLE_KEYS),
        "# name multi2": _report_name(_name_multi2(), _NAME_MULTI2_KEYS),
        "# name multi3": _report_name(_name_multi3(), _NAME_MULTI3_KEYS),
        "# num single": _report_num(_num_single(), _NUM_SINGLE_KEYS),
        "# num multi2": _report_num(_num_multi2(), _NUM_MULTI2_KEYS),
        "# num multi3": _report_num(_num_multi3(), _NUM_MULTI3_KEYS),
    }

    py = "".join(f"{header}\n{body}" for header, body in sections.items())
    assert py == java, (
        "generic name/number tree report diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


# ---------- malformed-input divergences (pypdfbox-only; oracle crashes) ----------


def test_no_limit_kid_name_falls_through() -> None:
    """A name-tree kid missing ``/Limits`` mid-list must not break descent.

    DIVERGENCE 2 (see module docstring): PDFBox stops at the no-limit kid and
    fails to reach the later limited sibling. pypdfbox falls through, so a key
    living in a later sibling (``golf``/``hotel``) still resolves. This is a
    robustness improvement on malformed input, pinned here because the oracle
    cannot model it.
    """
    node = _StrNode(
        _name_intermediate(
            [
                _name_leaf([("alpha", "1"), ("bravo", "2")], limits=True),
                _name_leaf([("delta", "3"), ("echo", "4")]),  # no /Limits
                _name_leaf([("golf", "5"), ("hotel", "6")], limits=True),
            ]
        )
    )
    assert node.get_value("alpha") == "1"
    assert node.get_value("delta") == "3"  # found via no-limit fallback search
    assert node.get_value("golf") == "5"  # PDFBox returns None here; pypdfbox finds it
    assert node.get_value("hotel") == "6"
    assert node.get_value("zzz") is None


def test_no_limit_kid_number_no_crash() -> None:
    """A number-tree kid missing ``/Limits`` must not raise.

    DIVERGENCE 2 (see module docstring): PDFBox's ``getValue`` throws
    NullPointerException dereferencing the null lower limit. pypdfbox guards
    the null and resolves every present key.
    """
    node = _IntNode(
        _num_intermediate(
            [
                _num_leaf([(0, 1000), (2, 1002)], limits=True),
                _num_leaf([(10, 1010), (12, 1012)]),  # no /Limits
                _num_leaf([(20, 1020), (25, 1025)], limits=True),
            ]
        )
    )
    assert node.get_value(0) == 1000
    assert node.get_value(10) == 1010  # found via no-limit fallback search
    assert node.get_value(25) == 1025  # PDFBox crashes before reaching this
    assert node.get_value(99) is None


# ---------- save -> reload round-trip (serialization parity) ----------
#
# The tests above build the COS in memory and never touch the writer. This one
# closes that gap: pypdfbox SAVES a PDF carrying a 3-deep name tree (catalog
# /Names /JavaScript) and a 3-deep number tree (catalog /PageLabels), then both
# libraries re-parse the *same* saved file and descend through it. This pins the
# writer's serialization of a balanced /Kids+/Limits tree — the indirect-object
# layout, the sorted /Names / /Nums arrays and the /Limits [lo hi] arrays must
# all survive so PDFBox can binary-descend through them identically.

# 8-entry name tree, 3 levels deep: root /Kids -> 2 intermediates -> 4 leaves.
_RT_NAME_KEYS = [
    "alpha", "bravo", "delta", "echo", "golf", "hotel", "kilo", "lima",
    "charlie", "foxtrot", "india", "zulu", "aaa", "echo", "golf",
]
# 10-entry number tree, 3 levels deep: root /Kids -> 2 intermediates -> 5
# leaves. Ranges are strictly non-overlapping and ascending, as a well-formed
# number tree requires.
_RT_NUM_KEYS = [0, 2, 10, 12, 20, 25, 30, 33, 40, 47, 1, 11, 26, 35, -5, 50, 100]


def _rt_name_root() -> COSDictionary:
    """Root /Kids node (no /Limits) of a 3-deep name tree."""
    left = _name_intermediate(
        [
            _name_leaf([("alpha", "1"), ("bravo", "2")], limits=True),
            _name_leaf([("delta", "3"), ("echo", "4")], limits=True),
        ]
    )
    right = _name_intermediate(
        [
            _name_leaf([("golf", "5"), ("hotel", "6")], limits=True),
            _name_leaf([("kilo", "7"), ("lima", "8")], limits=True),
        ]
    )
    root = COSDictionary()
    kids = COSArray()
    kids.add(left)
    kids.add(right)
    root.set_item(_KIDS, kids)  # root: /Kids only, no /Limits
    return root


def _rt_num_root() -> COSDictionary:
    """Root /Kids node (no /Limits) of a 3-deep number tree."""
    left = _num_intermediate(
        [
            _num_leaf([(0, 1000), (2, 1002)], limits=True),
            _num_leaf([(10, 1010), (12, 1012)], limits=True),
            _num_leaf([(20, 1020), (25, 1025)], limits=True),
        ]
    )
    right = _num_intermediate(
        [
            _num_leaf([(30, 1030), (33, 1033)], limits=True),
            _num_leaf([(40, 1040), (47, 1047)], limits=True),
        ]
    )
    root = COSDictionary()
    kids = COSArray()
    kids.add(left)
    kids.add(right)
    root.set_item(_KIDS, kids)  # root: /Kids only, no /Limits
    return root


@requires_oracle
def test_round_trip_multi_level_trees_match_pdfbox(tmp_path) -> None:
    """pypdfbox-saved multi-level trees re-parse + descend identically.

    Builds a 3-deep name tree (catalog /Names /JavaScript) and number tree
    (catalog /PageLabels), saves with pypdfbox, then asserts pypdfbox's
    reload-and-descend report equals PDFBox's report of the same file.
    """
    from pypdfbox.cos import COSName as _COSName
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    pdf_path = tmp_path / "name_num_tree.pdf"

    # --- build + save with pypdfbox ---
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        names_dict = COSDictionary()
        names_dict.set_item(_COSName.get_pdf_name("JavaScript"), _rt_name_root())
        catalog.set_item(_COSName.get_pdf_name("Names"), names_dict)
        catalog.set_item(_COSName.get_pdf_name("PageLabels"), _rt_num_root())
        doc.save(str(pdf_path))
    finally:
        doc.close()

    # --- reload with pypdfbox and build the report from the re-parsed COS ---
    reloaded = PDDocument.load(str(pdf_path))
    try:
        cat = reloaded.get_document_catalog().get_cos_object()
        nd = cat.get_dictionary_object(COSName.get_pdf_name("Names"))
        assert isinstance(nd, COSDictionary)
        js_root = nd.get_dictionary_object(COSName.get_pdf_name("JavaScript"))
        assert isinstance(js_root, COSDictionary)
        labels_root = cat.get_dictionary_object(COSName.get_pdf_name("PageLabels"))
        assert isinstance(labels_root, COSDictionary)

        py = (
            "# name tree\n"
            + _report_name(_StrNode(js_root), _RT_NAME_KEYS)
            + "# num tree\n"
            + _report_num(_IntNode(labels_root), _RT_NUM_KEYS)
        )
    finally:
        reloaded.close()

    java = run_probe_text("NameNumTreeRoundTripProbe", str(pdf_path))
    assert py == java, (
        "round-tripped multi-level name/number tree diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
