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
from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDStructureClassMap,
    PDStructureElement,
    PDStructureTreeRoot,
    Revisions,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import PDTableAttributeObject
from pypdfbox.pdmodel.pd_page import PDPage


def _typed_attribute(
    attributes: Revisions[PDAttributeObject], index: int
) -> PDAttributeObject | None:
    """Return revision ``index`` as a typed :class:`PDAttributeObject`.

    Upstream's ``Revisions<PDAttributeObject>`` stores the wrappers; the
    pypdfbox port stores the underlying ``COSArray`` entries, so the typed
    view has to be rebuilt via ``PDAttributeObject.create``.
    """
    raw = attributes.get_object(index)
    if isinstance(raw, PDAttributeObject):
        return raw
    if isinstance(raw, COSDictionary):
        return PDAttributeObject.create(raw)
    return None


def _check_element(
    base: COSBase | None,
    attribute_set: list[Revisions[PDAttributeObject]],
    class_map: PDStructureClassMap | None,
    class_set: set[str],
) -> None:
    """Port of upstream ``PDStructureElementTest.checkElement(...)``.

    Walks ``base`` and collects every structure element that carries at
    least one attribute object, plus the class-name references of elements
    whose ``/C`` is not shadowed by ``/A`` (PDF 32000-1 §14.7.3).

    Commits ``def6da8f`` / ``54427197`` (PDFBOX-6261) reshaped this walk:
    the ``/Pg`` gate was dropped in favour of "has attributes", the
    class-name check moved out of that branch, and a ``PDTableAttributeObject``
    first revision now has its ``/Headers`` inspected — which is what made
    the ``getHeaders`` ClassCastException observable in the first place."""
    if isinstance(base, COSArray):
        for i in range(base.size()):
            child = base.get_object(i)
            _check_element(child, attribute_set, class_map, class_set)
        return
    if not isinstance(base, COSDictionary):
        return

    elem = PDStructureElement(base)
    attributes = elem.get_attributes()
    if attributes.size() > 0:
        attribute_set.append(attributes)
        # pypdfbox's Revisions is backed by a live COSArray, so get_object
        # hands back the raw COSDictionary rather than the typed wrapper
        # upstream's Revisions<PDAttributeObject> holds; re-type it here.
        obj0 = _typed_attribute(attributes, 0)
        if isinstance(obj0, PDTableAttributeObject):  # Table 349
            headers = obj0.get_headers()
            if headers is not None:
                for header in headers:
                    # not a real test, just so that we have something with
                    # table headers after doing TIKA-4891 / PDFBOX-6261
                    assert header.startswith("node0")

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
    """Build a synthetic structure tree with three leaves:
    - leaf_a has /A (one Layout attribute) → takes precedence over /C.
    - leaf_b has /C ("Bold") → must be present in /ClassMap.
    - leaf_c has /A with a PDTableAttributeObject carrying /Headers
      (PDFBOX-6261 / def6da8f — the walk now reads them back).
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

    leaf_c = PDStructureElement(structure_type="TD")
    leaf_c.set_page(page)
    table_attr = PDTableAttributeObject()
    table_attr.set_headers(["node0a", "node0b"])
    leaf_c.add_attribute(table_attr)

    doc = PDStructureElement(structure_type="Document")
    doc.append_kid(leaf_a)
    doc.append_kid(leaf_b)
    doc.append_kid(leaf_c)
    root.append_kid(doc)

    return root


def test_check_element_collects_attributes_for_pg_leaves() -> None:
    """Port of ``testPDFBox4197`` (lite): every structure element that
    carries at least one attribute object contributes a
    ``Revisions<PDAttributeObject>`` to the accumulator. The upstream test
    asserts a 108-element set against a real fixture (117 before
    ``def6da8f`` swapped the ``/Pg`` gate for an "has attributes" gate); we
    assert the count for our synthetic tree."""
    root = _build_synthetic_tagged_tree()
    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()
    class_map = root.get_class_map()
    k = root.get_cos_object().get_dictionary_object(COSName.get_pdf_name("K"))
    _check_element(k, attribute_set, class_map, class_set)

    # leaf_a and leaf_c carry /A; leaf_b has only /C, so it is not counted.
    assert len(attribute_set) == 2
    total_attrs = sum(r.size() for r in attribute_set)
    assert total_attrs == 2


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


def test_check_element_reads_table_attribute_headers() -> None:
    """Port of ``def6da8f`` (PDFBOX-6261): the walk reaches a
    ``PDTableAttributeObject`` first revision and reads its ``/Headers``.

    Upstream only asserts the ``node0`` prefix inside ``checkElement``; this
    pins that the headers are actually non-empty, so the arm cannot pass
    vacuously if ``getHeaders`` regressed to ``null``.
    """
    root = _build_synthetic_tagged_tree()
    k = root.get_cos_object().get_dictionary_object(COSName.get_pdf_name("K"))
    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()
    _check_element(k, attribute_set, root.get_class_map(), class_set)

    tables = [
        typed
        for revisions in attribute_set
        if isinstance((typed := _typed_attribute(revisions, 0)), PDTableAttributeObject)
    ]
    assert len(tables) == 1
    assert tables[0].get_headers() == ["node0a", "node0b"]
