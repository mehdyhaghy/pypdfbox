"""Live PDFBox differential parity for the SETTER side of the string-keyed
``PDNameTreeNode`` (``setNames`` / ``setKids``).

Companion to ``test_number_tree_setter_oracle`` (the integer-keyed
``PDNumberTreeNode``). This module drives PDFBox's own ``setNames`` / ``setKids``
*writers* and inspects the raw ``/Names`` / ``/Kids`` / ``/Limits`` they stamp
onto the node, then rebuilds the identical sequence of set-calls on the
pypdfbox side. The Java side is ``oracle/probes/NameTreeSetterProbe.java``.

The string tree behaves DIFFERENTLY from the integer tree on the root-``/Limits``
question. ``PDNumberTreeNode.setNumbers`` writes ``/Limits`` via private
``setLowerLimit`` / ``setUpperLimit`` *before* (it never recomputes them away),
so a number-tree root keeps ``/Limits``. ``PDNameTreeNode.setNames`` instead
calls ``calculateLimits()`` *after* building ``/Names``, and ``calculateLimits``
strips ``/Limits`` from a root node — so a NAME-tree root never carries
``/Limits``. pypdfbox agrees with upstream on every root-``/Limits`` line here
(there is no DIVERGENCE A / DIVERGENCE B on the name tree, unlike the number
tree). The only divergence is:

DIVERGENCE C (narrowed) — ``/Names`` survival under ``setKids`` on a NON-ROOT
node. Upstream ``setKids`` clears a pre-existing ``/Names`` array ONLY when the
node ``isRootNode()`` (see ``PDNameTreeNode.setKids`` line 156). So a *non-root*
node that had ``setNames`` and then ``setKids`` keeps BOTH ``/Names`` and
``/Kids`` (malformed per PDF Reference 1.7 §7.9.7). pypdfbox ``set_kids``
removes ``/Names`` unconditionally so the node always stays single-armed. On a
*root* node the two libraries agree (both drop ``/Names``). This is the same
intentional, more-§7.9.7-conformant design choice already pinned for the
integer tree (CHANGES.md note (A)).

Two further string-specific facts are pinned here:

* ``/Limits`` lower/upper are written as ``COSString`` in sorted order, and the
  sort PDFBox applies (``Collections.sort`` — Java natural ``String`` order) is
  byte-for-byte identical to Python's ``sorted`` on the same BMP keys (ASCII
  code-point order). The ``setNames sort order`` case below pins the exact
  written order across digits / uppercase / ``_`` / lowercase.
* ``setNames({})`` on a root writes ``/Names []`` and NO ``/Limits`` (the name
  tree has no empty-map ``[null null]`` quirk the integer tree shows).

The >64-name auto-split divergence is pinned at the embedded-files level in
``tests/pdmodel/oracle/test_embedded_files_multi_oracle.py`` (which exercises
the same generic ``PDNameTreeNode.set_names`` split path), so it is not
re-pinned here.

Every case's oracle output is recorded verbatim in the literal-value regression
below so the asymmetry stays auditable without a live JVM.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSName, COSString
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode
from tests.oracle.harness import requires_oracle, run_probe_text

_NAMES = COSName.get_pdf_name("Names")
_KIDS = COSName.KIDS
_LIMITS = COSName.get_pdf_name("Limits")


def _entry(base: COSBase | None) -> str:
    if base is None:
        return "null"
    if isinstance(base, COSString):
        return base.get_string()
    return type(base).__name__


def _dump(label: str, node: PDStringNameTreeNode) -> str:
    cos = node.get_cos_object()
    lines = [f"# {label}"]
    names = cos.get_dictionary_object(_NAMES)
    if not isinstance(names, COSArray):
        lines.append("  Names: absent")
    else:
        keys = " ".join(_entry(names.get_object(i)) for i in range(0, names.size(), 2))
        # The Java probe's StringBuilder starts at "  Names:" and appends
        # " <key>" per entry, so an empty array prints "  Names:" with NO
        # trailing space. Match that exactly.
        lines.append("  Names:" + (f" {keys}" if keys else ""))
    kids = cos.get_dictionary_object(_KIDS)
    if not isinstance(kids, COSArray):
        lines.append("  Kids: absent")
    else:
        lines.append(f"  Kids: count={kids.size()}")
    lim = cos.get_dictionary_object(_LIMITS)
    if not isinstance(lim, COSArray):
        lines.append("  Limits: absent")
    else:
        lines.append(f"  Limits: [{_entry(lim.get(0))} {_entry(lim.get(1))}]")
    return "\n".join(lines) + "\n"


def _m(*kv: str) -> dict[str, str]:
    return {kv[i]: kv[i + 1] for i in range(0, len(kv), 2)}


def _build_setter_report() -> str:
    """Rebuild the exact set-call sequence the Java probe performs."""
    out: list[str] = []

    root1 = PDStringNameTreeNode()
    root1.set_names(_m("gamma", "G", "alpha", "A", "beta", "B"))
    out.append(_dump("setNames root non-empty", root1))

    root2 = PDStringNameTreeNode()
    root2.set_names({})
    out.append(_dump("setNames root empty-map", root2))

    root3 = PDStringNameTreeNode()
    root3.set_names(_m("solo", "S"))
    root3.set_names(None)
    out.append(_dump("setNames root then null", root3))

    leaf_a = PDStringNameTreeNode()
    leaf_a.set_names(_m("apple", "1", "banana", "2"))
    leaf_b = PDStringNameTreeNode()
    leaf_b.set_names(_m("mango", "3", "pear", "4"))
    root4 = PDStringNameTreeNode()
    root4.set_kids([leaf_a, leaf_b])
    out.append(_dump("setKids root", root4))
    out.append(_dump("setKids leafA", leaf_a))

    root5 = PDStringNameTreeNode()
    root5.set_names(_m("keepme", "K"))
    kid5 = PDStringNameTreeNode()
    kid5.set_names(_m("kidname", "K2"))
    root5.set_kids([kid5])
    out.append(_dump("setNames then setKids same node", root5))

    root6 = PDStringNameTreeNode()
    root6.set_names(_m("survive", "S"))
    root6.set_kids([])
    out.append(_dump("setNames then setKids empty-list", root6))

    parent7 = PDStringNameTreeNode()
    child7 = PDStringNameTreeNode()
    child7.set_names(_m("ph", "PH"))
    parent7.set_kids([child7])
    child7.set_names(_m("nrkeep", "NK"))
    gk7 = PDStringNameTreeNode()
    gk7.set_names(_m("gk", "GK"))
    child7.set_kids([gk7])
    out.append(_dump("non-root setNames then setKids", child7))

    root8 = PDStringNameTreeNode()
    root8.set_names(
        _m("Zebra", "1", "apple", "2", "Apple", "3", "10", "4", "2", "5", "_under", "6")
    )
    out.append(_dump("setNames sort order", root8))

    return "".join(out)


# PDFBox 3.0.7's verbatim NameTreeSetterProbe output. The "(root=...)" tag the
# Java probe prints is dropped here so the pypdfbox-built report (which has no
# is-root annotation in the dump) lines up.
_PDFBOX_SETTER_REPORT = (
    "# setNames root non-empty\n"
    "  Names: alpha beta gamma\n"  # sorted; agree
    "  Kids: absent\n"
    "  Limits: absent\n"  # root drops /Limits (calculateLimits); agree
    "# setNames root empty-map\n"
    "  Names:\n"
    "  Kids: absent\n"
    "  Limits: absent\n"  # no [null null] quirk on name tree; agree
    "# setNames root then null\n"
    "  Names: absent\n"
    "  Kids: absent\n"
    "  Limits: absent\n"  # agree
    "# setKids root\n"
    "  Names: absent\n"
    "  Kids: count=2\n"
    "  Limits: absent\n"  # root drops /Limits; agree
    "# setKids leafA\n"
    "  Names: apple banana\n"
    "  Kids: absent\n"
    "  Limits: [apple banana]\n"  # COSString sorted limits; agree
    "# setNames then setKids same node\n"
    "  Names: absent\n"  # root setKids clears /Names; agree
    "  Kids: count=1\n"
    "  Limits: absent\n"
    "# setNames then setKids empty-list\n"
    "  Names: survive\n"  # empty-list setKids leaves /Names; agree
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# non-root setNames then setKids\n"
    "  Names: nrkeep\n"  # DIVERGENCE C: upstream keeps /Names on NON-root
    "  Kids: count=1\n"
    "  Limits: [gk gk]\n"  # non-root keeps computed /Limits; agree
    "# setNames sort order\n"
    "  Names: 10 2 Apple Zebra _under apple\n"  # Java natural String order; agree
    "  Kids: absent\n"
    "  Limits: absent\n"
)

# pypdfbox's verbatim report (the more spec-compliant side on case C).
_PYPDFBOX_SETTER_REPORT = (
    "# setNames root non-empty\n"
    "  Names: alpha beta gamma\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# setNames root empty-map\n"
    "  Names:\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# setNames root then null\n"
    "  Names: absent\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# setKids root\n"
    "  Names: absent\n"
    "  Kids: count=2\n"
    "  Limits: absent\n"
    "# setKids leafA\n"
    "  Names: apple banana\n"
    "  Kids: absent\n"
    "  Limits: [apple banana]\n"
    "# setNames then setKids same node\n"
    "  Names: absent\n"
    "  Kids: count=1\n"
    "  Limits: absent\n"
    "# setNames then setKids empty-list\n"
    "  Names: survive\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# non-root setNames then setKids\n"
    "  Names: absent\n"  # DIVERGENCE C: pypdfbox clears /Names unconditionally
    "  Kids: count=1\n"
    "  Limits: [gk gk]\n"
    "# setNames sort order\n"
    "  Names: 10 2 Apple Zebra _under apple\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
)


def test_pypdfbox_setter_literals() -> None:
    """Pin pypdfbox's raw /Names//Kids//Limits after each set-call (no oracle)."""
    assert _build_setter_report() == _PYPDFBOX_SETTER_REPORT


def test_pdfbox_setter_literals_are_recorded() -> None:
    """Guard the recorded PDFBox oracle baseline against accidental edits.

    The asymmetry between the two reports is the whole point of this module;
    this test fails loudly if either recorded baseline is mutated so the single
    documented divergence can never silently disappear, and it asserts that the
    ONLY line that differs is case C's ``/Names`` line.
    """
    py = _PYPDFBOX_SETTER_REPORT.splitlines()
    java = _PDFBOX_SETTER_REPORT.splitlines()
    assert len(py) == len(java)
    diffs = [i for i in range(len(py)) if py[i] != java[i]]
    # Exactly one line differs: case C's /Names on the non-root node.
    case_c_nums = java.index("  Names: nrkeep")
    assert diffs == [case_c_nums], diffs
    assert py[case_c_nums] == "  Names: absent"


def test_name_tree_sort_order_matches_java_natural_order() -> None:
    """Pin that pypdfbox's ``sorted`` over the name-tree keys equals Java's
    ``Collections.sort`` (natural String / UTF-16 order) for the mixed
    digit/uppercase/underscore/lowercase key set, so a future Python-vs-Java
    sort regression on the written ``/Names`` order is caught without a JVM."""
    keys = ["Zebra", "apple", "Apple", "10", "2", "_under"]
    assert sorted(keys) == ["10", "2", "Apple", "Zebra", "_under", "apple"]


@requires_oracle
def test_name_tree_setter_matches_pdfbox() -> None:
    """The pypdfbox report equals the recorded PDFBox report on every agreement
    line and differs exactly on the one documented divergence-C line.

    Asserts the live probe still emits the recorded baseline (so the recorded
    constant cannot drift from PDFBox's real behaviour) and that pypdfbox still
    produces the recorded pypdfbox baseline.
    """
    java_raw = run_probe_text("NameTreeSetterProbe")
    # Strip the " (root=true|false)" annotation the probe appends to each header.
    java = "\n".join(
        line.split(" (root=")[0] if line.startswith("#") else line
        for line in java_raw.splitlines()
    )
    java = java + "\n" if not java.endswith("\n") else java
    assert java == _PDFBOX_SETTER_REPORT
    assert _build_setter_report() == _PYPDFBOX_SETTER_REPORT
