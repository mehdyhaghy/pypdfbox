"""Live PDFBox differential parity for ``/RoleMap`` resolution
(``PDStructureElement.get_standard_structure_type``).

The oracle probe ``RoleMapResolveProbe`` loads a PDF, fetches
``PDStructureTreeRoot`` from the catalog, walks the structure-element tree
pre-order (DFS), and emits one canonical line per structure element::

    <depth>\\ts=<getStructureType>\\tstd=<getStandardStructureType>

with ``-`` for a null value.

This isolates the role-map resolution contract that the broader
``StructTreeProbe`` test only exercises with single-hop, already-standard
mappings (``Heading``→``H1``, ``Para``→``P``). Upstream PDFBox 3.0.7's
``getStandardStructureType()`` performs exactly **one** role-map lookup: if
``/S`` maps to a name it returns that name, otherwise it returns ``/S``
unchanged. It does **not** recurse a multi-hop role-map chain and does **not**
short-circuit on standard structure types.

A previous pypdfbox implementation walked the chain recursively (capped at 16
hops) and so resolved a ``Foo→Bar→P`` chain all the way to ``P`` where upstream
stops at ``Bar``. This test pins the single-hop behaviour differentially.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _walk(elem: PDStructureElement, depth: int, out: list[str]) -> None:
    """Pre-order DFS emitting ``<depth>\\ts=<S>\\tstd=<resolved>`` per element.

    Mirrors the Java ``RoleMapResolveProbe.walk`` exactly: raw ``/S`` then the
    single-hop role-map-resolved standard type, ``-`` for null."""
    s = elem.get_structure_type()
    std = elem.get_standard_structure_type()
    out.append(f"{depth}\ts={_nv(s)}\tstd={_nv(std)}")
    for kid in elem.get_kids():
        if isinstance(kid, PDStructureElement):
            _walk(kid, depth + 1, out)


def _nv(value: str | None) -> str:
    return "-" if value is None else value


def _dump_resolution(path: Path) -> str:
    """pypdfbox reproduction of ``RoleMapResolveProbe``: catalog →
    ``get_structure_tree_root`` → pre-order walk emitting raw + resolved type."""
    doc = PDDocument.load(path)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        if root is None:
            return ""
        out: list[str] = []
        for kid in root.get_kids():
            if isinstance(kid, PDStructureElement):
                _walk(kid, 0, out)
        return "".join(line + "\n" for line in out)
    finally:
        doc.close()


def _build_role_map_pdf(path: Path) -> None:
    """Build a tagged document whose role-map exercises every resolution edge:

    Role map: ``{Foo: Bar, Bar: P, Std: Document}``::

        Document        /S=Document (standard, unmapped)   -> Document
          Foo           /S=Foo  (maps to Bar, NON-standard) -> Bar  (single hop)
          Std           /S=Std  (maps to a standard type)   -> Document
          P             /S=P    (standard, unmapped)        -> P

    ``Foo`` is the discriminating case: a recursive resolver would chase
    ``Foo→Bar→P`` and report ``P``; upstream stops after one hop at ``Bar``.
    """
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog()

        root = PDStructureTreeRoot()
        root.set_role_map({"Foo": "Bar", "Bar": "P", "Std": "Document"})

        document = PDStructureElement("Document")
        document.set_parent(root)

        foo = PDStructureElement("Foo")
        foo.set_parent(document)

        std = PDStructureElement("Std")
        std.set_parent(document)

        plain = PDStructureElement("P")
        plain.set_parent(document)

        document.append_kid(foo)
        document.append_kid(std)
        document.append_kid(plain)
        root.append_kid(document)

        catalog.set_struct_tree_root(root)
        doc.save(str(path))
    finally:
        doc.close()


@requires_oracle
def test_role_map_single_hop_matches_pdfbox(tmp_path):
    """Built tagged doc: role-map resolution is a single hop, matching upstream.

    Both libraries read the *same* pypdfbox-written file, so this is a real
    differential check of the role-map resolution contract, not a
    self-comparison.
    """
    built = tmp_path / "role_map_resolve.pdf"
    _build_role_map_pdf(built)

    java = run_probe_text("RoleMapResolveProbe", str(built))
    py = _dump_resolution(built)
    assert py == java

    # Pin the expected single-hop shape so a regression that re-introduces
    # recursive resolution (Foo -> P) fails even if both sides happened to
    # agree on the recursive answer.
    expected = (
        "0\ts=Document\tstd=Document\n"
        "1\ts=Foo\tstd=Bar\n"
        "1\ts=Std\tstd=Document\n"
        "1\ts=P\tstd=P\n"
    )
    assert java == expected
    assert py == expected


def test_role_map_resolution_is_single_hop_unit(tmp_path):
    """Non-oracle guard: ``Foo`` (mapped to non-standard ``Bar``) resolves to
    ``Bar``, *not* ``P``. Runs without the live oracle so the single-hop
    contract is pinned on every machine."""
    built = tmp_path / "role_map_resolve_unit.pdf"
    _build_role_map_pdf(built)

    doc = PDDocument.load(built)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        by_type: dict[str, PDStructureElement] = {}
        for kid in root.get_kids():
            if isinstance(kid, PDStructureElement):
                for grand in kid.get_kids():
                    if isinstance(grand, PDStructureElement):
                        by_type[grand.get_structure_type()] = grand
        # Foo -> Bar (single hop; Bar is non-standard but resolution stops).
        assert by_type["Foo"].get_standard_structure_type() == "Bar"
        # Std -> Document (single hop to a standard type).
        assert by_type["Std"].get_standard_structure_type() == "Document"
        # P -> P (no mapping; returned unchanged).
        assert by_type["P"].get_standard_structure_type() == "P"
    finally:
        doc.close()
