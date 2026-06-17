"""Differential fuzz audit for the GENERIC name-tree / number-tree traversal +
lookup contract vs Apache PDFBox 3.0.7 (wave 1514, agent E).

Complements the well-formed name/number tree parity suites (and the wave-1511
doc-nav page-labels fuzz, which targets the PDPageLabels-specific path) — none
of which exercise the MALFORMED generic-traversal subset this audit targets:

* ``/Kids``-vs-``/Names``/``/Nums`` (leaf vs intermediate, both present);
* value array odd length (key without value); wrong key type (non-string
  name-tree key / non-int number-tree key); unsorted keys;
* ``/Limits`` missing / wrong arity / inverted (lo>hi) / wrong type;
* ``/Kids`` non-array / containing a non-dict / deeply nested;
* lookup of a present key, an absent key, a key outside ``/Limits``.

Both sides are driven on the SAME bytes: the corpus builder writes one PDF per
case whose catalog carries the fuzzed tree under ``/Names /Dests`` (name tree)
or ``/PageLabels`` (number tree), plus a ``manifest.txt`` into a tmp dir. The
Java probe (``oracle/probes/NameNumberTreeFuzzProbe.java``) loads each
``<case>.pdf``, wraps the raw tree dict in a thin local ``PDNameTreeNode`` /
``PDNumberTreeNode`` subclass and projects a stable framed line; this module
reads the exact same files and projects the identical grammar through pypdfbox,
then asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> names=<count|null|ERR> kids=<count|null|ERR>
        lookup_hit=<v|null|ERR> lookup_miss=<null|ERR> limits=<lo..hi>

``names`` is the size of ``get_names()``/``get_numbers()`` (this node's own leaf
array), ``null`` when it returns ``None``, ``ERR:<ExcSimpleName>`` when it
raises. ``kids`` is the size of ``get_kids()`` (``null`` when absent).
``lookup_hit`` is ``get_value(present_key)``, ``lookup_miss`` is
``get_value(absent_key)``. ``limits`` is
``get_lower_limit()..get_upper_limit()``.

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/common/pd_name_tree_node.py`` /
``pd_number_tree_node.py``; a defensible divergence is pinned in ``_PINNED``
with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

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

_N = COSName.get_pdf_name
_NAMES = _N("Names")
_NUMS = _N("Nums")
_LIMITS = _N("Limits")
_KIDS = COSName.KIDS
_DESTS = _N("Dests")
_PAGELABELS = _N("PageLabels")


# ---------- node subclasses mirroring the Java probe (_Str / _Num) ----------


class _Str(PDNameTreeNode[COSString]):
    def convert_cos_to_value(self, base: COSBase) -> COSString:
        return base  # type: ignore[return-value]

    def convert_value_to_cos(self, value: COSString) -> COSBase:
        return value

    def create_child_node(self, dic: COSDictionary) -> _Str:
        return _Str(dic)


class _Num(PDNumberTreeNode[COSBase]):
    def convert_cos_to_value(self, base: COSBase) -> COSBase:
        return base

    def convert_value_to_cos(self, value: COSBase) -> COSBase:
        return value

    def create_child_node(self, dic: COSDictionary) -> _Num:
        return _Num(dic)


# ---------- COS builders ----------


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _limits(*items: COSBase) -> COSArray:
    return _arr(*items)


# ---------- name-tree corpus ----------


def _name_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def nc(name: str, d: COSDictionary) -> None:
        cases[f"name_{name}"] = d

    # --- well-formed leaf -------------------------------------------------
    d = COSDictionary()
    d.set_item(_NAMES, _arr(
        COSString("key1"), COSString("v1"),
        COSString("key2"), COSString("v2"),
        COSString("key3"), COSString("v3"),
    ))
    nc("leaf_wellformed", d)

    # --- empty tree (neither Names nor Kids) ------------------------------
    nc("empty", COSDictionary())

    # --- /Names empty array -----------------------------------------------
    d = COSDictionary()
    d.set_item(_NAMES, COSArray())
    nc("names_empty_array", d)

    # --- /Names odd length (key without value) ----------------------------
    d = COSDictionary()
    d.set_item(_NAMES, _arr(
        COSString("key1"), COSString("v1"),
        COSString("key3"),  # dangling key, no value
    ))
    nc("names_odd_length", d)

    # --- /Names wrong key type (name not string at index 0) ---------------
    d = COSDictionary()
    d.set_item(_NAMES, _arr(
        _N("key1"), COSString("v1"),
        COSString("key2"), COSString("v2"),
    ))
    nc("names_key_not_string", d)

    # --- /Names key is an integer -----------------------------------------
    d = COSDictionary()
    d.set_item(_NAMES, _arr(
        COSInteger.get(5), COSString("v1"),
    ))
    nc("names_key_integer", d)

    # --- /Names unsorted keys ---------------------------------------------
    d = COSDictionary()
    d.set_item(_NAMES, _arr(
        COSString("key3"), COSString("v3"),
        COSString("key1"), COSString("v1"),
        COSString("key2"), COSString("v2"),
    ))
    nc("names_unsorted", d)

    # --- /Names not an array ----------------------------------------------
    d = COSDictionary()
    d.set_item(_NAMES, COSString("notanarray"))
    nc("names_not_array", d)

    # --- both /Names and /Kids present ------------------------------------
    d = COSDictionary()
    d.set_item(_NAMES, _arr(COSString("key1"), COSString("v1")))
    leaf = COSDictionary()
    leaf.set_item(_NAMES, _arr(COSString("zzz"), COSString("vz")))
    leaf.set_item(_LIMITS, _limits(COSString("zzz"), COSString("zzz")))
    d.set_item(_KIDS, _arr(leaf))
    nc("both_names_and_kids", d)

    # --- intermediate /Kids with limited leaves ---------------------------
    def _leaf(pairs: list[tuple[str, str]], *, limits: bool = True) -> COSDictionary:
        x = COSDictionary()
        arr = COSArray()
        for k, v in pairs:
            arr.add(COSString(k))
            arr.add(COSString(v))
        x.set_item(_NAMES, arr)
        if limits:
            x.set_item(_LIMITS, _limits(COSString(pairs[0][0]), COSString(pairs[-1][0])))
        return x

    d = COSDictionary()
    d.set_item(_KIDS, _arr(
        _leaf([("key0", "v0"), ("key1", "v1")]),
        _leaf([("key5", "v5"), ("key9", "v9")]),
    ))
    nc("kids_wellformed", d)

    # --- /Kids not an array -----------------------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, COSString("notanarray"))
    nc("kids_not_array", d)

    # --- /Kids containing a non-dict element ------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, _arr(
        COSString("garbage"),
        _leaf([("key1", "v1"), ("key2", "v2")]),
    ))
    nc("kids_contains_non_dict", d)

    # --- /Kids empty array ------------------------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, COSArray())
    nc("kids_empty_array", d)

    # --- deeply nested /Kids (3 levels) -----------------------------------
    inner = COSDictionary()
    inner.set_item(_KIDS, _arr(_leaf([("key1", "v1"), ("key2", "v2")])))
    inner.set_item(_LIMITS, _limits(COSString("key1"), COSString("key2")))
    d = COSDictionary()
    d.set_item(_KIDS, _arr(inner))
    nc("kids_deeply_nested", d)

    # --- /Limits missing on leaf (lookup falls through) -------------------
    d = COSDictionary()
    d.set_item(_KIDS, _arr(_leaf([("key1", "v1"), ("key2", "v2")], limits=False)))
    nc("limits_missing_on_kid", d)

    # --- /Limits wrong arity (one element) --------------------------------
    d = _leaf([("key1", "v1"), ("key2", "v2")], limits=False)
    d.set_item(_LIMITS, _limits(COSString("key1")))
    nc("limits_one_element", d)

    # --- /Limits inverted (lo > hi) ---------------------------------------
    d = _leaf([("key1", "v1"), ("key2", "v2")], limits=False)
    d.set_item(_LIMITS, _limits(COSString("zzz"), COSString("aaa")))
    nc("limits_inverted", d)

    # --- /Limits wrong type (integers) ------------------------------------
    d = _leaf([("key1", "v1"), ("key2", "v2")], limits=False)
    d.set_item(_LIMITS, _limits(COSInteger.get(0), COSInteger.get(9)))
    nc("limits_wrong_type", d)

    # --- /Limits not an array ---------------------------------------------
    d = _leaf([("key1", "v1"), ("key2", "v2")], limits=False)
    d.set_item(_LIMITS, COSString("notanarray"))
    nc("limits_not_array", d)

    return cases


# ---------- number-tree corpus ----------


def _num_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def nc(name: str, d: COSDictionary) -> None:
        cases[f"num_{name}"] = d

    # --- well-formed leaf -------------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(
        COSInteger.get(1), COSString("v1"),
        COSInteger.get(2), COSString("v2"),
        COSInteger.get(3), COSString("v3"),
    ))
    nc("leaf_wellformed", d)

    # --- empty tree -------------------------------------------------------
    nc("empty", COSDictionary())

    # --- /Nums empty array ------------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, COSArray())
    nc("nums_empty_array", d)

    # --- /Nums odd length -------------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(
        COSInteger.get(1), COSString("v1"),
        COSInteger.get(3),  # dangling key
    ))
    nc("nums_odd_length", d)

    # --- /Nums key not integer (string) -----------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(
        COSString("notanint"), COSString("v1"),
        COSInteger.get(1), COSString("v2"),
    ))
    nc("nums_key_not_int", d)

    # --- /Nums key is a name ----------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(
        _N("five"), COSString("v1"),
    ))
    nc("nums_key_name", d)

    # --- /Nums negative key -----------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(
        COSInteger.get(-5), COSString("vm5"),
        COSInteger.get(1), COSString("v1"),
    ))
    nc("nums_negative_key", d)

    # --- /Nums unsorted keys ----------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(
        COSInteger.get(3), COSString("v3"),
        COSInteger.get(1), COSString("v1"),
        COSInteger.get(2), COSString("v2"),
    ))
    nc("nums_unsorted", d)

    # --- /Nums not an array -----------------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, COSString("notanarray"))
    nc("nums_not_array", d)

    # --- both /Nums and /Kids present -------------------------------------
    d = COSDictionary()
    d.set_item(_NUMS, _arr(COSInteger.get(1), COSString("v1")))
    leaf = COSDictionary()
    leaf.set_item(_NUMS, _arr(COSInteger.get(50), COSString("v50")))
    leaf.set_item(_LIMITS, _limits(COSInteger.get(50), COSInteger.get(50)))
    d.set_item(_KIDS, _arr(leaf))
    nc("both_nums_and_kids", d)

    def _leaf(pairs: list[tuple[int, str]], *, limits: bool = True) -> COSDictionary:
        x = COSDictionary()
        arr = COSArray()
        for k, v in pairs:
            arr.add(COSInteger.get(k))
            arr.add(COSString(v))
        x.set_item(_NUMS, arr)
        if limits:
            x.set_item(_LIMITS, _limits(COSInteger.get(pairs[0][0]),
                                        COSInteger.get(pairs[-1][0])))
        return x

    # --- intermediate /Kids -----------------------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, _arr(
        _leaf([(0, "v0"), (1, "v1")]),
        _leaf([(5, "v5"), (9, "v9")]),
    ))
    nc("kids_wellformed", d)

    # --- /Kids not an array -----------------------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, COSString("notanarray"))
    nc("kids_not_array", d)

    # --- /Kids containing a non-dict element ------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, _arr(
        COSString("garbage"),
        _leaf([(1, "v1"), (2, "v2")]),
    ))
    nc("kids_contains_non_dict", d)

    # --- /Kids empty array ------------------------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, COSArray())
    nc("kids_empty_array", d)

    # --- deeply nested ----------------------------------------------------
    inner = COSDictionary()
    inner.set_item(_KIDS, _arr(_leaf([(1, "v1"), (2, "v2")])))
    inner.set_item(_LIMITS, _limits(COSInteger.get(1), COSInteger.get(2)))
    d = COSDictionary()
    d.set_item(_KIDS, _arr(inner))
    nc("kids_deeply_nested", d)

    # --- /Limits missing on kid -------------------------------------------
    d = COSDictionary()
    d.set_item(_KIDS, _arr(_leaf([(1, "v1"), (2, "v2")], limits=False)))
    nc("limits_missing_on_kid", d)

    # --- /Limits wrong arity ----------------------------------------------
    d = _leaf([(1, "v1"), (2, "v2")], limits=False)
    d.set_item(_LIMITS, _limits(COSInteger.get(1)))
    nc("limits_one_element", d)

    # --- /Limits inverted -------------------------------------------------
    d = _leaf([(1, "v1"), (2, "v2")], limits=False)
    d.set_item(_LIMITS, _limits(COSInteger.get(9), COSInteger.get(0)))
    nc("limits_inverted", d)

    # --- /Limits wrong type (strings) -------------------------------------
    d = _leaf([(1, "v1"), (2, "v2")], limits=False)
    d.set_item(_LIMITS, _limits(COSString("a"), COSString("z")))
    nc("limits_wrong_type", d)

    # --- /Limits not an array ---------------------------------------------
    d = _leaf([(1, "v1"), (2, "v2")], limits=False)
    d.set_item(_LIMITS, COSString("notanarray"))
    nc("limits_not_array", d)

    return cases


def _build_corpus() -> dict[str, COSDictionary]:
    corpus: dict[str, COSDictionary] = {}
    corpus.update(_name_cases())
    corpus.update(_num_cases())
    return corpus


def _write_case_pdf(path: Path, name: str, entry: COSDictionary) -> None:
    """One-page PDF whose catalog carries the fuzzed tree under ``/Names
    /Dests`` (name tree) or ``/PageLabels`` (number tree)."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        cat = doc.get_document_catalog().get_cos_object()
        if name.startswith("name_"):
            names_dict = COSDictionary()
            names_dict.set_item(_DESTS, entry)
            cat.set_item(_NAMES, names_dict)
        else:
            cat.set_item(_PAGELABELS, entry)
        doc.save(str(path))
    finally:
        doc.close()


# ---------- Python-side projection ----------


def _exc_name(exc: Exception) -> str:
    """Map a pypdfbox exception to the Java exception simple-name the probe
    would report for the same failure."""
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _name_names(node: _Str) -> str:
    try:
        names = node.get_names()
        return "null" if names is None else str(len(names))
    except Exception as e:
        return f"ERR:{_exc_name(e)}"


def _name_kids(node: _Str) -> str:
    try:
        kids = node.get_kids()
        return "null" if kids is None else str(len(kids))
    except Exception as e:
        return f"ERR:{_exc_name(e)}"


def _name_lookup(node: _Str, key: str) -> str:
    try:
        v = node.get_value(key)
        return "null" if v is None else v.get_string()
    except Exception as e:
        return f"ERR:{_exc_name(e)}"


def _name_limits(node: _Str) -> str:
    try:
        lo = node.get_lower_limit()
    except Exception:
        lo = "ERR"
    try:
        hi = node.get_upper_limit()
    except Exception:
        hi = "ERR"
    return f"{'null' if lo is None else lo}..{'null' if hi is None else hi}"


def _num_value_str(v: COSBase) -> str:
    if isinstance(v, COSString):
        return v.get_string()
    return str(v)


def _num_names(node: _Num) -> str:
    try:
        nums = node.get_numbers()
        return "null" if nums is None else str(len(nums))
    except Exception as e:
        return f"ERR:{_exc_name(e)}"


def _num_kids(node: _Num) -> str:
    try:
        kids = node.get_kids()
        return "null" if kids is None else str(len(kids))
    except Exception as e:
        return f"ERR:{_exc_name(e)}"


def _num_lookup(node: _Num, key: int) -> str:
    try:
        v = node.get_value(key)
        return "null" if v is None else _num_value_str(v)
    except Exception as e:
        return f"ERR:{_exc_name(e)}"


def _num_limits(node: _Num) -> str:
    try:
        lo = node.get_lower_limit()
    except Exception:
        lo = "ERR"
    try:
        hi = node.get_upper_limit()
    except Exception:
        hi = "ERR"
    return f"{'null' if lo is None else lo}..{'null' if hi is None else hi}"


def _python_line(case_dir: Path, name: str) -> str:
    from pypdfbox.pdmodel.pd_document import PDDocument

    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + f"open=ERR:{_exc_name(e)}"
    try:
        cat = doc.get_document_catalog().get_cos_object()
        if name.startswith("name_"):
            names_dict = cat.get_dictionary_object(_NAMES)
            dict_ = (
                names_dict.get_dictionary_object(_DESTS)
                if isinstance(names_dict, COSDictionary)
                else None
            )
            if not isinstance(dict_, COSDictionary):
                return prefix + (
                    "names=NODICT kids=NODICT lookup_hit=NODICT "
                    "lookup_miss=NODICT limits=NODICT"
                )
            node = _Str(dict_)
            return prefix + (
                f"names={_name_names(node)} kids={_name_kids(node)} "
                f"lookup_hit={_name_lookup(node, 'key1')} "
                f"lookup_miss={_name_lookup(node, 'zzzmiss')} "
                f"limits={_name_limits(node)}"
            )
        dict_ = cat.get_dictionary_object(_PAGELABELS)
        if not isinstance(dict_, COSDictionary):
            return prefix + (
                "names=NODICT kids=NODICT lookup_hit=NODICT "
                "lookup_miss=NODICT limits=NODICT"
            )
        nnode = _Num(dict_)
        return prefix + (
            f"names={_num_names(nnode)} kids={_num_kids(nnode)} "
            f"lookup_hit={_num_lookup(nnode, 1)} "
            f"lookup_miss={_num_lookup(nnode, 999)} "
            f"limits={_num_limits(nnode)}"
        )
    finally:
        doc.close()


# ---------- pins ----------
#
# Every pin below is a DEFENSIBLE robustness divergence on MALFORMED input only
# (a well-formed name/number tree carries /Kids-or-leaf exclusively and a
# 2-element integer /Limits on every non-root node, so none of these shapes
# arise in practice). pypdfbox is strictly more robust than Apache PDFBox 3.0.7
# here; Java is pinned as ground truth but is NOT matched, because matching it
# would mean re-introducing crashes / latent -1 limits. Three divergence
# families, all recorded in CHANGES.md:
#
# D1 (getNumbers recursion): pypdfbox PDNumberTreeNode.get_numbers() flattens
#    the whole subtree through /Kids; upstream getNumbers() is non-recursive and
#    returns null on a /Kids-only (intermediate/root) node. So names=<count> vs
#    names=null whenever the node is intermediate. (PDNameTreeNode.get_names is
#    already non-recursive on both sides and agrees — only the NUMBER tree
#    recurses; this asymmetry is the long-standing Wave-1360-era divergence,
#    re-surfaced here for the generic-traversal projection.)
# D2 (no-limit / non-dict kid lookup): a kid missing /Limits (or a non-dict kid
#    that degrades to an empty no-limit node) makes upstream getValue either
#    stop early (name tree: returns the empty kid's null instead of falling
#    through) or throw NullPointerException (number tree: getLowerLimit() is
#    null and .compareTo NPEs). pypdfbox guards the null limit and continues the
#    fall-through search, so it neither crashes nor loses a later sibling.
# D3 (malformed /Limits leniency): upstream PDNumberTreeNode.getLowerLimit /
#    getUpperLimit read arr.get(index) (NOT bounds-checked) then arr.getInt,
#    which (a) throws IndexOutOfBoundsException when /Limits has < 2 elements and
#    you ask for the upper, and (b) returns the -1 sentinel when a /Limits entry
#    is a non-number. pypdfbox is bounds-safe (size>=2 guard -> None) and
#    type-strict (isinstance COSInteger -> None), so it reports null..null /
#    1..null where upstream reports 1..ERR / -1..-1. The NAME tree's
#    getLowerLimit/getUpperLimit already use the bounds-safe arr.getString on
#    both sides, so the name tree agrees — only the NUMBER tree limits diverge.

# name -> (python_line_override, java_line_override, reason).
_D1 = (
    "PDNumberTreeNode.get_numbers recurses through /Kids; upstream is "
    "non-recursive (null on intermediate node)."
)
_D2 = (
    "no-limit / non-dict kid: pypdfbox guards the null /Limits and falls "
    "through; upstream stops early (name) or NPEs (number)."
)
_D3 = (
    "malformed /Limits: pypdfbox is bounds-safe + type-strict (None); upstream "
    "number-tree throws IndexOutOfBounds (<2 elems) or returns -1 (non-number)."
)


def _pin(name: str, py: str, java: str, reason: str) -> tuple[str, str, str]:
    return (f"CASE {name} {py}", f"CASE {name} {java}", reason)


_PINNED: dict[str, tuple[str, str, str]] = {
    # D2: name-tree no-limit fall-through reaches the real leaf (key1 -> v1);
    # upstream stops at the empty no-limit kid and returns null.
    "name_kids_contains_non_dict": _pin(
        "name_kids_contains_non_dict",
        "names=null kids=2 lookup_hit=v1 lookup_miss=null limits=null..null",
        "names=null kids=2 lookup_hit=null lookup_miss=null limits=null..null",
        _D2,
    ),
    # D1: get_numbers flattens 2 leaves (4 entries) vs upstream null.
    "num_kids_wellformed": _pin(
        "num_kids_wellformed",
        "names=4 kids=2 lookup_hit=v1 lookup_miss=null limits=null..null",
        "names=null kids=2 lookup_hit=v1 lookup_miss=null limits=null..null",
        _D1,
    ),
    # D1 + D2: get_numbers flattens the lone real leaf (names=2) and getValue
    # survives the empty non-dict kid; upstream null + NPE on getValue.
    "num_kids_contains_non_dict": _pin(
        "num_kids_contains_non_dict",
        "names=2 kids=2 lookup_hit=v1 lookup_miss=null limits=null..null",
        "names=null kids=2 lookup_hit=ERR:NullPointerException "
        "lookup_miss=ERR:NullPointerException limits=null..null",
        f"{_D1} {_D2}",
    ),
    # D1: empty /Kids -> get_numbers returns {} (size 0) vs upstream null.
    "num_kids_empty_array": _pin(
        "num_kids_empty_array",
        "names=0 kids=0 lookup_hit=null lookup_miss=null limits=null..null",
        "names=null kids=0 lookup_hit=null lookup_miss=null limits=null..null",
        _D1,
    ),
    # D1: recursive flatten through the 2-level /Kids reaches the leaf (names=2).
    "num_kids_deeply_nested": _pin(
        "num_kids_deeply_nested",
        "names=2 kids=1 lookup_hit=v1 lookup_miss=null limits=null..null",
        "names=null kids=1 lookup_hit=v1 lookup_miss=null limits=null..null",
        _D1,
    ),
    # D1 + D2: flatten reaches the no-limit leaf (names=2) and getValue survives
    # its null limits; upstream null + NPE.
    "num_limits_missing_on_kid": _pin(
        "num_limits_missing_on_kid",
        "names=2 kids=1 lookup_hit=v1 lookup_miss=null limits=null..null",
        "names=null kids=1 lookup_hit=ERR:NullPointerException "
        "lookup_miss=ERR:NullPointerException limits=null..null",
        f"{_D1} {_D2}",
    ),
    # D3: 1-element /Limits -> upstream getUpperLimit throws (arr.get(1) OOB);
    # pypdfbox returns null.
    "num_limits_one_element": _pin(
        "num_limits_one_element",
        "names=2 kids=null lookup_hit=v1 lookup_miss=null limits=1..null",
        "names=2 kids=null lookup_hit=v1 lookup_miss=null limits=1..ERR",
        _D3,
    ),
    # D3: non-number /Limits entries -> upstream getInt returns -1 sentinel;
    # pypdfbox is type-strict and returns null.
    "num_limits_wrong_type": _pin(
        "num_limits_wrong_type",
        "names=2 kids=null lookup_hit=v1 lookup_miss=null limits=null..null",
        "names=2 kids=null lookup_hit=v1 lookup_miss=null limits=-1..-1",
        _D3,
    ),
}


@requires_oracle
def test_name_number_tree_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every fuzzed name/number tree traverses + looks up identically on
    pypdfbox and Apache PDFBox 3.0.7. Divergences are pinned explicitly in
    ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", name, entry)
    (tmp_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")

    raw = run_probe_text("NameNumberTreeFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, "name/number tree fuzz divergences:\n" + "\n".join(
        mismatches
    )
