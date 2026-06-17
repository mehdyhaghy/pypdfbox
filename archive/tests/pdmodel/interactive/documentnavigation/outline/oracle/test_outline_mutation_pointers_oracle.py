"""Raw COS pointer-projection parity for outline-tree *mutation* — the
doubly-linked-list rewiring (``/First /Last /Next /Prev /Parent``) plus the
signed ``/Count`` after each mutation, captured directly off the in-memory
``COSDictionary`` with no PDF save/reload round-trip.

Where ``test_pd_outline_count_propagation_wave1483.py`` pins only the signed
``/Count`` and ``oracle/test_outline_traversal_oracle.py`` pins wrapper titles
after a save+reload, this file pins the *pointer rewiring itself* — which node
each of the five link keys points at after:

* ``insert_sibling_after`` / ``insert_sibling_before`` on the **first / middle /
  last** node of a chain (head / tail parent-pointer fixups, mid-chain splice);
* ``add_first`` / ``add_last`` interleaving on a fresh root;
* a **cross-parent re-add** (``addLast`` of an already-attached only-child into a
  second parent) — upstream's ``requireSingleNode`` passes for an only-child, so
  the node's ``/Parent`` is re-pointed and *both* parents land a child-count
  contribution while the **old parent's ``/First``/``/Last`` stay stale** (a
  documented PDFBox quirk, pinned here so a future refactor can't "fix" it into a
  divergence);
* ``insert_sibling_after`` on a **parent-less** node (no parent ``/Last`` fixup).

Every literal below was captured from Apache PDFBox 3.0.7 via
``oracle/probes/OutlineMutationPointersProbe.java`` (wave 1501). The plain tests
pin those exact pointer projections and pass without the oracle;
``test_matches_pdfbox_oracle`` re-runs the same probe and asserts byte-for-byte
equality of the whole multi-scenario dump when the live oracle is present.

Upstream surface confirmed via ``javap`` on the pinned jar: PDFBox 3.0.7's
``PDOutlineNode`` exposes only ``addLast`` / ``addFirst`` (+ the package-private
``append`` / ``prepend`` / ``setFirstChild`` / ``setLastChild`` helpers) and
``PDOutlineItem`` exposes ``insertSiblingAfter`` / ``insertSiblingBefore`` — there
is **no** ``removeFromTree`` / ``removeChild`` on the upstream mutation surface,
so pypdfbox's ``remove_child`` is a pypdfbox-only convenience (already documented
in its docstring) and is exercised by the hand-written tests, not the oracle.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_FIRST = COSName.get_pdf_name("First")
_LAST = COSName.get_pdf_name("Last")
_NEXT = COSName.get_pdf_name("Next")
_PREV = COSName.get_pdf_name("Prev")
_PARENT = COSName.get_pdf_name("Parent")
_COUNT = COSName.get_pdf_name("Count")
_TITLE = COSName.get_pdf_name("Title")
_TYPE = COSName.get_pdf_name("Type")


# ---------- pypdfbox-side dumper (mirrors OutlineMutationPointersProbe) ----------


def _title_of(d) -> str:
    title = d.get_string(_TITLE)
    if title is not None:
        return title
    type_name = d.get_dictionary_object(_TYPE)
    if type_name is not None and getattr(type_name, "get_name", lambda: None)() == "Outlines":
        return "ROOT"
    return "?"


def _ptr(d, key: COSName) -> str:
    target = d.get_dictionary_object(key)
    return "-" if target is None else _title_of(target)


def _count(d) -> str:
    return "-" if d.get_dictionary_object(_COUNT) is None else str(d.get_int(_COUNT))


def _dump_node(node, node_id: str, out: list[str]) -> None:
    d = node.get_cos_object()
    out.append(
        f"{node_id}:parent={_ptr(d, _PARENT)},first={_ptr(d, _FIRST)}"
        f",last={_ptr(d, _LAST)},next={_ptr(d, _NEXT)}"
        f",prev={_ptr(d, _PREV)},count={_count(d)}"
    )


def _dump_children(node, out: list[str]) -> None:
    for child in node.children():
        _dump_node(child, _title_of(child.get_cos_object()), out)
        _dump_children(child, out)


def _dump(root, out: list[str]) -> None:
    _dump_node(root, _title_of(root.get_cos_object()), out)
    _dump_children(root, out)


def _mk_root() -> PDDocumentOutline:
    root = PDDocumentOutline()
    root.get_cos_object().set_string(_TITLE, "ROOT")
    return root


def _mk(title: str) -> PDOutlineItem:
    item = PDOutlineItem()
    item.set_title(title)
    return item


def _build_all() -> str:
    out: list[str] = []

    out.append("== insert_after_middle ==")
    root = _mk_root()
    a, b, c = _mk("A"), _mk("B"), _mk("C")
    root.add_last(a)
    root.add_last(b)
    root.add_last(c)
    b.insert_sibling_after(_mk("X"))
    _dump(root, out)

    out.append("== insert_before_middle ==")
    root = _mk_root()
    a, b, c = _mk("A"), _mk("B"), _mk("C")
    root.add_last(a)
    root.add_last(b)
    root.add_last(c)
    b.insert_sibling_before(_mk("X"))
    _dump(root, out)

    out.append("== insert_after_last ==")
    root = _mk_root()
    a, b = _mk("A"), _mk("B")
    root.add_last(a)
    root.add_last(b)
    b.insert_sibling_after(_mk("X"))
    _dump(root, out)

    out.append("== insert_before_first ==")
    root = _mk_root()
    a, b = _mk("A"), _mk("B")
    root.add_last(a)
    root.add_last(b)
    a.insert_sibling_before(_mk("X"))
    _dump(root, out)

    out.append("== add_first_last_interleave ==")
    root = _mk_root()
    root.add_last(_mk("A"))
    root.add_first(_mk("B"))
    root.add_last(_mk("C"))
    root.add_first(_mk("D"))
    _dump(root, out)

    out.append("== cross_parent_readd ==")
    root = _mk_root()
    p1, p2 = _mk("P"), _mk("Q")
    root.add_last(p1)
    root.add_last(p2)
    a = _mk("A")
    p1.add_last(a)
    p2.add_last(a)
    _dump(root, out)

    out.append("== insert_after_no_parent ==")
    lone = _mk("L")
    x = _mk("X")
    lone.insert_sibling_after(x)
    _dump_node(lone, "L", out)
    _dump_node(x, "X", out)

    return "\n".join(out)


# Expected: the byte-for-byte dump captured from PDFBox 3.0.7 via
# OutlineMutationPointersProbe (the probe prints a trailing newline per line; the
# Python builder joins with "\n" so we compare against the rstripped probe text).
_EXPECTED = """\
== insert_after_middle ==
ROOT:parent=-,first=A,last=C,next=-,prev=-,count=4
A:parent=ROOT,first=-,last=-,next=B,prev=-,count=-
B:parent=ROOT,first=-,last=-,next=X,prev=A,count=-
X:parent=ROOT,first=-,last=-,next=C,prev=B,count=-
C:parent=ROOT,first=-,last=-,next=-,prev=X,count=-
== insert_before_middle ==
ROOT:parent=-,first=A,last=C,next=-,prev=-,count=4
A:parent=ROOT,first=-,last=-,next=X,prev=-,count=-
X:parent=ROOT,first=-,last=-,next=B,prev=A,count=-
B:parent=ROOT,first=-,last=-,next=C,prev=X,count=-
C:parent=ROOT,first=-,last=-,next=-,prev=B,count=-
== insert_after_last ==
ROOT:parent=-,first=A,last=X,next=-,prev=-,count=3
A:parent=ROOT,first=-,last=-,next=B,prev=-,count=-
B:parent=ROOT,first=-,last=-,next=X,prev=A,count=-
X:parent=ROOT,first=-,last=-,next=-,prev=B,count=-
== insert_before_first ==
ROOT:parent=-,first=X,last=B,next=-,prev=-,count=3
X:parent=ROOT,first=-,last=-,next=A,prev=-,count=-
A:parent=ROOT,first=-,last=-,next=B,prev=X,count=-
B:parent=ROOT,first=-,last=-,next=-,prev=A,count=-
== add_first_last_interleave ==
ROOT:parent=-,first=D,last=C,next=-,prev=-,count=4
D:parent=ROOT,first=-,last=-,next=B,prev=-,count=-
B:parent=ROOT,first=-,last=-,next=A,prev=D,count=-
A:parent=ROOT,first=-,last=-,next=C,prev=B,count=-
C:parent=ROOT,first=-,last=-,next=-,prev=A,count=-
== cross_parent_readd ==
ROOT:parent=-,first=P,last=Q,next=-,prev=-,count=2
P:parent=ROOT,first=A,last=A,next=Q,prev=-,count=-1
A:parent=Q,first=-,last=-,next=-,prev=-,count=-
Q:parent=ROOT,first=A,last=A,next=-,prev=P,count=-1
A:parent=Q,first=-,last=-,next=-,prev=-,count=-
== insert_after_no_parent ==
L:parent=-,first=-,last=-,next=X,prev=-,count=-
X:parent=-,first=-,last=-,next=-,prev=L,count=-"""


def test_pointer_projection_matches_captured_literals() -> None:
    """pypdfbox's raw COS pointer rewiring matches the values captured from
    Apache PDFBox 3.0.7. Passes without the live oracle."""
    assert _build_all() == _EXPECTED


@requires_oracle
def test_matches_pdfbox_oracle() -> None:
    """Differential: the same mutation sequence run through Apache PDFBox 3.0.7
    yields a byte-identical pointer dump."""
    expected = run_probe_text("OutlineMutationPointersProbe").rstrip("\n")
    assert _build_all() == expected
