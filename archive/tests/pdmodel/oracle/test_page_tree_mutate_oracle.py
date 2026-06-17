"""Live PDFBox differential parity for structural page-tree mutation on an
UNBALANCED, multi-level ``/Kids`` tree.

``test_page_tree_oracle`` pins the *linear* page traversal (count + per-page
``indexOf`` + inherited geometry) after a remove/insert round-trip. This module
goes one level deeper: it pins the **internal tree shape** after a mutation —
every intermediate ``/Pages`` node's ``/Count`` (so ``/Count`` propagation up
*multiple* levels is checked, not just the root), the ``/Parent`` back-pointer
integrity at every node, and the leaf-page ordering (each page tagged with a
unique integer ``/MediaBox`` width so identity + position survive the
save/reload).

The tree is built from scratch identically on both sides (no fixture). Shape::

    root /Pages
      A /Pages
        p0 (width 100)
        p1 (101)
        B /Pages
          p2 (102)
          p3 (103)
          p4 (104)
      p5 (105)

Each parametrised case applies one mutation (``add`` / ``insert_after`` /
``insert_before`` / ``remove``), saves, reloads, and asserts pypdfbox's
canonical structure dump equals Apache PDFBox's (``PageTreeMutateProbe.java``).
The output is also fed to ``qpdf --check`` for structural soundness.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_PAGES = COSName.get_pdf_name("Pages")
_KIDS = COSName.get_pdf_name("Kids")
_COUNT = COSName.get_pdf_name("Count")
_PARENT = COSName.get_pdf_name("Parent")


def _rect(width: float) -> PDRectangle:
    # Java's ``new PDRectangle(width, height)`` is lower-left (0,0); pypdfbox's
    # 4-arg ctor takes the explicit corners.
    return PDRectangle(0, 0, width, 200)


def _page(width: float) -> COSDictionary:
    return PDPage(_rect(width)).get_cos_object()


def _pages_node(parent: COSDictionary) -> COSDictionary:
    node = COSDictionary()
    node.set_item(_TYPE, _PAGES)
    node.set_item(_KIDS, COSArray())
    node.set_item(_COUNT, COSInteger.get(0))
    node.set_item(_PARENT, parent)
    return node


def _add_kid(parent: COSDictionary, kid: COSDictionary) -> None:
    kids = parent.get_dictionary_object(_KIDS)
    kids.add(kid)
    kid.set_item(_PARENT, parent)


def _build(doc: PDDocument) -> None:
    """Build the fixed unbalanced multi-level tree (mirror of the probe)."""
    root = doc.get_pages().get_root()
    root.set_item(_KIDS, COSArray())
    root.set_item(_COUNT, COSInteger.get(0))

    a = _pages_node(root)
    b = _pages_node(a)

    _add_kid(a, _page(100))
    _add_kid(a, _page(101))
    _add_kid(b, _page(102))
    _add_kid(b, _page(103))
    _add_kid(b, _page(104))
    _add_kid(a, b)
    _add_kid(root, a)
    _add_kid(root, _page(105))

    b.set_item(_COUNT, COSInteger.get(3))
    a.set_item(_COUNT, COSInteger.get(5))
    root.set_item(_COUNT, COSInteger.get(6))


def _page_by_width(tree, width: float) -> PDPage:
    for page in tree:
        if abs(page.get_media_box().get_width() - width) < 0.001:
            return page
    raise AssertionError(f"no page of width {width}")


def _apply(doc: PDDocument, op: str, arg: float | None) -> None:
    tree = doc.get_pages()
    if op == "build":
        return
    if op == "add":
        doc.add_page(PDPage(_rect(200)))
        return
    assert arg is not None
    target = _page_by_width(tree, arg)
    if op == "remove":
        doc.remove_page(target)
    elif op == "insert_after":
        tree.insert_after(PDPage(_rect(200)), target)
    elif op == "insert_before":
        tree.insert_before(PDPage(_rect(200)), target)
    else:  # pragma: no cover - defensive
        raise AssertionError(f"unknown op: {op}")


def _fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)


def _dump(doc: PDDocument) -> str:
    lines: list[str] = []
    root = doc.get_pages().get_root()
    lines.append(f"pages {doc.get_number_of_pages()}")
    _walk(root, None, 0, lines)
    return "\n".join(lines) + "\n"


def _walk(
    node: COSDictionary,
    expected_parent: COSDictionary | None,
    depth: int,
    lines: list[str],
) -> None:
    type_name = node.get_cos_name(_TYPE)
    is_pages = type_name == _PAGES or node.contains_key(_KIDS)
    type_str = "Pages" if is_pages else "Page"

    count = str(node.get_int(_COUNT)) if node.contains_key(_COUNT) else "-"

    kids_arr = node.get_dictionary_object(_KIDS) if is_pages else None
    kids = "-" if kids_arr is None else str(kids_arr.size())

    if expected_parent is None:
        parent_ok = 1
    else:
        parent = node.get_dictionary_object(_PARENT)
        parent_ok = 1 if parent is expected_parent else 0

    width = "-" if is_pages else _fmt(PDPage(node).get_media_box().get_width())

    lines.append(
        f"node depth={depth} type={type_str} count={count} "
        f"kids={kids} parentok={parent_ok} w={width}"
    )

    if kids_arr is not None:
        for i in range(kids_arr.size()):
            kid = kids_arr.get_object(i)
            if isinstance(kid, COSDictionary):
                _walk(kid, node, depth + 1, lines)


# (op, arg, label) — arg is the tag-width of the target page (None for
# add/build which don't take a target).
_CASES = [
    ("build", None, "build"),
    ("add", None, "add"),
    ("insert_after", 102.0, "insert_after_mid"),
    ("insert_after", 104.0, "insert_after_last_of_node"),
    ("insert_before", 100.0, "insert_before_first"),
    ("insert_before", 105.0, "insert_before_root_leaf"),
    ("remove", 103.0, "remove_mid"),
    ("remove", 105.0, "remove_root_leaf"),
    ("remove", 102.0, "remove_first_of_node"),
]


@requires_oracle
@pytest.mark.parametrize(
    ("op", "arg", "label"), _CASES, ids=[c[2] for c in _CASES]
)
def test_page_tree_mutation_structure_matches_pdfbox(
    op: str, arg: float | None, label: str, tmp_path: Path
) -> None:
    java_out = tmp_path / "java.pdf"
    probe_args = [op]
    if arg is not None:
        probe_args.append(_fmt(arg))
    probe_args.append(str(java_out))
    java = run_probe_text("PageTreeMutateProbe", *probe_args)

    py_out = tmp_path / "py.pdf"
    doc = PDDocument()
    try:
        _build(doc)
        _apply(doc, op, arg)
        doc.save(py_out)
    finally:
        doc.close()
    reloaded = PDDocument.load(py_out)
    try:
        py = _dump(reloaded)
    finally:
        reloaded.close()

    assert py == java, (
        f"{label}: post-{op} tree structure diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )

    qpdf = shutil.which("qpdf")
    if qpdf is not None:
        result = subprocess.run(
            [qpdf, "--check", str(py_out)],
            capture_output=True,
            text=True,
            check=False,
        )
        # qpdf exit 0 = clean, 3 = warnings only; both acceptable.
        assert result.returncode in (0, 3), (
            f"{label}: qpdf --check failed on pypdfbox output:\n{result.stdout}\n{result.stderr}"
        )
