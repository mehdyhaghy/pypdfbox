"""Upstream-ported tests for PDStructureElement.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/
logicalstructure/PDStructureElementTest.java`` (PDFBox 3.0).

The upstream suite has two integration tests (``testPDFBox4197`` and
``testClassMap``) that load tagged-PDF fixtures and walk the structure tree
via a private ``checkElement`` recursion. The fixture-loading portion
requires the full PDF reader (deferred); we port the *recursion logic* into
a hand-driven walk over a synthetic structure tree. This exercises the same
``getAttributes`` + ``getClassNames`` + ``/ClassMap`` lookup paths that the
upstream test depends on.

The synthetic tree is small but covers every branch the upstream walk
visits: nested ``/K`` arrays, structure elements with ``/Pg``, the ``/A``-
takes-precedence-over-``/C`` rule (PDF 32000-1 §14.7.3), and attribute /
class-name revision read-back.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDStructureClassMap,
    PDStructureElement,
    PDStructureTreeRoot,
    Revisions,
)
from pypdfbox.pdmodel.pd_page import PDPage


def _check_element(
    base: COSBase | None,
    attribute_set: list[Revisions[PDAttributeObject]],
    class_map: PDStructureClassMap | None,
    class_set: set[str],
) -> None:
    """Port of upstream ``PDStructureElementTest.checkElement(...)``.

    Walks ``base`` and collects attribute objects + class-name references
    on every structure element that carries a ``/Pg`` entry. Mirrors the
    "A takes precedence over C" rule from PDF 32000-1 §14.7.3 (only
    inspect ``/C`` when ``/A`` is absent)."""
    if isinstance(base, COSArray):
        for i in range(base.size()):
            child = base.get_object(i)
            _check_element(child, attribute_set, class_map, class_set)
        return
    if not isinstance(base, COSDictionary):
        return
    if not base.contains_key(COSName.get_pdf_name("Pg")):
        # Recurse into /K even when this isn't a structure element with a
        # /Pg — the upstream walk does the same.
        kids = base.get_dictionary_object(COSName.get_pdf_name("K"))
        if kids is not None:
            _check_element(kids, attribute_set, class_map, class_set)
        return

    elem = PDStructureElement(base)
    attribute_set.append(elem.get_attributes())

    if base.contains_key(COSName.get_pdf_name("C")) and not base.contains_key(
        COSName.get_pdf_name("A")
    ):
        for class_name in elem.get_class_names_as_strings():
            class_set.add(class_name)
            if class_map is not None:
                assert class_name in class_map.get_class_definitions(), (
                    f"'{class_name}' not in ClassMap "
                    f"{class_map.get_class_definitions()}"
                )

    kids = base.get_dictionary_object(COSName.get_pdf_name("K"))
    if kids is not None:
        _check_element(kids, attribute_set, class_map, class_set)


def _build_synthetic_tagged_tree() -> PDStructureTreeRoot:
    """Build a synthetic structure tree with two leaves:
    - leaf_a has /A (one Layout attribute) → takes precedence over /C.
    - leaf_b has /C ("Bold") → must be present in /ClassMap.
    """
    root = PDStructureTreeRoot()
    class_map = PDStructureClassMap()
    bold_attr = PDAttributeObject()
    bold_attr.set_owner("Layout")
    class_map.add_class("Bold", bold_attr)
    root.set_class_map(class_map)

    page = PDPage()

    leaf_a = PDStructureElement(structure_type="P")
    leaf_a.set_page(page)
    leaf_a_attr = PDAttributeObject()
    leaf_a_attr.set_owner("Layout")
    leaf_a.add_attribute(leaf_a_attr)

    leaf_b = PDStructureElement(structure_type="Span")
    leaf_b.set_page(page)
    leaf_b.add_class_name("Bold")

    doc = PDStructureElement(structure_type="Document")
    doc.append_kid(leaf_a)
    doc.append_kid(leaf_b)
    root.append_kid(doc)

    return root


def test_check_element_collects_attributes_for_pg_leaves() -> None:
    """Port of ``testPDFBox4197`` (lite): every structure element with a
    ``/Pg`` contributes a ``Revisions<PDAttributeObject>`` to the
    accumulator. The upstream test asserts a 117-element set against a
    real fixture; we assert the count for our synthetic tree."""
    root = _build_synthetic_tagged_tree()
    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()
    class_map = root.get_class_map()
    k = root.get_cos_object().get_dictionary_object(COSName.get_pdf_name("K"))
    _check_element(k, attribute_set, class_map, class_set)

    assert len(attribute_set) == 2
    total_attrs = sum(r.size() for r in attribute_set)
    # leaf_a contributes one /A entry; leaf_b has no /A, only /C.
    assert total_attrs == 1


def test_check_element_classmap_contains_seen_class_names() -> None:
    """Port of ``testClassMap`` (lite): every ``/C`` class name on a
    structure element with ``/Pg`` must appear in the tree-root's
    ``/ClassMap``. The upstream version validates against 10 unique
    class-name strings on a real fixture; we exercise the lookup with one."""
    root = _build_synthetic_tagged_tree()
    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()
    class_map = root.get_class_map()
    k = root.get_cos_object().get_dictionary_object(COSName.get_pdf_name("K"))
    _check_element(k, attribute_set, class_map, class_set)

    assert class_set == {"Bold"}
    # Sanity check: assertion inside _check_element would have fired if
    # /Bold were missing from /ClassMap.
    assert class_map is not None
    assert "Bold" in class_map.get_class_definitions()


def test_check_element_a_takes_precedence_over_c() -> None:
    """Port of upstream ``checkElement``'s § 14.7.3 precedence guard: when
    both ``/A`` and ``/C`` are present, ``/C`` is *not* inspected."""
    root = PDStructureTreeRoot()
    class_map = PDStructureClassMap()
    foo_attr = PDAttributeObject()
    foo_attr.set_owner("Layout")
    class_map.add_class("Foo", foo_attr)
    root.set_class_map(class_map)

    page = PDPage()
    leaf = PDStructureElement(structure_type="P")
    leaf.set_page(page)
    a_attr = PDAttributeObject()
    a_attr.set_owner("Layout")
    leaf.add_attribute(a_attr)
    leaf.add_class_name("MissingFromClassMap")  # would fail the /C check
    root.append_kid(leaf)

    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()
    k = root.get_cos_object().get_dictionary_object(COSName.get_pdf_name("K"))
    # Should NOT raise — /A presence suppresses /C lookup.
    _check_element(k, attribute_set, class_map, class_set)

    # /C was skipped despite the dangling class name.
    assert class_set == set()
