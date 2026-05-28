"""Live PDFBox differential parity for the tagged-PDF ``/ParentTree`` reverse
mapping (``pypdfbox.pdmodel.documentinterchange.logicalstructure``).

Distinct surface from ``test_struct_tree_oracle`` (structure-element tree
shape) and ``test_struct_element_oracle`` (per-element role/class/attr detail):
this drives the *reverse* mapping that resolves marked-content (MCID) back to
structure elements — ``PDStructureTreeRoot.getParentTreeNextKey()`` and
``PDStructureTreeRoot.getParentTree().getNumbers()`` — plus per-page
``/StructParents`` linkage.

The oracle probe ``StructParentTreeProbe`` emits::

    NEXTKEY\\t<getParentTreeNextKey()>
    PAGE\\t<pageIndex>\\tsp=<StructParents or -1>
    ENTRY\\t<key>\\t<value>

where each ``ENTRY`` value classifies the parent-tree leaf for that integer
key (PDF 32000-1 §14.7.4.4):

* ``arr[r0,r1,...]`` — a ``COSArray`` indexed by MCID; each slot is the
  resolved standard structure type of the element in that slot (or ``null`` /
  ``?``).
* ``elem:<resolvedType>`` — a single structure-element dictionary.

We assert pypdfbox's dump equals Java PDFBox's on:

1. The bundled tagged fixture (``PDFA3A.pdf``) — exercises the real on-disk
   ``/ParentTree`` of an MCID-array-per-page document.
2. A multi-page tagged document built once via pypdfbox, exercising two
   per-page MCID arrays, role-map resolution inside slot type resolution
   (``Para`` → ``P``), and a non-trivial ``/ParentTreeNextKey``. Both libraries
   read that same file, so the parity is genuinely differential.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"


def _resolved_type(dict_obj: COSDictionary) -> str:
    """Slot/element type resolution mirroring the Java probe's ``resolvedType``:
    standard structure type, falling back to the raw ``/S`` type, then ``?``."""
    elem = PDStructureElement(dict_obj)
    std = elem.get_standard_structure_type()
    if std is not None:
        return std
    raw = elem.get_structure_type()
    return raw if raw is not None else "?"


def _slot(base: object) -> str:
    if base is None:
        return "null"
    if isinstance(base, COSDictionary):
        return _resolved_type(base)
    return "?"


def _classify(value: object) -> str:
    """Mirror the Java probe's ``classify``: array-indexed-by-MCID vs single
    element vs other."""
    if value is None:
        return "?"
    base = value.get_cos_object() if hasattr(value, "get_cos_object") else value
    if isinstance(base, COSArray):
        slots = [_slot(base.get_object(i)) for i in range(base.size())]
        return "arr[" + ",".join(slots) + "]"
    if isinstance(base, COSDictionary):
        return "elem:" + _resolved_type(base)
    return "?"


def _dump_parent_tree(path: Path) -> str:
    """pypdfbox reproduction of ``StructParentTreeProbe``."""
    doc = PDDocument.load(path)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        if root is None:
            return ""
        out: list[str] = [f"NEXTKEY\t{root.get_parent_tree_next_key()}"]
        for page_index, page in enumerate(doc.get_pages()):
            out.append(f"PAGE\t{page_index}\tsp={page.get_struct_parents()}")
        parent_tree = root.get_parent_tree()
        if parent_tree is None:
            return "".join(line + "\n" for line in out)
        numbers = parent_tree.get_numbers()
        if numbers is None:
            return "".join(line + "\n" for line in out)
        for key in sorted(numbers):
            out.append(f"ENTRY\t{key}\t{_classify(numbers[key])}")
        return "".join(line + "\n" for line in out)
    finally:
        doc.close()


def _build_tagged_pdf(path: Path) -> None:
    """Build a 2-page tagged document with a populated ``/ParentTree``.

    Each page maps its ``/StructParents`` key to a per-page MCID array. Slot
    types exercise role-map resolution (``Para`` → ``P``). ``ParentTreeNextKey``
    is set past the last used key.

    parent tree::

        key 0 -> [P (Para), H1]      (page 0, MCID 0 and 1)
        key 1 -> [Figure]            (page 1, MCID 0)
        nextkey = 2
    """
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
        PDStructureElementNumberTreeNode,
    )

    doc = PDDocument()
    try:
        page0 = PDPage()
        page1 = PDPage()
        doc.add_page(page0)
        doc.add_page(page1)
        page0.set_struct_parents(0)
        page1.set_struct_parents(1)

        catalog = doc.get_document_catalog()
        root = PDStructureTreeRoot()
        root.set_role_map({"Para": "P"})

        document = PDStructureElement("Document")
        document.set_parent(root)

        para = PDStructureElement("Para")
        para.set_parent(document)
        heading = PDStructureElement("H1")
        heading.set_parent(document)
        figure = PDStructureElement("Figure")
        figure.set_parent(document)

        document.append_kid(para)
        document.append_kid(heading)
        document.append_kid(figure)
        root.append_kid(document)

        # Wire the parent tree: key 0 -> [para, heading]; key 1 -> [figure].
        arr0 = COSArray()
        arr0.add(para.get_cos_object())
        arr0.add(heading.get_cos_object())
        arr1 = COSArray()
        arr1.add(figure.get_cos_object())

        tree = PDStructureElementNumberTreeNode()
        tree.set_numbers({0: arr0, 1: arr1})
        root.set_parent_tree(tree)
        root.set_parent_tree_next_key(2)

        catalog.set_struct_tree_root(root)
        doc.save(str(path))
    finally:
        doc.close()


@requires_oracle
def test_parent_tree_matches_pdfbox_bundled_pdfa3a():
    """Bundled PDF/A-3a fixture: real on-disk ``/ParentTree`` (MCID array)."""
    fixture = _FIXTURES / "multipdf" / "PDFA3A.pdf"
    java = run_probe_text("StructParentTreeProbe", str(fixture))
    py = _dump_parent_tree(fixture)
    assert py == java


@requires_oracle
def test_parent_tree_matches_pdfbox_built_multipage(tmp_path):
    """Built 2-page doc: two MCID arrays, role-map slot resolution, nextkey.

    Both libraries read the *same* pypdfbox-written file, so this is a real
    differential check of the parent-tree reverse mapping, not a self-compare.
    """
    built = tmp_path / "parent_tree_built.pdf"
    _build_tagged_pdf(built)

    java = run_probe_text("StructParentTreeProbe", str(built))
    py = _dump_parent_tree(built)
    assert py == java

    expected = (
        "NEXTKEY\t2\n"
        "PAGE\t0\tsp=0\n"
        "PAGE\t1\tsp=1\n"
        "ENTRY\t0\tarr[P,H1]\n"
        "ENTRY\t1\tarr[Figure]\n"
    )
    assert java == expected
    assert py == expected


def test_pdfa3a_fixture_has_parent_tree():
    """Guard: the bundled fixture really carries a ``/ParentTree`` so the
    oracle tests above exercise a non-empty reverse mapping."""
    fixture = _FIXTURES / "multipdf" / "PDFA3A.pdf"
    doc = PDDocument.load(fixture)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        assert root is not None
        assert root.has_parent_tree()
        parent_tree = root.get_parent_tree()
        assert parent_tree is not None
        assert parent_tree.get_numbers()
    finally:
        doc.close()
