"""Wave 1348 — coverage-boost pass on ``pypdfbox.multipdf.splitter``.

Targets the remaining uncovered branches:

* public-named hooks (``process_pages``, ``create_new_document_if_necessary``,
  ``process_annotations`` 1-arg form);
* ``_process_annotations`` orphan-popup branch + popup/Parent rewrite paths;
* ``_stage_link_destination`` named-destination resolution (string +
  PDNamedDestination paths) and post-clone action re-read fallback;
* ``clone_structure_tree`` annotation-resource + appearance-stream resource
  walking;
* ``process_resources`` Form/Image XObject branches with /StructParents and
  /StructParent indices.
"""

from __future__ import annotations

from typing import Any

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import Splitter


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


# ---------- public-named hooks (parity with upstream protected methods) ----


def test_process_pages_public_hook_delegates_to_underscored() -> None:
    """``process_pages`` (public-named hook) calls ``_process_pages``."""
    src = _make_doc(2)
    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._current_destination_document = None
    splitter._destination_documents = []
    splitter._page_dict_map = {}
    splitter._page_dict_maps = []
    splitter._annot_dict_map = {}
    splitter._annot_dict_maps = []
    splitter._dest_to_fix = []
    splitter._dest_to_fix_per_chunk = []
    splitter._struct_dict_map = {}
    splitter._struct_dict_maps = []
    splitter._signatures_dropped = False
    splitter.process_pages()
    assert splitter._current_page_number == 2
    for d in splitter._destination_documents:
        d.close()
    src.close()


def test_create_new_document_if_necessary_public_hook() -> None:
    """``create_new_document_if_necessary`` delegates to underscored impl."""
    src = _make_doc(1)
    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._current_destination_document = None
    splitter._destination_documents = []
    splitter._page_dict_map = {}
    splitter._page_dict_maps = []
    splitter._annot_dict_map = {}
    splitter._annot_dict_maps = []
    splitter._dest_to_fix = []
    splitter._dest_to_fix_per_chunk = []
    splitter.create_new_document_if_necessary()
    assert splitter._current_destination_document is not None
    splitter._current_destination_document.close()
    src.close()


def test_process_annotations_public_1arg_hook_with_no_annots() -> None:
    """``process_annotations(imported)`` (1-arg form) is a no-op when the
    page has no annotations — exercises the public-named alias."""
    page = PDPage()
    splitter = Splitter()
    splitter._annot_dict_map = {}
    splitter._signatures_dropped = False
    splitter._dest_to_fix = []
    splitter._page_dict_map = {}
    splitter._current_page_number = 0
    splitter.process_annotations(page)


# ---------- orphan popup + popup/parent rewrite branches ----------


def _add_popup_annot_pair(page: PDPage) -> tuple[COSDictionary, COSDictionary]:
    """Attach a markup ``Text`` annot + an in-page Popup annot. Returns
    (markup_dict, popup_dict). The markup's /Popup points at the popup
    dict, and the popup's /Parent points at the markup dict."""
    markup = COSDictionary()
    markup.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    markup.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    markup.set_item(COSName.get_pdf_name("P"), page.get_cos_object())

    popup = COSDictionary()
    popup.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    popup.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Popup"))
    popup.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    popup.set_item(COSName.get_pdf_name("Parent"), markup)
    markup.set_item(COSName.get_pdf_name("Popup"), popup)

    arr = COSArray()
    arr.add(markup)
    arr.add(popup)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)
    return markup, popup


def test_split_round_trip_with_popup_pair_rewrites_back_refs() -> None:
    """End-to-end split with a markup/popup annot pair on a page. The
    second-pass annotation pass should rewrite the cloned markup's
    ``/Popup`` to the cloned popup and the cloned popup's ``/Parent``
    to the cloned markup, keeping the pair in-chunk."""
    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    _add_popup_annot_pair(page)
    chunks = Splitter().split(src)
    assert len(chunks) == 1
    chunk = chunks[0]
    annots = chunk.get_page(0).get_annotations()
    assert len(annots) == 2
    markup_clone = annots[0].get_cos_object()
    popup_clone = annots[1].get_cos_object()
    # Both back-pointers are wired to the cloned counterparts.
    assert markup_clone.get_dictionary_object(
        COSName.get_pdf_name("Popup")
    ) is popup_clone
    assert popup_clone.get_dictionary_object(
        COSName.get_pdf_name("Parent")
    ) is markup_clone
    chunk.close()
    src.close()


def test_split_drops_popup_parent_when_markup_orphan() -> None:
    """A popup annot whose ``/Parent`` markup is not present in the
    chunk's /Annots gets its /Parent removed (mirrors upstream's
    ``setItem(PARENT, null)``)."""
    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    # Build a popup annot with /Parent pointing at a markup that is NOT
    # included in the page's /Annots array.
    orphan_markup = COSDictionary()
    orphan_markup.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    orphan_markup.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text")
    )

    popup = COSDictionary()
    popup.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    popup.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Popup"))
    popup.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    popup.set_item(COSName.get_pdf_name("Parent"), orphan_markup)

    arr = COSArray()
    arr.add(popup)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    chunks = Splitter().split(src)
    assert len(chunks) == 1
    popup_clone = chunks[0].get_page(0).get_annotations()[0].get_cos_object()
    # /Parent has been removed because the markup wasn't in the chunk.
    assert not popup_clone.contains_key(COSName.get_pdf_name("Parent"))
    chunks[0].close()
    src.close()


def test_split_clones_orphan_popup_when_markup_lacks_popup_in_annots() -> None:
    """A markup whose ``/Popup`` value is not itself listed in the page's
    /Annots array still gets its popup cloned in the second pass
    (upstream's orphan-popup-clone branch)."""
    src = PDDocument()
    page = PDPage()
    src.add_page(page)
    markup = COSDictionary()
    markup.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    markup.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text"))
    markup.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    # Popup dict NOT in /Annots — orphan path.
    orphan_popup = COSDictionary()
    orphan_popup.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    orphan_popup.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Popup")
    )
    orphan_popup.set_item(
        COSName.get_pdf_name("P"), page.get_cos_object()
    )
    markup.set_item(COSName.get_pdf_name("Popup"), orphan_popup)

    arr = COSArray()
    arr.add(markup)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    chunks = Splitter().split(src)
    assert len(chunks) == 1
    markup_clone = chunks[0].get_page(0).get_annotations()[0].get_cos_object()
    cloned_popup = markup_clone.get_dictionary_object(COSName.get_pdf_name("Popup"))
    assert isinstance(cloned_popup, COSDictionary)
    # Cloned popup is a fresh COSDictionary, not the orphan original.
    assert cloned_popup is not orphan_popup
    # /Parent on the popup clone points back at the markup clone.
    assert cloned_popup.get_dictionary_object(
        COSName.get_pdf_name("Parent")
    ) is markup_clone
    chunks[0].close()
    src.close()


# ---------- _stage_link_destination paths ----------


def test_stage_link_destination_with_str_named_destination() -> None:
    """When ``get_destination()`` returns a bare ``str`` (named
    destination), the staging code wraps it in ``PDNamedDestination``
    and resolves through the source catalog."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    src = _make_doc(2)
    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._dest_to_fix = []
    splitter._annot_dict_map = {}

    # Build a link annot whose /Dest is a bare string (named destination).
    link_dict = COSDictionary()
    link_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    link_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link")
    )
    link_dict.set_item(COSName.get_pdf_name("Dest"), COSName.get_pdf_name("MissingName"))
    link = PDAnnotationLink(link_dict)

    # Should not raise; the named-destination resolution returns None,
    # so the function bails out cleanly.
    splitter._stage_link_destination(
        link, src.get_page(0).get_cos_object(), link_dict
    )
    src.close()


def test_stage_link_destination_str_from_goto_action() -> None:
    """Link with a GoTo action whose ``/D`` is a COSName resolves to a
    Python ``str`` and the staging code wraps it in PDNamedDestination
    (covers the ``isinstance(src_destination, str)`` branch)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    src = _make_doc(1)
    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._dest_to_fix = []
    splitter._annot_dict_map = {}

    # Link with /A (action) /S /GoTo /D /MyName — no top-level /Dest.
    action_dict = COSDictionary()
    action_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Action")
    )
    action_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("GoTo")
    )
    action_dict.set_item(
        COSName.get_pdf_name("D"), COSName.get_pdf_name("MyName")
    )

    link_dict = COSDictionary()
    link_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    link_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link")
    )
    link_dict.set_item(COSName.get_pdf_name("A"), action_dict)
    link = PDAnnotationLink(link_dict)

    splitter._stage_link_destination(
        link, src.get_page(0).get_cos_object(), link_dict
    )
    src.close()


def test_stage_link_destination_get_page_raises_is_tolerated() -> None:
    """When ``src_destination.get_page()`` raises, the target snapshot
    stays ``None`` and processing continues (covers lines 935-936)."""
    from pypdfbox.cos import COSString
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    src = _make_doc(1)
    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._dest_to_fix = []
    splitter._annot_dict_map = {}

    # Build /Names /Dests with our named entry pointing at a page array.
    target_array = COSArray()
    target_array.add(src.get_page(0).get_cos_object())
    target_array.add(COSName.get_pdf_name("Fit"))
    dests_node_dict = COSDictionary()
    names = COSArray()
    names.add(COSString("BoomDest"))
    names.add(target_array)
    dests_node_dict.set_item(COSName.get_pdf_name("Names"), names)
    names_dict = COSDictionary()
    names_dict.set_item(COSName.get_pdf_name("Dests"), dests_node_dict)
    src.get_document_catalog().get_cos_object().set_item(
        COSName.get_pdf_name("Names"), names_dict
    )

    # Build a link whose /Dest = COSString("BoomDest") — resolution returns
    # a PDPageDestination whose .get_page() raises.
    link_dict = COSDictionary()
    link_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    link_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link")
    )
    link_dict.set_item(COSName.get_pdf_name("Dest"), COSString("BoomDest"))
    link = PDAnnotationLink(link_dict)

    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
        PDPageDestination,
    )

    real_get_page = PDPageDestination.get_page

    def boom_get_page(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated")

    # Patch PDPageDestination.get_page to raise so the staging code's
    # except branch (935-936) executes. Restore afterwards.
    PDPageDestination.get_page = boom_get_page  # type: ignore[method-assign]
    try:
        splitter._stage_link_destination(
            link, src.get_page(0).get_cos_object(), link_dict
        )
    finally:
        PDPageDestination.get_page = real_get_page  # type: ignore[method-assign]
    src.close()


def test_stage_link_destination_link_get_action_raises_uses_source_action() -> None:
    """When the cloned link's ``get_action()`` raises after the source
    link had a GoTo action, ``cloned_action`` falls back to ``None`` and
    the original action dict is cloned (covers lines 957-958)."""
    from pypdfbox.cos import COSString
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    src = _make_doc(1)
    splitter = Splitter()
    splitter._source_document = src
    splitter._current_page_number = 0
    splitter._dest_to_fix = []
    splitter._annot_dict_map = {}

    # Build a name-tree /Dests so the named lookup yields a real
    # PDPageDestination (which has get_cos_object→COSArray).
    target_array = COSArray()
    target_array.add(src.get_page(0).get_cos_object())
    target_array.add(COSName.get_pdf_name("Fit"))
    dests_node_dict = COSDictionary()
    names = COSArray()
    names.add(COSString("D1"))
    names.add(target_array)
    dests_node_dict.set_item(COSName.get_pdf_name("Names"), names)
    names_dict = COSDictionary()
    names_dict.set_item(COSName.get_pdf_name("Dests"), dests_node_dict)
    src.get_document_catalog().get_cos_object().set_item(
        COSName.get_pdf_name("Names"), names_dict
    )

    # Link with /A GoTo /D /D1 — source-side resolution_link comes from
    # the source dict; the cloned link is the one passed positionally.
    action_dict = COSDictionary()
    action_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Action")
    )
    action_dict.set_item(
        COSName.get_pdf_name("S"), COSName.get_pdf_name("GoTo")
    )
    action_dict.set_item(COSName.get_pdf_name("D"), COSName.get_pdf_name("D1"))
    link_dict = COSDictionary()
    link_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    link_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link")
    )
    link_dict.set_item(COSName.get_pdf_name("A"), action_dict)

    class BadLink(PDAnnotationLink):  # type: ignore[misc]
        def get_action(self):  # type: ignore[no-untyped-def, override]
            raise RuntimeError("re-read failed")

    link = BadLink(link_dict)
    splitter._stage_link_destination(
        link, src.get_page(0).get_cos_object(), link_dict
    )
    src.close()


def test_stage_link_destination_resolved_named_destination_round_trip() -> None:
    """End-to-end split with a Link annot that references a named
    destination installed in the source catalog's /Names /Dests tree."""
    from pypdfbox.cos import COSString

    src = _make_doc(2)
    # Build a /Dests name tree mapping "MyDest" → [page0, /Fit].
    target_array = COSArray()
    target_array.add(src.get_page(0).get_cos_object())
    target_array.add(COSName.get_pdf_name("Fit"))
    dests_node_dict = COSDictionary()
    names = COSArray()
    names.add(COSString("MyDest"))
    names.add(target_array)
    dests_node_dict.set_item(COSName.get_pdf_name("Names"), names)
    # Hook the dests tree to the catalog via /Names /Dests.
    catalog_dict = src.get_document_catalog().get_cos_object()
    names_dict = COSDictionary()
    names_dict.set_item(COSName.get_pdf_name("Dests"), dests_node_dict)
    catalog_dict.set_item(COSName.get_pdf_name("Names"), names_dict)

    # Build a link on page 1 referencing the named destination.
    link_dict = COSDictionary()
    link_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot")
    )
    link_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link")
    )
    link_dict.set_item(COSName.get_pdf_name("Dest"), COSString("MyDest"))

    arr = COSArray()
    arr.add(link_dict)
    src.get_page(1).get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    chunks = Splitter().split(src)
    # Both pages split into separate chunks.
    assert len(chunks) == 2
    for chunk in chunks:
        chunk.close()
    src.close()


# ---------- clone_structure_tree annotation + page resource walks ----------


def test_clone_structure_tree_walks_annotation_struct_parent() -> None:
    """Annotations carrying /StructParent should have their entry copied
    into the chunk's parent tree."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElement,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
        PDStructureElementNumberTreeNode,
    )

    src = PDDocument()
    page = PDPage()
    page.set_struct_parents(0)
    src.add_page(page)

    # Build an annot with /StructParent = 1.
    ann_dict = COSDictionary()
    ann_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    ann_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text")
    )
    ann_dict.set_item(COSName.get_pdf_name("StructParent"), COSInteger.get(1))
    ann_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    arr = COSArray()
    arr.add(ann_dict)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    # Build a struct tree with parent-tree entries 0 (page) and 1 (annot).
    struct_root = PDStructureTreeRoot()
    document_elem = PDStructureElement(structure_type="Document")
    p_page = PDStructureElement(structure_type="P")
    p_page.set_page(page)
    document_elem.append_kid(p_page)
    p_page.get_cos_object().set_item(
        COSName.get_pdf_name("P"), document_elem.get_cos_object()
    )
    p_ann = PDStructureElement(structure_type="P")
    p_ann.set_page(page)
    document_elem.append_kid(p_ann)
    p_ann.get_cos_object().set_item(
        COSName.get_pdf_name("P"), document_elem.get_cos_object()
    )
    struct_root.append_kid(document_elem)
    document_elem.get_cos_object().set_item(
        COSName.get_pdf_name("P"), struct_root.get_cos_object()
    )

    parent_tree_dict = COSDictionary()
    parent_tree_node = PDStructureElementNumberTreeNode(parent_tree_dict)
    parent_tree_node.set_numbers(
        {0: p_page.get_cos_object(), 1: p_ann.get_cos_object()}
    )
    struct_root.set_parent_tree(parent_tree_node)
    struct_root.set_parent_tree_next_key(2)
    src.get_document_catalog().set_struct_tree_root(struct_root)

    chunks = Splitter().split(src)
    assert len(chunks) == 1
    chunk = chunks[0]
    dst_root = chunk.get_document_catalog().get_struct_tree_root()
    assert dst_root is not None
    chunk.close()
    src.close()


# ---------- process_resources Form/Image XObject branches ----------


def test_split_with_non_dict_entry_in_source_annots_array() -> None:
    """Source-side /Annots array may contain non-dict entries (e.g. nulls
    or stray names) — the second-pass loop must skip them via the
    ``isinstance(candidate, COSDictionary)`` guard (covers line 636)."""
    src = PDDocument()
    page = PDPage()
    src.add_page(page)

    # Build a real markup/popup pair, then prepend a non-dictionary entry
    # (a stray COSName) to the source /Annots array. The cloned page's
    # /Annots starts at index 0 with the markup, so the source-side walk
    # has to skip past index 0 (the COSName) without crashing.
    from pypdfbox.cos import COSName as _N

    markup = COSDictionary()
    markup.set_item(_N.get_pdf_name("Type"), _N.get_pdf_name("Annot"))
    markup.set_item(_N.get_pdf_name("Subtype"), _N.get_pdf_name("Text"))
    markup.set_item(_N.get_pdf_name("P"), page.get_cos_object())
    popup = COSDictionary()
    popup.set_item(_N.get_pdf_name("Type"), _N.get_pdf_name("Annot"))
    popup.set_item(_N.get_pdf_name("Subtype"), _N.get_pdf_name("Popup"))
    popup.set_item(_N.get_pdf_name("P"), page.get_cos_object())
    popup.set_item(_N.get_pdf_name("Parent"), markup)
    markup.set_item(_N.get_pdf_name("Popup"), popup)

    arr = COSArray()
    # Prepend a stray name (non-dict). Annotation iteration skips it.
    arr.add(_N.get_pdf_name("Junk"))
    arr.add(markup)
    arr.add(popup)
    page.get_cos_object().set_item(_N.get_pdf_name("Annots"), arr)

    chunks = Splitter().split(src)
    assert len(chunks) == 1
    chunks[0].close()
    src.close()


def test_clone_structure_tree_walks_annotation_appearance_resources() -> None:
    """An annotation with a normal-appearance stream that carries its own
    /Resources should have those resources walked for /StructParent
    entries (covers lines 1114-1118)."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElement,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
        PDStructureElementNumberTreeNode,
    )

    src = PDDocument()
    page = PDPage()
    page.set_struct_parents(0)
    src.add_page(page)

    # Build an /AP /N appearance stream with its own /Resources dict.
    app_stream = COSStream()
    app_stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    app_stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    app_stream.set_item(COSName.get_pdf_name("BBox"), COSArray())
    app_resources_dict = COSDictionary()
    app_stream.set_item(COSName.get_pdf_name("Resources"), app_resources_dict)

    ap_dict = COSDictionary()
    ap_dict.set_item(COSName.get_pdf_name("N"), app_stream)

    ann_dict = COSDictionary()
    ann_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    ann_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text")
    )
    ann_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    ann_dict.set_item(COSName.get_pdf_name("AP"), ap_dict)
    arr = COSArray()
    arr.add(ann_dict)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    # Minimal struct tree: one element on page 0.
    struct_root = PDStructureTreeRoot()
    document_elem = PDStructureElement(structure_type="Document")
    p_elem = PDStructureElement(structure_type="P")
    p_elem.set_page(page)
    document_elem.append_kid(p_elem)
    p_elem.get_cos_object().set_item(
        COSName.get_pdf_name("P"), document_elem.get_cos_object()
    )
    struct_root.append_kid(document_elem)
    document_elem.get_cos_object().set_item(
        COSName.get_pdf_name("P"), struct_root.get_cos_object()
    )
    parent_tree_dict = COSDictionary()
    parent_tree_node = PDStructureElementNumberTreeNode(parent_tree_dict)
    parent_tree_node.set_numbers({0: p_elem.get_cos_object()})
    struct_root.set_parent_tree(parent_tree_node)
    struct_root.set_parent_tree_next_key(1)
    src.get_document_catalog().set_struct_tree_root(struct_root)

    chunks = Splitter().split(src)
    assert len(chunks) == 1
    chunks[0].close()
    src.close()


def test_clone_structure_tree_appearance_get_resources_raises() -> None:
    """When an annotation's normal appearance stream raises on
    ``get_resources()``, the clone walker swallows it and falls through
    to process_resources(None, ...) (covers lines 1116-1117)."""
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElement,
        PDStructureTreeRoot,
    )
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
        PDStructureElementNumberTreeNode,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
        PDAnnotation,
    )

    src = PDDocument()
    page = PDPage()
    page.set_struct_parents(0)
    src.add_page(page)

    # Plain text annot on the page.
    ann_dict = COSDictionary()
    ann_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    ann_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Text")
    )
    ann_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    arr = COSArray()
    arr.add(ann_dict)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), arr)

    # Minimal struct tree.
    struct_root = PDStructureTreeRoot()
    document_elem = PDStructureElement(structure_type="Document")
    p_elem = PDStructureElement(structure_type="P")
    p_elem.set_page(page)
    document_elem.append_kid(p_elem)
    p_elem.get_cos_object().set_item(
        COSName.get_pdf_name("P"), document_elem.get_cos_object()
    )
    struct_root.append_kid(document_elem)
    document_elem.get_cos_object().set_item(
        COSName.get_pdf_name("P"), struct_root.get_cos_object()
    )
    parent_tree_dict = COSDictionary()
    parent_tree_node = PDStructureElementNumberTreeNode(parent_tree_dict)
    parent_tree_node.set_numbers({0: p_elem.get_cos_object()})
    struct_root.set_parent_tree(parent_tree_node)
    struct_root.set_parent_tree_next_key(1)
    src.get_document_catalog().set_struct_tree_root(struct_root)

    # Patch PDAnnotation.get_normal_appearance_stream to return a stub
    # whose get_resources() raises — exercises the except branch.
    real_method = PDAnnotation.get_normal_appearance_stream

    class _BadAppStream:
        def get_resources(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("simulated")

    def bad_get(self):  # type: ignore[no-untyped-def]
        return _BadAppStream()

    PDAnnotation.get_normal_appearance_stream = bad_get  # type: ignore[method-assign]
    try:
        chunks = Splitter().split(src)
    finally:
        PDAnnotation.get_normal_appearance_stream = real_method  # type: ignore[method-assign]
    assert len(chunks) == 1
    chunks[0].close()
    src.close()


def test_process_resources_form_xobject_with_struct_parents() -> None:
    """``process_resources`` walks Form XObjects: reads
    ``get_struct_parents()`` (plural — note the trailing ``s``), copies
    matching entries from src to dst, and recurses into nested
    /Resources."""
    splitter = Splitter()

    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    # Build a real Form XObject with /StructParents.
    form_dict = COSDictionary()
    form_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    form_dict.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    form_dict.set_item(COSName.get_pdf_name("BBox"), COSArray())
    form_dict.set_item(COSName.get_pdf_name("StructParents"), COSInteger.get(7))

    class StubResources:
        def __init__(self, name_to_xobj):  # type: ignore[no-untyped-def]
            self._name_to_xobj = name_to_xobj
            self._cos = COSDictionary()

        def get_cos_object(self):  # type: ignore[no-untyped-def]
            return self._cos

        def get_xobject_names(self):  # type: ignore[no-untyped-def]
            return list(self._name_to_xobj.keys())

        def get_x_object(self, name):  # type: ignore[no-untyped-def]
            return self._name_to_xobj[name]

    from pypdfbox.cos import COSStream
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    stream.set_item(COSName.get_pdf_name("BBox"), COSArray())
    stream.set_item(COSName.get_pdf_name("StructParents"), COSInteger.get(7))
    form = PDFormXObject(stream)
    resources = StubResources({"F1": form})

    # Parent-tree entries are COSArray (per page) or COSDictionary (per
    # element). Use a COSArray so clone_tree_element walks the array
    # branch.
    sp_array = COSArray()
    sp_array.add(COSDictionary())
    splitter._struct_dict_map = {}
    src_numbers: dict[int, Any] = {7: sp_array}
    dst_numbers: dict[int, Any] = {}
    splitter.process_resources(resources, src_numbers, dst_numbers, set())
    assert 7 in dst_numbers


def test_process_resources_image_xobject_with_struct_parent() -> None:
    """``process_resources`` walks Image XObjects: reads
    ``get_struct_parent()`` (singular — no ``s``) and copies matching
    entries from src to dst."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    splitter = Splitter()

    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image")
    )
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    stream.set_item(COSName.get_pdf_name("StructParent"), COSInteger.get(5))
    image = PDImageXObject(stream)

    class StubResources:
        def __init__(self, name_to_xobj):  # type: ignore[no-untyped-def]
            self._name_to_xobj = name_to_xobj
            self._cos = COSDictionary()

        def get_cos_object(self):  # type: ignore[no-untyped-def]
            return self._cos

        def get_xobject_names(self):  # type: ignore[no-untyped-def]
            return list(self._name_to_xobj.keys())

        def get_x_object(self, name):  # type: ignore[no-untyped-def]
            return self._name_to_xobj[name]

    resources = StubResources({"I1": image})
    sp_array = COSArray()
    splitter._struct_dict_map = {}
    src_numbers: dict[int, Any] = {5: sp_array}
    dst_numbers: dict[int, Any] = {}
    splitter.process_resources(resources, src_numbers, dst_numbers, set())
    assert 5 in dst_numbers


def test_process_resources_xobject_get_raises_continues() -> None:
    """Each XObject access is guarded — a raising ``get_x_object`` for one
    name shouldn't break the loop."""
    splitter = Splitter()

    class StubResources:
        def get_cos_object(self):  # type: ignore[no-untyped-def]
            return COSDictionary()

        def get_xobject_names(self):  # type: ignore[no-untyped-def]
            return ["X1"]

        def get_x_object(self, name):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    splitter.process_resources(StubResources(), {}, {}, set())


def test_process_resources_resources_get_cos_object_raises_returns() -> None:
    """A resources object whose ``get_cos_object`` raises
    ``AttributeError`` short-circuits."""
    splitter = Splitter()

    class BadResources:
        def get_cos_object(self):  # type: ignore[no-untyped-def]
            raise AttributeError("nope")

    splitter.process_resources(BadResources(), {}, {}, set())


def test_process_resources_get_xobject_names_raises_returns() -> None:
    """Resources whose ``get_xobject_names`` raises bail out cleanly."""
    splitter = Splitter()

    class BadResources:
        def get_cos_object(self):  # type: ignore[no-untyped-def]
            return COSDictionary()

        def get_xobject_names(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("xobject discovery failed")

    splitter.process_resources(BadResources(), {}, {}, set())


def test_process_resources_form_xobject_with_struct_parents_raise() -> None:
    """Form XObject whose ``get_struct_parents()`` raises is tolerated;
    nested resources still get walked."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

    splitter = Splitter()
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form")
    )
    stream.set_item(COSName.get_pdf_name("BBox"), COSArray())
    # No /StructParents — get_struct_parents() returns -1 by default.

    class FormStub(PDFormXObject):  # type: ignore[misc]
        def get_struct_parents(self):  # type: ignore[no-untyped-def, override]
            raise RuntimeError("nope")

        def get_resources(self):  # type: ignore[no-untyped-def, override]
            raise RuntimeError("nope2")

    form = FormStub(stream)

    class StubResources:
        def __init__(self, name_to_xobj):  # type: ignore[no-untyped-def]
            self._name_to_xobj = name_to_xobj
            self._cos = COSDictionary()

        def get_cos_object(self):  # type: ignore[no-untyped-def]
            return self._cos

        def get_xobject_names(self):  # type: ignore[no-untyped-def]
            return list(self._name_to_xobj.keys())

        def get_x_object(self, name):  # type: ignore[no-untyped-def]
            return self._name_to_xobj[name]

    splitter.process_resources(StubResources({"F1": form}), {}, {}, set())


def test_process_resources_image_xobject_struct_parent_raise() -> None:
    """Image XObject whose ``get_struct_parent()`` raises is tolerated."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    splitter = Splitter()
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image")
    )
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )

    class ImageStub(PDImageXObject):  # type: ignore[misc]
        def get_struct_parent(self):  # type: ignore[no-untyped-def, override]
            raise RuntimeError("nope")

    image = ImageStub(stream)

    class StubResources:
        def __init__(self, name_to_xobj):  # type: ignore[no-untyped-def]
            self._name_to_xobj = name_to_xobj
            self._cos = COSDictionary()

        def get_cos_object(self):  # type: ignore[no-untyped-def]
            return self._cos

        def get_xobject_names(self):  # type: ignore[no-untyped-def]
            return list(self._name_to_xobj.keys())

        def get_x_object(self, name):  # type: ignore[no-untyped-def]
            return self._name_to_xobj[name]

    splitter.process_resources(StubResources({"I1": image}), {}, {}, set())
