"""Live PDFBox differential parity for the tagged-PDF logical-structure tree
(``pypdfbox.pdmodel.documentinterchange.logicalstructure``).

The oracle probe ``StructTreeProbe`` loads a PDF, fetches
``PDStructureTreeRoot`` from the catalog, walks the structure-element tree
depth-first (pre-order), and emits one canonical line per structure element::

    <depth>\\t<role>\\talt=<0|1>\\tactual=<0|1>

* ``role`` is the element's structure type (``/S``) resolved through the
  ``/RoleMap`` to its standard structure type (upstream
  ``getStandardStructureType``), falling back to the raw ``/S`` when ``/S`` is
  absent from the role-map resolution.
* ``alt`` is ``/Alt`` presence; ``actual`` is ``/ActualText`` presence.

Non-structure-element kids (MCID ints, marked-content references, object
references) are skipped — only the structure-element tree shape is dumped.

We assert pypdfbox's dump equals Java PDFBox's on:

1. A bundled tagged fixture (``PDFA3A.pdf`` — PDF/A-3a, ``/Document`` → ``/P``).
2. A richer tagged document we build *once* via pypdfbox, exercising role-map
   resolution (``Heading`` → ``H1``, ``Para`` → ``P``), ``/Alt`` and
   ``/ActualText`` presence, and a deeper (3-level) tree. Both libraries read
   that same file so the parity is genuinely differential, not a self-check.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures"

_ALT = COSName.get_pdf_name("Alt")
_ACTUAL_TEXT = COSName.get_pdf_name("ActualText")


def _walk(elem: PDStructureElement, depth: int, out: list[str]) -> None:
    """Pre-order DFS emitting one canonical line per structure element.

    Mirrors the Java ``StructTreeProbe.walk`` exactly: resolved role (falling
    back to raw ``/S``), then ``/Alt`` / ``/ActualText`` presence flags."""
    role = elem.get_standard_structure_type() or elem.get_structure_type()
    cos = elem.get_cos_object()
    alt = 1 if cos.get_dictionary_object(_ALT) is not None else 0
    actual = 1 if cos.get_dictionary_object(_ACTUAL_TEXT) is not None else 0
    out.append(f"{depth}\t{role}\talt={alt}\tactual={actual}")
    for kid in elem.get_kids():
        if isinstance(kid, PDStructureElement):
            _walk(kid, depth + 1, out)


def _dump_struct_tree(path: Path) -> str:
    """pypdfbox reproduction of ``StructTreeProbe``: catalog →
    ``get_structure_tree_root`` → pre-order walk of structure elements."""
    doc = PDDocument.load(path)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        if root is None:
            return ""
        out: list[str] = []
        for kid in root.get_kids():
            if isinstance(kid, PDStructureElement):
                _walk(kid, 0, out)
        # Java prints a trailing newline after each line via out.print('\n');
        # join + trailing newline reproduces that framing.
        return "".join(line + "\n" for line in out)
    finally:
        doc.close()


def _build_tagged_pdf(path: Path) -> None:
    """Build a small tagged document exercising role-map resolution,
    ``/Alt`` / ``/ActualText`` presence, and a 3-level tree.

    Tree (resolved roles in parens)::

        Document
          Heading (H1)   /Alt
          Para (P)       /ActualText
            Figure       /Alt + /ActualText
    """
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()

        root = PDStructureTreeRoot()
        root.set_role_map({"Heading": "H1", "Para": "P"})

        document = PDStructureElement("Document")
        document.set_parent(root)

        heading = PDStructureElement("Heading")
        heading.set_parent(document)
        heading.set_alternate_description("alt heading")

        para = PDStructureElement("Para")
        para.set_parent(document)
        para.set_actual_text("actual para")

        figure = PDStructureElement("Figure")
        figure.set_parent(para)
        figure.set_alternate_description("a figure")
        figure.set_actual_text("fig actual")

        para.append_kid(figure)
        document.append_kid(heading)
        document.append_kid(para)
        root.append_kid(document)

        catalog.set_struct_tree_root(root)
        doc.save(str(path))
    finally:
        doc.close()


@requires_oracle
def test_struct_tree_matches_pdfbox_bundled_pdfa3a():
    """Bundled PDF/A-3a fixture: ``/Document`` → ``/P``, no Alt/ActualText."""
    fixture = _FIXTURES / "multipdf" / "PDFA3A.pdf"
    java = run_probe_text("StructTreeProbe", str(fixture))
    py = _dump_struct_tree(fixture)
    assert py == java


@requires_oracle
def test_struct_tree_matches_pdfbox_built_role_map(tmp_path):
    """Built tagged doc: role-map resolution + Alt/ActualText flags + nesting.

    Both libraries read the *same* pypdfbox-written file, so this is a real
    differential check of role-map resolution and tree shape, not a
    self-comparison.
    """
    built = tmp_path / "struct_tree_built.pdf"
    _build_tagged_pdf(built)

    java = run_probe_text("StructTreeProbe", str(built))
    py = _dump_struct_tree(built)
    assert py == java

    # Pin the expected shape so a regression in either side that happens to
    # agree (e.g. both stop resolving the role-map) still fails the test.
    expected = (
        "0\tDocument\talt=0\tactual=0\n"
        "1\tH1\talt=1\tactual=0\n"
        "1\tP\talt=0\tactual=1\n"
        "2\tFigure\talt=1\tactual=1\n"
    )
    assert java == expected
    assert py == expected


def test_pdfa3a_fixture_is_tagged():
    """Guard: the bundled fixture really carries a structure tree, so the
    oracle tests above are exercising a non-empty tree (not a vacuous
    empty-string == empty-string pass)."""
    fixture = _FIXTURES / "multipdf" / "PDFA3A.pdf"
    doc = PDDocument.load(fixture)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        assert root is not None
        assert root.has_kids()
    finally:
        doc.close()
