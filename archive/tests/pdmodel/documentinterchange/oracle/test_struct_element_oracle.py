"""Live PDFBox differential parity for tagged-PDF structure-element *detail*
(``pypdfbox.pdmodel.documentinterchange`` logical-structure + tagged-pdf
classes).

Where ``test_struct_tree_oracle`` checks the coarse tree shape (depth, resolved
role, ``/Alt`` / ``/ActualText`` presence flags), this module drives the deeper
per-element surface that PDFBox developers actually read off a
``PDStructureElement``:

* ``/S`` raw structure type and the ``/RoleMap``-resolved standard type
  (custom ``Chapter`` → ``Sect``),
* ``/T`` title, ``/Lang`` language, ``/Alt`` alternate description,
  ``/ActualText``,
* ``/C`` class names (``getClassNames`` → :meth:`get_class_names_as_strings`),
* the first ``/A`` attribute object's ``/O`` owner plus a sample typed
  attribute (a ``/O /Layout`` object's ``SpaceBefore``),
* the ``/K`` kid *kinds* in order — an MCID integer vs a nested
  ``PDStructureElement`` vs a ``PDMarkedContentReference`` vs a
  ``PDObjectReference``,
* and the structure-tree-root ``/RoleMap`` + ``/ClassMap`` key sets.

The oracle probe ``StructElemDetailProbe`` emits one ``ROOT`` record (sorted
role-map / class-map key sets) followed by one ``E`` record per structure
element (pre-order DFS). We build the tagged PDF *once* with pypdfbox, then both
Java PDFBox and pypdfbox read that same file — a genuine differential check of
role-map resolution, attribute-object reading, class-name decoding, and mixed
``/K`` kid dispatch, not a self-comparison.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_class_map import (
    PDStructureClassMap,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_layout_attribute_object import (
    PDLayoutAttributeObject,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _java_float(value: float) -> str:
    """Render ``value`` the way Java's ``StringBuilder.append(float)`` does.

    The probe appends a primitive ``float`` (from ``getSpaceBefore()``) to a
    ``StringBuilder``, which routes through ``Float.toString``. For the finite
    decimal we store (``12.5``) Java prints ``"12.5"``; Python's ``str(12.5)``
    matches. We keep the helper explicit so the expected-shape pin documents
    the contract rather than hard-coding the literal."""
    text = repr(float(value))
    return text


def _sorted_keys(keys: list[str]) -> str:
    """Mirror the probe's ``sortedKeys``: sorted, comma-joined, ``-`` if empty."""
    if not keys:
        return "-"
    return ",".join(sorted(keys))


def _nv(value: str | None) -> str:
    return "-" if value is None else value


def _classes(elem: PDStructureElement) -> str:
    names = elem.get_class_names_as_strings()
    if not names:
        return "-"
    return ",".join(names)


def _attr(elem: PDStructureElement) -> str:
    attrs = elem.get_attribute_objects()
    if not attrs:
        return "-"
    ao = attrs[0]
    owner = ao.get_owner()
    out = _nv(owner)
    if isinstance(ao, PDLayoutAttributeObject):
        out += f":SpaceBefore={_java_float(ao.get_space_before())}"
    return out


def _kid_kind(kid: object) -> str:
    # bool is an int subclass — guard it out (no bool kids here, but mirror Java's
    # Integer-only branch precisely).
    if isinstance(kid, int) and not isinstance(kid, bool):
        return f"mcid{kid}"
    if isinstance(kid, PDStructureElement):
        return "elem"
    if isinstance(kid, PDMarkedContentReference):
        return f"mcr{kid.get_mcid()}"
    if isinstance(kid, PDObjectReference):
        return "objr"
    return "other"


def _kids(elem: PDStructureElement) -> str:
    kid_list = elem.get_kids()
    if not kid_list:
        return "-"
    return ",".join(_kid_kind(k) for k in kid_list)


def _walk(elem: PDStructureElement, depth: int, out: list[str]) -> None:
    """Pre-order DFS mirroring ``StructElemDetailProbe.walk`` field-for-field."""
    s = elem.get_structure_type()
    std = elem.get_standard_structure_type() or s
    fields = [
        f"E\t{depth}",
        f"s={_nv(s)}",
        f"std={_nv(std)}",
        f"t={_nv(elem.get_title())}",
        f"lang={_nv(elem.get_language())}",
        f"alt={_nv(elem.get_alternate_description())}",
        f"actual={_nv(elem.get_actual_text())}",
        f"classes={_classes(elem)}",
        f"attr={_attr(elem)}",
        f"kids={_kids(elem)}",
    ]
    out.append("\t".join(fields))
    for kid in elem.get_kids():
        if isinstance(kid, PDStructureElement):
            _walk(kid, depth + 1, out)


def _dump(path: Path) -> str:
    """pypdfbox reproduction of ``StructElemDetailProbe``."""
    doc = PDDocument.load(path)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        if root is None:
            return ""
        out: list[str] = []
        role_keys = list(root.get_role_map().keys())
        class_map = root.get_class_map()
        class_keys = class_map.get_keys() if class_map is not None else []
        out.append(
            f"ROOT\trolemap={_sorted_keys(role_keys)}"
            f"\tclassmap={_sorted_keys(class_keys)}"
        )
        for kid in root.get_kids():
            if isinstance(kid, PDStructureElement):
                _walk(kid, 0, out)
        return "".join(line + "\n" for line in out)
    finally:
        doc.close()


def _build_tagged_pdf(path: Path) -> None:
    """Build a tagged PDF exercising the full element-detail surface.

    Tree (resolved standard types in parens)::

        Document
          Chapter (Sect)              /T /Lang /Alt + Layout attr + /C "warm"
          P (P)                       /ActualText
            kids: MCID 3, nested Figure, OBJR

    The root carries a ``/RoleMap`` (``Chapter`` → ``Sect``) and a
    ``/ClassMap`` (one class ``warm`` → a Layout attribute object).
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        catalog = doc.get_document_catalog()

        root = PDStructureTreeRoot()
        root.set_role_map({"Chapter": "Sect"})

        # /ClassMap: one class "warm" mapping to a Layout attribute object.
        class_attr = PDLayoutAttributeObject()
        class_attr.set_space_after(4.0)
        class_map = root.get_class_map()
        if class_map is None:
            class_map = PDStructureClassMap()
        class_map.add_class("warm", class_attr)
        root.set_class_map(class_map)

        document = PDStructureElement("Document")
        document.set_parent(root)

        # Chapter -> Sect (via role map). Carries title/lang/alt + Layout
        # attribute object (SpaceBefore) + class name "warm".
        chapter = PDStructureElement("Chapter")
        chapter.set_parent(document)
        chapter.set_title("Chapter One")
        chapter.set_language("en-US")
        chapter.set_alternate_description("first chapter")
        layout = PDLayoutAttributeObject()
        layout.set_space_before(12.5)
        chapter.add_attribute(layout)
        chapter.add_class_name("warm")

        # P element with /ActualText and mixed /K kids: MCID int, nested
        # Figure element, and an object reference (OBJR).
        para = PDStructureElement("P")
        para.set_parent(document)
        para.set_actual_text("actual para text")
        para.append_kid_mcid(3)
        figure = PDStructureElement("Figure")
        figure.set_parent(para)
        para.append_kid_element(figure)
        objref = PDObjectReference()
        para.append_kid_object_reference(objref)

        document.append_kid(chapter)
        document.append_kid(para)
        root.append_kid(document)

        catalog.set_struct_tree_root(root)
        doc.save(str(path))
    finally:
        doc.close()


@requires_oracle
def test_struct_element_detail_matches_pdfbox(tmp_path):
    """Differential: per-element /S+std/T/Lang/Alt/ActualText/classes/attr/kids
    and the root role-map + class-map key sets equal Java PDFBox's."""
    built = tmp_path / "struct_elem_detail.pdf"
    _build_tagged_pdf(built)

    java = run_probe_text("StructElemDetailProbe", str(built))
    py = _dump(built)
    assert py == java

    # Pin the expected shape so a regression that happens to agree on both
    # sides (e.g. both stop resolving the role map, or both drop /A) still
    # fails. SpaceBefore = 12.5 -> Java "12.5".
    expected = (
        "ROOT\trolemap=Chapter\tclassmap=warm\n"
        "E\t0\ts=Document\tstd=Document\tt=-\tlang=-\talt=-\tactual=-"
        "\tclasses=-\tattr=-\tkids=elem,elem\n"
        "E\t1\ts=Chapter\tstd=Sect\tt=Chapter One\tlang=en-US"
        "\talt=first chapter\tactual=-\tclasses=warm"
        "\tattr=Layout:SpaceBefore=12.5\tkids=-\n"
        "E\t1\ts=P\tstd=P\tt=-\tlang=-\talt=-\tactual=actual para text"
        "\tclasses=-\tattr=-\tkids=mcid3,elem,objr\n"
        "E\t2\ts=Figure\tstd=Figure\tt=-\tlang=-\talt=-\tactual=-"
        "\tclasses=-\tattr=-\tkids=-\n"
    )
    assert java == expected
    assert py == expected


@requires_oracle
def test_struct_element_role_map_resolution_matches_pdfbox(tmp_path):
    """Focused: the custom ``Chapter`` element resolves through ``/RoleMap`` to
    the standard ``Sect`` type identically in both libraries."""
    built = tmp_path / "struct_elem_rolemap.pdf"
    _build_tagged_pdf(built)
    java = run_probe_text("StructElemDetailProbe", str(built))

    # Extract Java's std= for the Chapter element line.
    chapter_line = next(
        line for line in java.splitlines() if "\ts=Chapter\t" in line
    )
    assert "\tstd=Sect\t" in chapter_line

    # pypdfbox resolves the same way.
    doc = PDDocument.load(built)
    try:
        root = doc.get_document_catalog().get_structure_tree_root()
        chapter = next(
            e for e in root.iter_descendants() if e.get_structure_type() == "Chapter"
        )
        assert chapter.get_standard_structure_type() == "Sect"
    finally:
        doc.close()


def test_built_pdf_has_expected_structure():
    """Guard (no oracle): the pypdfbox-built file genuinely carries the
    role map, class map, attribute object, and mixed kids — so the oracle
    tests above are non-vacuous."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        built = Path(td) / "guard.pdf"
        _build_tagged_pdf(built)
        doc = PDDocument.load(built)
        try:
            root = doc.get_document_catalog().get_structure_tree_root()
            assert root is not None
            assert root.get_role_map() == {"Chapter": "Sect"}
            cm = root.get_class_map()
            assert cm is not None
            assert "warm" in cm.get_keys()

            chapter = next(
                e
                for e in root.iter_descendants()
                if e.get_structure_type() == "Chapter"
            )
            attrs = chapter.get_attribute_objects()
            assert len(attrs) == 1
            assert isinstance(attrs[0], PDLayoutAttributeObject)
            assert attrs[0].get_owner() == "Layout"
            assert attrs[0].get_space_before() == 12.5
            assert chapter.get_class_names_as_strings() == ["warm"]

            para = next(
                e for e in root.iter_descendants() if e.get_structure_type() == "P"
            )
            kinds = [_kid_kind(k) for k in para.get_kids()]
            assert kinds == ["mcid3", "elem", "objr"]
        finally:
            doc.close()
