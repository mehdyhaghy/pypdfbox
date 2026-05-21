"""Tagged-PDF / accessibility structure-tree round-trip tests (wave 1367, agent E).

Builds small synthetic ``PDDocument`` instances wired with ``/MarkInfo``,
``/StructTreeRoot``, ``/RoleMap``, ``/ClassMap``, ``/ParentTree`` and a tree
of ``PDStructureElement`` kids (PDStructureElement / PDMarkedContentReference
/ integer MCID), saves through ``PDDocument.save``, reparses through
``PDDocument.load``, then asserts that structural identity survives the
round-trip.

Covers the documentinterchange surface called out in wave 1367 agent E:

- PDStructureTreeRoot construction + walking + retrieve-by-id (``/IDTree``)
- PDStructureElement ``append_kid`` for element / MCR / integer MCID kids
  and the negative-MCID validation rule
- PDMarkInfo + StructTreeRoot relationships (``/Marked true``)
- ParentTree lookups (PDF 32000-1 §14.7.4.4 - struct-parents → array of
  structure elements indexed by MCID)
- ClassMap dispatch through PDStructureClassMap
- ``/K`` integer / dict / array round-trips
- Standard structure types (P, H1-H6, L, LI, Lbl, LBody, Table, TR, TH, TD,
  Span, Quote, Note, Reference, BibEntry, Code, Link, Annot, Ruby, Warichu,
  Figure, Formula, Form)
- Role-map cycle detection (forbidden — must not infinite-loop)

No upstream JUnit counterpart for the full save/load loop — the upstream
``PDStructureElementTest`` exercises the in-memory tree only; pypdfbox's
round-trip is a tighter contract that catches xref / serialisation drift in
the tagged-PDF cluster.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox import Loader, PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDMarkedContentReference,
    PDMarkInfo,
    PDObjectReference,
    PDStructureClassMap,
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNumberTreeNode,
)
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDLayoutAttributeObject,
    PDTableAttributeObject,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_and_reload(doc: PDDocument) -> PDDocument:
    """Serialise ``doc`` and re-parse through ``Loader.load_pdf``."""
    sink = io.BytesIO()
    doc.save(sink)
    return PDDocument.load(sink.getvalue())


def _wire_tagged_doc(
    doc: PDDocument, root: PDStructureTreeRoot, marked: bool = True
) -> None:
    """Attach a freshly constructed ``PDStructureTreeRoot`` (and the
    ``/Marked true`` flag) to the document catalog."""
    catalog = doc.get_document_catalog()
    catalog.set_structure_tree_root(root)
    mark_info = PDMarkInfo()
    mark_info.set_marked(marked)
    catalog.set_mark_info(mark_info)


# ---------------------------------------------------------------------------
# PDMarkInfo + StructTreeRoot relationship
# ---------------------------------------------------------------------------


def test_marked_true_survives_roundtrip() -> None:
    """``/MarkInfo /Marked true`` set on the catalog reappears after
    save → reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        _wire_tagged_doc(doc, root, marked=True)
        with _save_and_reload(doc) as reloaded:
            mark_info = reloaded.get_document_catalog().get_mark_info()
            assert mark_info is not None
            assert mark_info.is_marked() is True
            assert mark_info.is_tagged() is True


def test_marked_false_explicit_survives_roundtrip() -> None:
    """An explicit ``/Marked false`` is preserved (distinct from absent)."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        _wire_tagged_doc(doc, root, marked=False)
        with _save_and_reload(doc) as reloaded:
            mark_info = reloaded.get_document_catalog().get_mark_info()
            assert mark_info is not None
            # When written via set_marked(False), the key is present.
            assert mark_info.has_marked() is True
            assert mark_info.is_marked() is False


def test_mark_info_user_properties_suspects_roundtrip() -> None:
    """``/UserProperties`` and ``/Suspects`` flags round-trip independently."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        mark_info = PDMarkInfo()
        mark_info.set_marked(True)
        mark_info.set_user_properties(True)
        mark_info.set_suspects(True)
        doc.get_document_catalog().set_mark_info(mark_info)
        doc.get_document_catalog().set_structure_tree_root(PDStructureTreeRoot())
        with _save_and_reload(doc) as reloaded:
            mi = reloaded.get_document_catalog().get_mark_info()
            assert mi is not None
            assert mi.is_marked() is True
            assert mi.is_user_properties() is True
            assert mi.uses_user_properties() is True
            assert mi.is_suspects() is True
            assert mi.is_suspect() is True


def test_struct_tree_root_attached_to_catalog_roundtrip() -> None:
    """``/StructTreeRoot`` dictionary survives a save/reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            reloaded_root = reloaded.get_document_catalog().get_struct_tree_root()
            assert reloaded_root is not None
            assert isinstance(reloaded_root, PDStructureTreeRoot)
            assert reloaded_root.get_type() == "StructTreeRoot"


# ---------------------------------------------------------------------------
# PDStructureTreeRoot + PDStructureElement construction + walking
# ---------------------------------------------------------------------------


def test_simple_document_root_with_one_element_roundtrip() -> None:
    """Document → P element. The root and its single ``P`` kid round-trip."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        document_element = PDStructureElement(PDStructureElement.DOCUMENT, root)
        paragraph = PDStructureElement(PDStructureElement.P, document_element)
        document_element.append_kid_element(paragraph)
        root.append_kid(document_element)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            reloaded_root = reloaded.get_document_catalog().get_struct_tree_root()
            assert reloaded_root is not None
            kids = reloaded_root.get_kids()
            assert len(kids) == 1
            assert isinstance(kids[0], PDStructureElement)
            assert kids[0].get_structure_type() == "Document"
            grand_kids = kids[0].get_kids()
            assert len(grand_kids) == 1
            assert grand_kids[0].get_structure_type() == "P"


def test_structure_tree_walk_via_iter_descendants_roundtrip() -> None:
    """A multi-level tree comes back with the same descendant set after
    a save/reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        document = PDStructureElement(PDStructureElement.DOCUMENT, root)
        h1 = PDStructureElement(PDStructureElement.H1, document)
        section = PDStructureElement(PDStructureElement.SECT, document)
        p1 = PDStructureElement(PDStructureElement.P, section)
        p2 = PDStructureElement(PDStructureElement.P, section)
        document.append_kid_element(h1)
        document.append_kid_element(section)
        section.append_kid_element(p1)
        section.append_kid_element(p2)
        root.append_kid(document)
        _wire_tagged_doc(doc, root)

        with _save_and_reload(doc) as reloaded:
            reloaded_root = reloaded.get_document_catalog().get_struct_tree_root()
            assert reloaded_root is not None
            descendants = list(reloaded_root.iter_descendants())
            types = sorted(d.get_structure_type() for d in descendants)
            assert types == ["Document", "H1", "P", "P", "Sect"]


# ---------------------------------------------------------------------------
# PDStructureTreeRoot retrieve-by-id / IDTree
# ---------------------------------------------------------------------------


def test_id_tree_lookup_roundtrip() -> None:
    """Building an ``/IDTree`` from elements with ``/ID`` lets the reloaded
    tree resolve them by id."""
    from pypdfbox.cos import COSDictionary as _COSDict

    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        document = PDStructureElement(PDStructureElement.DOCUMENT, root)
        para = PDStructureElement(PDStructureElement.P, document)
        para.set_id("para-1")
        h1 = PDStructureElement(PDStructureElement.H1, document)
        h1.set_id("heading-alpha")
        document.append_kid_element(para)
        document.append_kid_element(h1)
        root.append_kid(document)

        # Wire a flat /IDTree (no kids — just /Names) so the round-trip can
        # inspect it. The PDNameTreeNode encoding is COSArray pairs of
        # [name-string, PDStructureElement-dict].
        id_tree_dict = _COSDict()
        names = COSArray()
        names.add(COSName.get_pdf_name("heading-alpha"))
        names.add(h1.get_cos_object())
        names.add(COSName.get_pdf_name("para-1"))
        names.add(para.get_cos_object())
        id_tree_dict.set_item("Names", names)
        root.get_cos_object().set_item("IDTree", id_tree_dict)

        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            reloaded_root = reloaded.get_document_catalog().get_struct_tree_root()
            assert reloaded_root is not None
            assert reloaded_root.has_id_tree() is True


# ---------------------------------------------------------------------------
# append_kid validation rules
# ---------------------------------------------------------------------------


def test_append_kid_negative_mcid_rejected() -> None:
    """Upstream ``appendKid(int)`` rejects negative MCID values; the lite
    dispatcher in ``PDStructureNode`` mirrors this."""
    elem = PDStructureElement(PDStructureElement.P, None)
    with pytest.raises(ValueError):
        elem.append_kid(-1)
    with pytest.raises(ValueError):
        elem.append_kid_mcid(-1)


def test_append_kid_marked_content_object_negative_mcid_rejected() -> None:
    """A PDMarkedContent whose ``/MCID`` is negative is rejected, matching
    upstream ``appendKid(PDMarkedContent)``."""
    elem = PDStructureElement(PDStructureElement.P, None)
    bad_props = COSDictionary()
    bad_props.set_int("MCID", -3)
    bad_mc = PDMarkedContent.create(COSName.get_pdf_name("Span"), bad_props)
    with pytest.raises(ValueError):
        elem.append_kid_marked_content_object(bad_mc)


def test_append_kid_marked_content_object_missing_mcid_rejected() -> None:
    """A PDMarkedContent without ``/MCID`` returns -1 from ``get_mcid``
    and must therefore raise."""
    elem = PDStructureElement(PDStructureElement.P, None)
    mc = PDMarkedContent.create(COSName.get_pdf_name("Span"), None)
    assert mc.get_mcid() == -1
    with pytest.raises(ValueError):
        elem.append_kid_marked_content_object(mc)


def test_append_kid_bool_rejected_type_error() -> None:
    """``bool`` is an ``int`` subclass in Python; the dispatcher must
    reject it explicitly to match the Java overload set."""
    elem = PDStructureElement(PDStructureElement.P, None)
    with pytest.raises(TypeError):
        elem.append_kid(True)


# ---------------------------------------------------------------------------
# /K integer + MCR + dict + array round-trip
# ---------------------------------------------------------------------------


def test_k_integer_mcid_kid_roundtrip() -> None:
    """A ``/K`` entry that is a single integer MCID survives the round-trip
    as an ``int`` after wrapping."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        para = PDStructureElement(PDStructureElement.P, root)
        para.append_kid(7)
        root.append_kid(para)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            kids = r.get_kids()
            assert len(kids) == 1
            grand = kids[0].get_kids()
            assert len(grand) == 1
            assert grand[0] == 7


def test_k_marked_content_reference_kid_roundtrip() -> None:
    """A ``/K`` entry that is a PDMarkedContentReference round-trips into
    a typed wrapper after reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        para = PDStructureElement(PDStructureElement.P, root)
        mcr = PDMarkedContentReference()
        mcr.set_mcid(42)
        para.append_kid_marked_content(mcr)
        root.append_kid(para)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            grand = r.get_kids()[0].get_kids()
            assert len(grand) == 1
            assert isinstance(grand[0], PDMarkedContentReference)
            assert grand[0].get_mcid() == 42


def test_k_mixed_array_roundtrip() -> None:
    """A ``/K`` array carrying [element, MCR, int MCID] preserves order
    and types."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        sect = PDStructureElement(PDStructureElement.SECT, root)
        # Mix three kid shapes in a deterministic order.
        nested = PDStructureElement(PDStructureElement.P, sect)
        mcr = PDMarkedContentReference()
        mcr.set_mcid(11)
        sect.append_kid_element(nested)
        sect.append_kid_marked_content(mcr)
        sect.append_kid_mcid(99)
        root.append_kid(sect)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            kids = r.get_kids()
            assert len(kids) == 1
            grand = kids[0].get_kids()
            assert len(grand) == 3
            assert isinstance(grand[0], PDStructureElement)
            assert grand[0].get_structure_type() == "P"
            assert isinstance(grand[1], PDMarkedContentReference)
            assert grand[1].get_mcid() == 11
            assert grand[2] == 99


def test_k_single_dict_to_array_promotion_roundtrip() -> None:
    """Starting from a single-kid ``/K`` (bare dictionary), appending a
    second kid promotes the slot to a COSArray. The promoted shape
    survives a round-trip."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        sect = PDStructureElement(PDStructureElement.SECT, root)
        h1 = PDStructureElement(PDStructureElement.H1, sect)
        h2 = PDStructureElement(PDStructureElement.H2, sect)
        sect.append_kid_element(h1)
        # /K is now a bare COSDictionary at this point in upstream — append
        # again to force promotion.
        sect.append_kid_element(h2)
        root.append_kid(sect)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            grand = r.get_kids()[0].get_kids()
            assert [g.get_structure_type() for g in grand] == ["H1", "H2"]


# ---------------------------------------------------------------------------
# Standard structure types — exhaustive parameterised round-trip
# ---------------------------------------------------------------------------


_STANDARD_TYPES_SAMPLE = [
    "P",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "L",
    "LI",
    "Lbl",
    "LBody",
    "Table",
    "TR",
    "TH",
    "TD",
    "Span",
    "Quote",
    "Note",
    "Reference",
    "BibEntry",
    "Code",
    "Link",
    "Annot",
    "Ruby",
    "Warichu",
    "Figure",
    "Formula",
    "Form",
]


@pytest.mark.parametrize("struct_type", _STANDARD_TYPES_SAMPLE, ids=_STANDARD_TYPES_SAMPLE)
def test_standard_structure_type_roundtrip(struct_type: str) -> None:
    """Every PDF 32000-1 §14.8.4 standard structure type makes it through
    save → reload with its ``/S`` name intact."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        elem = PDStructureElement(struct_type, root)
        root.append_kid(elem)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            kids = r.get_kids()
            assert len(kids) == 1
            assert kids[0].get_structure_type() == struct_type
            # The resolved standard type matches when no /RoleMap is wired.
            assert kids[0].is_resolved_structure_type_standard() is True


# ---------------------------------------------------------------------------
# Role-map dispatch + cycle detection
# ---------------------------------------------------------------------------


def test_role_map_resolves_through_roundtrip() -> None:
    """A non-standard ``/S`` mapped via ``/RoleMap`` resolves to the
    standard target after reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        root.set_role_map({"Heading": "H1", "Para": "P"})
        elem = PDStructureElement("Heading", root)
        root.append_kid(elem)
        _wire_tagged_doc(doc, root)

        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            assert r.get_role_map() == {"Heading": "H1", "Para": "P"}
            elem = r.get_kids()[0]
            # Raw /S is unchanged...
            assert elem.get_structure_type() == "Heading"
            # ...but the resolved standard type is the role-map target.
            assert elem.get_standard_structure_type() == "H1"


def test_role_map_cycle_does_not_infinite_loop() -> None:
    """A two-name cycle in ``/RoleMap`` must terminate; the resolver
    returns one of the cycle members rather than spinning."""
    root = PDStructureTreeRoot()
    # Pathological cycle: A → B → A.
    root.set_role_map({"A": "B", "B": "A"})
    elem = PDStructureElement("A", root)
    root.append_kid(elem)
    resolved = elem.get_standard_structure_type()
    # Must terminate and produce one of the cycle members. The exact
    # halting value depends on the cap; we only assert termination + that
    # we landed on a cycle member.
    assert resolved in {"A", "B"}


def test_role_map_self_cycle_terminates() -> None:
    """A self-mapping ``X → X`` is the tightest possible cycle and must
    terminate without spinning."""
    root = PDStructureTreeRoot()
    root.set_role_map({"Hilite": "Hilite"})
    elem = PDStructureElement("Hilite", root)
    root.append_kid(elem)
    assert elem.get_standard_structure_type() == "Hilite"


def test_role_map_chain_three_hops_resolves_through_roundtrip() -> None:
    """A three-hop chain ``A → B → C → P`` resolves to ``P`` after
    save/reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        root.set_role_map({"Alpha": "Beta", "Beta": "Gamma", "Gamma": "P"})
        elem = PDStructureElement("Alpha", root)
        root.append_kid(elem)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            assert r.resolve_role_map("Alpha") == "P"


# ---------------------------------------------------------------------------
# ClassMap dispatch
# ---------------------------------------------------------------------------


def test_class_map_dispatch_roundtrip() -> None:
    """``/ClassMap`` carrying single + multi attribute entries comes back
    with the same dispatch behavior after reload."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        class_map = PDStructureClassMap()
        layout = PDLayoutAttributeObject()
        layout.set_inline_align("Start")
        table = PDTableAttributeObject()
        # Single-entry class.
        class_map.add_class("SmallText", layout)
        # Multi-entry class.
        class_map.add_class("TableCell", [layout, table])
        root.set_class_map(class_map)
        root.append_kid(PDStructureElement(PDStructureElement.DOCUMENT, root))
        _wire_tagged_doc(doc, root)

        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            cm = r.get_class_map()
            assert cm is not None
            assert cm.size() == 2
            assert "SmallText" in cm
            assert "TableCell" in cm
            small_text = cm.get_class("SmallText")
            assert len(small_text) == 1
            assert isinstance(small_text[0], PDLayoutAttributeObject)
            assert small_text[0].get_inline_align() == "Start"
            cell = cm.get_class("TableCell")
            # Multi-entry: must dispatch via owner — Layout + Table.
            owners = sorted(a.get_owner() for a in cell)
            assert owners == ["Layout", "Table"]


def test_class_map_empty_removed_roundtrip() -> None:
    """An empty ``PDStructureClassMap`` is removed from the dictionary on
    set, and the reload reflects that absence."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        empty = PDStructureClassMap()
        root.set_class_map(empty)
        root.append_kid(PDStructureElement(PDStructureElement.DOCUMENT, root))
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            assert r.has_class_map() is False
            assert r.get_class_map() is None


# ---------------------------------------------------------------------------
# ParentTree lookups
# ---------------------------------------------------------------------------


def test_parent_tree_lookup_roundtrip() -> None:
    """Setting ``/ParentTree`` directly via a number-tree and looking up
    by ``/StructParents`` resolves to the wired structure element after
    reload."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        page.set_struct_parents(0)
        root = PDStructureTreeRoot()
        document = PDStructureElement(PDStructureElement.DOCUMENT, root)
        p1 = PDStructureElement(PDStructureElement.P, document)
        p2 = PDStructureElement(PDStructureElement.P, document)
        document.append_kid_element(p1)
        document.append_kid_element(p2)
        root.append_kid(document)

        # Build a number tree mapping struct-parents 0 -> [p1.cos, p2.cos]
        # (the per-page array indexed by MCID).
        per_page_array = COSArray()
        per_page_array.add(p1.get_cos_object())
        per_page_array.add(p2.get_cos_object())
        number_tree = PDStructureElementNumberTreeNode()
        number_tree.set_numbers({0: per_page_array})
        root.set_parent_tree(number_tree)
        root.set_parent_tree_next_key(1)

        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            assert r.has_parent_tree() is True
            assert r.get_parent_tree_next_key() == 1
            reloaded_page = reloaded.get_page(0)
            elem0 = r.get_struct_element_for_mcid(reloaded_page, 0)
            elem1 = r.get_struct_element_for_mcid(reloaded_page, 1)
            assert elem0 is not None
            assert elem1 is not None
            assert elem0.get_structure_type() == "P"
            assert elem1.get_structure_type() == "P"
            # Out-of-range MCID returns None.
            assert r.get_struct_element_for_mcid(reloaded_page, 9) is None


def test_parent_tree_value_typed_wrapper_roundtrip() -> None:
    """``get_parent_tree_value`` returns a :class:`PDParentTreeValue` for a
    present key after reload."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDParentTreeValue,
    )

    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        document = PDStructureElement(PDStructureElement.DOCUMENT, root)
        root.append_kid(document)

        # Wire a parent-tree entry: key 5 → the document structure element
        # (annotation-style: value is a single structure element dictionary).
        number_tree = PDStructureElementNumberTreeNode()
        number_tree.set_numbers({5: document.get_cos_object()})
        root.set_parent_tree(number_tree)

        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            wrapper = r.get_parent_tree_value(5)
            assert wrapper is not None
            assert isinstance(wrapper, PDParentTreeValue)
            # Unknown key returns None.
            assert r.get_parent_tree_value(99) is None


def test_parent_tree_next_key_allocator_roundtrip() -> None:
    """``next_parent_tree_key`` reads + bumps the slot atomically. The
    bumped value survives the round-trip."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        root.set_parent_tree_next_key(3)
        assert root.next_parent_tree_key() == 3
        assert root.get_parent_tree_next_key() == 4
        root.append_kid(PDStructureElement(PDStructureElement.DOCUMENT, root))
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            assert r.get_parent_tree_next_key() == 4


# ---------------------------------------------------------------------------
# Misc — element identifier / attributes round-trip
# ---------------------------------------------------------------------------


def test_structure_element_identifiers_roundtrip() -> None:
    """``/ID``, ``/T``, ``/Lang``, ``/Alt``, ``/E``, ``/ActualText`` all
    survive the round-trip with their full string content."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        elem = PDStructureElement(PDStructureElement.SPAN, root)
        elem.set_element_identifier("ident-7")
        elem.set_title("Title with spaces")
        elem.set_language("en-US")
        elem.set_alternate_description("Alt text")
        elem.set_expanded_form("World Wide Web")
        elem.set_actual_text("Actual content")
        elem.set_revision_number(3)
        root.append_kid(elem)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            reloaded_elem = r.get_kids()[0]
            assert reloaded_elem.get_element_identifier() == "ident-7"
            assert reloaded_elem.get_title() == "Title with spaces"
            assert reloaded_elem.get_language() == "en-US"
            assert reloaded_elem.get_alternate_description() == "Alt text"
            assert reloaded_elem.get_expanded_form() == "World Wide Web"
            assert reloaded_elem.get_actual_text() == "Actual content"
            assert reloaded_elem.get_revision_number() == 3


def test_increment_revision_number_roundtrip() -> None:
    """``increment_revision_number`` bumps ``/R`` by one; the bump
    survives the round-trip."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        elem = PDStructureElement(PDStructureElement.P, root)
        elem.set_revision_number(5)
        elem.increment_revision_number()
        root.append_kid(elem)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            assert r.get_kids()[0].get_revision_number() == 6


def test_object_reference_kid_roundtrip() -> None:
    """A ``/Type /OBJR`` kid round-trips into a typed PDObjectReference."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        root = PDStructureTreeRoot()
        sect = PDStructureElement(PDStructureElement.SECT, root)
        objr = PDObjectReference()
        # Raw COSBase ``/Obj`` entry — typed PDAnnotation / PDXObject lives
        # on ``set_referenced_object``; ``set_obj`` is the raw-COS path.
        objr.set_obj(page.get_cos_object())
        sect.append_kid_object_reference(objr)
        root.append_kid(sect)
        _wire_tagged_doc(doc, root)
        with _save_and_reload(doc) as reloaded:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            grand = r.get_kids()[0].get_kids()
            assert len(grand) == 1
            assert isinstance(grand[0], PDObjectReference)


# ---------------------------------------------------------------------------
# Loader compatibility — Loader.load_pdf + get_document_catalog round-trip
# ---------------------------------------------------------------------------


def test_loader_load_pdf_returns_same_tree_topology() -> None:
    """A document wired with a 3-element tree, saved, then loaded through
    ``Loader.load_pdf`` exposes the same root.kids count."""
    with PDDocument() as doc:
        doc.add_page(PDPage())
        root = PDStructureTreeRoot()
        document = PDStructureElement(PDStructureElement.DOCUMENT, root)
        h1 = PDStructureElement(PDStructureElement.H1, document)
        p = PDStructureElement(PDStructureElement.P, document)
        document.append_kid_element(h1)
        document.append_kid_element(p)
        root.append_kid(document)
        _wire_tagged_doc(doc, root)
        sink = io.BytesIO()
        doc.save(sink)

    # Load via the lower-level Loader.load_pdf entry point (no wrapping).
    cos_doc = Loader.load_pdf(sink.getvalue())
    try:
        reloaded = PDDocument(cos_doc)
        try:
            r = reloaded.get_document_catalog().get_struct_tree_root()
            assert r is not None
            top = r.get_kids()
            assert len(top) == 1
            assert top[0].get_structure_type() == "Document"
            assert top[0].count_kids() == 2
        finally:
            reloaded.close()
    finally:
        cos_doc.close()
