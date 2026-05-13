"""Hand-written tests for ``Splitter`` structure-tree cloning.

Each test builds a small structured 4-page PDF, splits-every-2, then
asserts that the chunks each carry a ``/StructTreeRoot`` containing
exactly the structure elements that pertain to that chunk's pages,
plus a fresh ``/ParentTree`` keyed by the chunk's ``/StructParents``
indices.
"""

from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
    PDStructureElementNumberTreeNode,
)

# ---------- helpers ----------


def _make_structured_doc(n_pages: int = 4) -> PDDocument:
    """Build a tagged-PDF stand-in with ``n_pages`` and one structure
    element per page wired into a ``/StructTreeRoot`` + ``/ParentTree``.

    The structure tree looks like::

        StructTreeRoot
          /K = Document
              /K = [P_0, P_1, ..., P_{n-1}]   # one P per page

    Each ``P_i`` carries ``/Pg = page_i`` and an ``/ID``. Pages get a
    sequential ``/StructParents`` index pointing into the parent tree.
    """
    doc = PDDocument()
    pages: list[PDPage] = []
    for i in range(n_pages):
        page = PDPage()
        page.set_struct_parents(i)
        doc.add_page(page)
        pages.append(page)

    struct_root = PDStructureTreeRoot()
    document_elem = PDStructureElement(structure_type="Document")
    p_elements: list[PDStructureElement] = []
    for i in range(n_pages):
        p = PDStructureElement(structure_type="P")
        p.set_page(pages[i])
        p.set_id(f"id_p{i}")
        # /P → parent
        p.get_cos_object().set_item(
            COSName.get_pdf_name("P"), document_elem.get_cos_object()
        )
        document_elem.append_kid(p)
        p_elements.append(p)
    struct_root.append_kid(document_elem)
    document_elem.get_cos_object().set_item(
        COSName.get_pdf_name("P"), struct_root.get_cos_object()
    )

    # Build /ParentTree: index i → P_i dict
    parent_tree_dict = COSDictionary()
    parent_tree_node = PDStructureElementNumberTreeNode(parent_tree_dict)
    parent_tree_node.set_numbers(
        {i: p_elements[i].get_cos_object() for i in range(n_pages)}
    )
    struct_root.set_parent_tree(parent_tree_node)
    struct_root.set_parent_tree_next_key(n_pages)

    # /RoleMap with two entries — only "P" should survive into chunks.
    struct_root.set_role_map({"P": "P", "Caption": "Caption"})

    # /IDTree with one entry per element.
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (  # noqa: E501
        PDStructureElementNameTreeNode,
    )

    id_tree = PDStructureElementNameTreeNode()
    id_tree.set_names(
        {f"id_p{i}": p_elements[i] for i in range(n_pages)}
    )
    struct_root.set_id_tree(id_tree)

    doc.get_document_catalog().set_struct_tree_root(struct_root)
    return doc


# ---------- tests ----------


def test_split_every_two_emits_struct_tree_root_per_chunk() -> None:
    src = _make_structured_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    assert len(chunks) == 2
    for chunk in chunks:
        chunk_root = chunk.get_document_catalog().get_struct_tree_root()
        assert chunk_root is not None, "expected /StructTreeRoot on each chunk"
        chunk.close()
    src.close()


def test_chunk_struct_tree_only_carries_chunk_page_elements() -> None:
    """The cloned ``/K`` subtree must reference only the structure
    elements that pertain to pages in this chunk — i.e. P_0 + P_1 in the
    first chunk and P_2 + P_3 in the second."""
    src = _make_structured_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)

    expected_per_chunk = [{"id_p0", "id_p1"}, {"id_p2", "id_p3"}]
    for chunk, expected_ids in zip(chunks, expected_per_chunk, strict=True):
        chunk_root = chunk.get_document_catalog().get_struct_tree_root()
        assert chunk_root is not None
        ids_seen: set[str] = set()
        _collect_ids(chunk_root.get_cos_object(), ids_seen)
        assert ids_seen == expected_ids, (
            f"chunk struct-tree carries unexpected ids: {ids_seen}"
        )
        chunk.close()
    src.close()


def test_chunk_parent_tree_only_keys_chunk_pages() -> None:
    """The fresh ``/ParentTree`` should only contain entries for the
    ``/StructParents`` indices used by chunk pages, with values pointing
    at the cloned (not source) structure elements."""
    src = _make_structured_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)

    expected_keys_per_chunk = [{0, 1}, {2, 3}]
    for chunk, expected_keys in zip(chunks, expected_keys_per_chunk, strict=True):
        chunk_root = chunk.get_document_catalog().get_struct_tree_root()
        assert chunk_root is not None
        parent_tree = chunk_root.get_parent_tree()
        assert parent_tree is not None
        numbers = parent_tree.get_numbers()
        assert numbers is not None
        assert set(numbers.keys()) == expected_keys
        # Sanity: each value resolves to a /StructElem dict with the
        # expected /S role.
        for _key, value in numbers.items():
            assert isinstance(value, COSDictionary)
            assert value.get_name(COSName.get_pdf_name("S")) == "P"
        chunk.close()
    src.close()


def test_chunk_id_tree_only_keys_chunk_ids() -> None:
    src = _make_structured_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)

    expected_per_chunk = [{"id_p0", "id_p1"}, {"id_p2", "id_p3"}]
    for chunk, expected_ids in zip(chunks, expected_per_chunk, strict=True):
        chunk_root = chunk.get_document_catalog().get_struct_tree_root()
        assert chunk_root is not None
        id_tree = chunk_root.get_id_tree()
        assert id_tree is not None
        names = id_tree.get_names()
        assert names is not None
        assert set(names.keys()) == expected_ids
        chunk.close()
    src.close()


def test_chunk_role_map_narrows_to_used_roles() -> None:
    """``/RoleMap`` should be carried but narrowed to the ``/S`` roles
    that actually appear among retained structure elements. The
    structured doc has ``Document`` + ``P`` retained; ``Caption`` (which
    no element uses) must be dropped."""
    src = _make_structured_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    for chunk in chunks:
        chunk_root = chunk.get_document_catalog().get_struct_tree_root()
        assert chunk_root is not None
        role_map = chunk_root.get_role_map()
        # P is retained; Caption was unused.
        assert "P" in role_map or "Document" in role_map
        assert "Caption" not in role_map
        chunk.close()
    src.close()


def test_split_no_struct_tree_source_is_no_op() -> None:
    """Sources without a ``/StructTreeRoot`` are split unchanged — the
    new clone path must short-circuit cleanly."""
    src = PDDocument()
    for _ in range(4):
        src.add_page(PDPage())
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    assert len(chunks) == 2
    for chunk in chunks:
        assert chunk.get_document_catalog().get_struct_tree_root() is None
        chunk.close()
    src.close()


def test_struct_tree_split_round_trips_through_save_load() -> None:
    """Each chunk must remain saveable / re-loadable with its struct
    tree intact."""
    import io

    src = _make_structured_doc(4)
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    blobs = []
    for chunk in chunks:
        sink = io.BytesIO()
        chunk.save(sink)
        blobs.append(sink.getvalue())
        chunk.close()
    src.close()

    for blob in blobs:
        with PDDocument.load(blob) as reloaded:
            root = reloaded.get_document_catalog().get_struct_tree_root()
            assert root is not None, "round-trip lost /StructTreeRoot"


# ---------- destination remap ----------


def test_link_dest_to_outside_chunk_is_nulled() -> None:
    """A link annotation on chunk-1 page-0 pointing at source page-3
    should be cleared since the target is in chunk-2."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    src = _make_structured_doc(4)
    pages = list(src.get_pages())
    # Build a /Dest pointing at page-3 (outside chunk-1).
    link = PDAnnotationLink()
    dest_array = COSArray()
    dest_array.add(pages[3].get_cos_object())
    dest_array.add(COSName.get_pdf_name("XYZ"))
    link.get_cos_object().set_item(COSName.get_pdf_name("Dest"), dest_array)
    pages[0].set_annotations([link])

    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)

    chunk1_page0 = list(chunks[0].get_pages())[0]
    annots = chunk1_page0.get_annotations()
    assert len(annots) == 1
    cloned_link = annots[0]
    cloned_dest = cloned_link.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Dest")
    )
    assert isinstance(cloned_dest, COSArray)
    target = cloned_dest.get_object(0)
    # Cross-chunk destination → nulled out.
    from pypdfbox.cos import COSNull

    assert target is COSNull.NULL or target is None or (
        hasattr(target, "is_null") and target.is_null()
    )

    for chunk in chunks:
        chunk.close()
    src.close()


def test_link_dest_within_chunk_rewritten_to_cloned_page() -> None:
    """A link annotation on chunk-1 page-0 pointing at page-1 (same
    chunk) must be rewritten to the *cloned* page-1 dict, not the
    source's."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    src = _make_structured_doc(4)
    pages = list(src.get_pages())
    link = PDAnnotationLink()
    dest_array = COSArray()
    dest_array.add(pages[1].get_cos_object())
    dest_array.add(COSName.get_pdf_name("XYZ"))
    link.get_cos_object().set_item(COSName.get_pdf_name("Dest"), dest_array)
    pages[0].set_annotations([link])

    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)

    chunk1_pages = list(chunks[0].get_pages())
    cloned_page1_dict = chunk1_pages[1].get_cos_object()
    annots = chunk1_pages[0].get_annotations()
    assert len(annots) == 1
    cloned_dest = annots[0].get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Dest")
    )
    assert isinstance(cloned_dest, COSArray)
    assert cloned_dest.get_object(0) is cloned_page1_dict, (
        "in-chunk /Dest must point at the cloned destination page"
    )

    for chunk in chunks:
        chunk.close()
    src.close()


# ---------- internals ----------


def _collect_ids(node: COSDictionary, out: set[str]) -> None:
    """Walk a /K subtree and collect every dictionary's /ID string."""
    id_value = node.get_string(COSName.get_pdf_name("ID"))
    if id_value is not None:
        out.add(id_value)
    k = node.get_dictionary_object(COSName.get_pdf_name("K"))
    if k is None:
        return
    if isinstance(k, COSArray):
        for i in range(k.size()):
            entry = k.get_object(i)
            if isinstance(entry, COSDictionary):
                _collect_ids(entry, out)
    elif isinstance(k, COSDictionary):
        _collect_ids(k, out)
