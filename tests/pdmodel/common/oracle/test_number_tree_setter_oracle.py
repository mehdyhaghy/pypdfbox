"""Live PDFBox differential parity for the SETTER side of PDNumberTreeNode.

The existing ``test_name_number_tree_oracle`` / ``test_name_number_tree_range_oracle``
probes build COS by hand and only exercise the *reader* path (``get_value`` /
``get_numbers`` / ``get_lower_limit`` ...). This module drives PDFBox's own
``setNumbers`` / ``setKids`` *writers* and inspects the raw ``/Nums`` / ``/Kids``
/ ``/Limits`` they stamp onto the node, then rebuilds the identical sequence of
set-calls on the pypdfbox side. The Java side is
``oracle/probes/NumberTreeSetterProbe.java``.

Three intentional, oracle-confirmed divergences are pinned here (pypdfbox is the
*more* spec-compliant side in each — PDF Reference 1.7 §7.9.7 forbids ``/Limits``
on a root node and forbids a node carrying both ``/Nums`` and ``/Kids``):

DIVERGENCE A — root ``/Limits`` (well-formed input). PDFBox ``setNumbers`` /
``setKids`` unconditionally write a ``/Limits [lo hi]`` array onto the node they
mutate, *even when that node is the tree root*. pypdfbox's ``_calculate_limits``
strips ``/Limits`` from any root node (the node has no parent), matching §7.9.7
which says only intermediate and leaf nodes carry ``/Limits``. So on a root,
PDFBox keeps ``/Limits`` and pypdfbox drops it. On a non-root node (e.g. a leaf
that has been attached under a ``/Kids`` parent) both agree — see the
``setKids leafA`` case below, which matches string-for-string.

DIVERGENCE B — empty-map ``/Limits``. ``setNumbers({})`` on PDFBox writes an
empty ``/Nums []`` plus ``/Limits [null null]`` (its private ``setLowerLimit`` /
``setUpperLimit`` create the two-slot array then store nulls). pypdfbox writes
``/Nums []`` but ``_calculate_limits`` drops ``/Limits`` entirely for an empty
leaf. This is a special case of DIVERGENCE A (a root with no keys).

DIVERGENCE C — ``/Nums`` survival under ``setKids``. PDFBox ``setKids`` does NOT
clear a pre-existing ``/Nums`` array, so a node that had ``setNumbers`` called
and then ``setKids`` ends up carrying BOTH arms (malformed per §7.9.7).
pypdfbox ``set_kids`` removes ``/Nums`` so the node stays single-armed.

All three are pre-existing, consistent design choices shared with
``PDNameTreeNode`` (whose ``calculate_limits`` root-drop is itself pinned in
``test_pd_name_tree_node_wave1275``). They are documented in CHANGES.md. The
oracle output for every case is recorded verbatim in the literal-value
regression test below (``test_pdfbox_setter_literals``) so the asymmetry stays
auditable without a live JVM.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
)
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode
from tests.oracle.harness import requires_oracle, run_probe_text

_NUMS = COSName.get_pdf_name("Nums")
_KIDS = COSName.KIDS
_LIMITS = COSName.get_pdf_name("Limits")


class _IntNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        assert isinstance(base, COSInteger)
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNode:
        return _IntNode(dic)


def _entry(base: COSBase | None) -> str:
    if base is None or isinstance(base, COSNull) or base is COSNull.NULL:
        return "null"
    if isinstance(base, COSInteger):
        return str(int(base.value))
    return type(base).__name__


def _dump(label: str, node: _IntNode) -> str:
    cos = node.get_cos_object()
    lines = [f"# {label}"]
    nums = cos.get_dictionary_object(_NUMS)
    if not isinstance(nums, COSArray):
        lines.append("  Nums: absent")
    else:
        keys = " ".join(_entry(nums.get_object(i)) for i in range(0, nums.size(), 2))
        # The Java probe's StringBuilder starts at "  Nums:" and appends
        # " <key>" per entry, so an empty array prints "  Nums:" with NO
        # trailing space. Match that exactly.
        lines.append("  Nums:" + (f" {keys}" if keys else ""))
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


def _build_setter_report() -> str:
    """Rebuild the exact set-call sequence the Java probe performs."""
    out: list[str] = []

    root1 = _IntNode()
    root1.set_numbers({30: 300, 10: 100, 20: 200})
    out.append(_dump("setNumbers root non-empty", root1))

    root2 = _IntNode()
    root2.set_numbers({})
    out.append(_dump("setNumbers root empty-map", root2))

    root3 = _IntNode()
    root3.set_numbers({5: 50})
    root3.set_numbers(None)
    out.append(_dump("setNumbers root then null", root3))

    leaf_a = _IntNode()
    leaf_a.set_numbers({1: 11, 2: 22})
    leaf_b = _IntNode()
    leaf_b.set_numbers({100: 1100, 200: 2200})
    root4 = _IntNode()
    root4.set_kids([leaf_a, leaf_b])
    out.append(_dump("setKids root", root4))
    out.append(_dump("setKids leafA", leaf_a))

    root5 = _IntNode()
    root5.set_numbers({7: 70})
    kid5 = _IntNode()
    kid5.set_numbers({9: 90})
    root5.set_kids([kid5])
    out.append(_dump("setNumbers then setKids same node", root5))

    root6 = _IntNode()
    root6.set_numbers({3: 30})
    root6.set_kids([])
    out.append(_dump("setNumbers then setKids empty-list", root6))

    return "".join(out)


# PDFBox 3.0.7's verbatim NumberTreeSetterProbe output. The "(root=...)" tag the
# Java probe prints is dropped here so the pypdfbox-built report (which has no
# is-root annotation in the dump) lines up; the agreement / divergence per line
# is documented in the module docstring.
_PDFBOX_SETTER_REPORT = (
    "# setNumbers root non-empty\n"
    "  Nums: 10 20 30\n"
    "  Kids: absent\n"
    "  Limits: [10 30]\n"  # DIVERGENCE A: pypdfbox drops root /Limits
    "# setNumbers root empty-map\n"
    "  Nums:\n"
    "  Kids: absent\n"
    "  Limits: [null null]\n"  # DIVERGENCE B
    "# setNumbers root then null\n"
    "  Nums: absent\n"
    "  Kids: absent\n"
    "  Limits: absent\n"  # agree
    "# setKids root\n"
    "  Nums: absent\n"
    "  Kids: count=2\n"
    "  Limits: [1 200]\n"  # DIVERGENCE A: pypdfbox drops root /Limits
    "# setKids leafA\n"
    "  Nums: 1 2\n"
    "  Kids: absent\n"
    "  Limits: [1 2]\n"  # agree (leafA is non-root once attached)
    "# setNumbers then setKids same node\n"
    "  Nums: 7\n"  # DIVERGENCE C: pypdfbox clears /Nums under setKids
    "  Kids: count=1\n"
    "  Limits: [9 9]\n"  # DIVERGENCE A
    "# setNumbers then setKids empty-list\n"
    "  Nums: 3\n"
    "  Kids: absent\n"
    "  Limits: [3 3]\n"  # DIVERGENCE A: pypdfbox drops root /Limits
)

# pypdfbox's verbatim report (the more spec-compliant side).
_PYPDFBOX_SETTER_REPORT = (
    "# setNumbers root non-empty\n"
    "  Nums: 10 20 30\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# setNumbers root empty-map\n"
    "  Nums:\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# setNumbers root then null\n"
    "  Nums: absent\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
    "# setKids root\n"
    "  Nums: absent\n"
    "  Kids: count=2\n"
    "  Limits: absent\n"
    "# setKids leafA\n"
    "  Nums: 1 2\n"
    "  Kids: absent\n"
    "  Limits: [1 2]\n"
    "# setNumbers then setKids same node\n"
    "  Nums: absent\n"
    "  Kids: count=1\n"
    "  Limits: absent\n"
    "# setNumbers then setKids empty-list\n"
    "  Nums: 3\n"
    "  Kids: absent\n"
    "  Limits: absent\n"
)


def test_pypdfbox_setter_literals() -> None:
    """Pin pypdfbox's raw /Nums//Kids//Limits after each set-call (no oracle)."""
    assert _build_setter_report() == _PYPDFBOX_SETTER_REPORT


def test_pdfbox_setter_literals_are_recorded() -> None:
    """Guard the recorded PDFBox oracle baseline against accidental edits.

    The asymmetry between the two reports is the whole point of this module;
    this test fails loudly if either recorded baseline is mutated so the
    divergence can never silently disappear.
    """
    py = _PYPDFBOX_SETTER_REPORT.splitlines()
    java = _PDFBOX_SETTER_REPORT.splitlines()
    assert len(py) == len(java)
    # Lines that must AGREE between the two libraries.
    agree_indices = {
        i
        for i, line in enumerate(java)
        if line.startswith("#") or line.startswith("  Nums:") or line.startswith("  Kids:")
    }
    # Exception: case C ("setNumbers then setKids same node") diverges on /Nums.
    case_c_nums = java.index("  Nums: 7")
    agree_indices.discard(case_c_nums)
    for i in sorted(agree_indices):
        assert py[i] == java[i], f"line {i} should agree: {py[i]!r} vs {java[i]!r}"
    # Case C: PDFBox keeps /Nums, pypdfbox clears it.
    assert java[case_c_nums] == "  Nums: 7"
    assert py[case_c_nums] == "  Nums: absent"


@requires_oracle
def test_number_tree_setter_matches_pdfbox() -> None:
    """The pypdfbox report equals the recorded PDFBox report on agreement lines
    and differs exactly on the three documented divergence lines.

    Asserts the live probe still emits the recorded baseline (so the recorded
    constant cannot drift from PDFBox's real behaviour) and that pypdfbox still
    produces the recorded pypdfbox baseline.
    """
    java_raw = run_probe_text("NumberTreeSetterProbe")
    # Strip the " (root=true|false)" annotation the probe appends to each header.
    java = "\n".join(
        line.split(" (root=")[0] if line.startswith("#") else line
        for line in java_raw.splitlines()
    )
    java = java + "\n" if not java.endswith("\n") else java
    assert java == _PDFBOX_SETTER_REPORT
    assert _build_setter_report() == _PYPDFBOX_SETTER_REPORT
