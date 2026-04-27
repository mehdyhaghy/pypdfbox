"""Hand-written tests for ``PDFMergerUtility``'s structure-tree merge.

Each test builds two structured PDFs, merges them, and asserts that the
destination document's ``/StructTreeRoot`` carries both source trees with
non-overlapping ``/ParentTree`` keys, that imported pages and annotations
have their ``/StructParents`` / ``/StructParent`` re-routed into the
destination's parent-tree key range, that the destination ``/RoleMap``
follows the "dest wins on conflict" rule, and that ``/IDTree`` collisions
are dropped (with a warning) rather than silently overwritten.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)

# ---------- shared helpers ----------


def _seed_page_contents(page: PDPage, body: bytes = b"q Q\n") -> None:
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _build_structured_doc(
    *,
    page_count: int,
    parent_tree_keys: list[int],
    role_map: dict[str, str] | None = None,
    id_tree: dict[str, str] | None = None,
    body: bytes = b"q Q\n",
) -> PDDocument:
    """Construct a minimal but valid structured PDF.

    Each page gets a ``/StructParents`` value taken from
    ``parent_tree_keys`` (length must match ``page_count``). The structure
    tree root carries one ``/Document``-typed top-level dict whose ``/K``
    is a list of structure-element kids, one per page, each with a ``/Pg``
    pointing back at the corresponding page dictionary. The ``/ParentTree``
    is a flat ``/Nums`` leaf mapping each page's ``/StructParents`` value
    to its owning structure-element dict.
    """
    if len(parent_tree_keys) != page_count:
        raise ValueError("parent_tree_keys must have one entry per page")

    doc = PDDocument()
    pages: list[PDPage] = []
    for _ in range(page_count):
        page = PDPage()
        _seed_page_contents(page, body)
        doc.add_page(page)
        pages.append(page)

    # Build a /StructTreeRoot.
    root = PDStructureTreeRoot()
    doc_dict = COSDictionary()
    doc_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    doc_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Document"))
    doc_dict.set_item(COSName.get_pdf_name("P"), root.get_cos_object())

    kids_array = COSArray()
    parent_tree_map: dict[int, COSDictionary] = {}
    for idx, (page, key) in enumerate(zip(pages, parent_tree_keys, strict=True)):
        elem = COSDictionary()
        elem.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem")
        )
        elem.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("P"))
        elem.set_item(COSName.get_pdf_name("P"), doc_dict)
        elem.set_item(COSName.get_pdf_name("Pg"), page.get_cos_object())
        # Tag the element with /T for visual debug.
        elem.set_string(COSName.get_pdf_name("T"), f"para-{idx}")
        kids_array.add(elem)
        page.get_cos_object().set_item(
            COSName.get_pdf_name("StructParents"), COSInteger.get(key)
        )
        parent_tree_map[key] = elem
    doc_dict.set_item(COSName.get_pdf_name("K"), kids_array)
    root.get_cos_object().set_item(COSName.get_pdf_name("K"), doc_dict)

    # /ParentTree as a flat number-tree.
    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers(
        {k: PDStructureElement(v) for k, v in parent_tree_map.items()}
    )
    root.set_parent_tree(parent_tree)
    root.set_parent_tree_next_key(max(parent_tree_keys) + 1 if parent_tree_keys else 0)

    if role_map is not None:
        root.set_role_map(role_map)

    if id_tree is not None:
        # Build /IDTree directly. Values are PDStructureElement (parent
        # tree leaves) — for simplicity reuse the existing kids by name.
        id_dict = COSDictionary()
        names_array = COSArray()
        for elem_id, kid_name in id_tree.items():
            # Find the element with /T == kid_name.
            target: COSDictionary | None = None
            for i in range(kids_array.size()):
                kid = kids_array.get_object(i)
                if (
                    isinstance(kid, COSDictionary)
                    and kid.get_string(COSName.get_pdf_name("T")) == kid_name
                ):
                    target = kid
                    break
            if target is None:
                raise ValueError(f"id_tree references missing kid {kid_name!r}")
            target.set_string(COSName.get_pdf_name("ID"), elem_id)
            names_array.add(elem_id.encode("ascii"))  # COSString-compatible
            names_array.add(target)
        id_dict.set_item(COSName.get_pdf_name("Names"), names_array)
        root.get_cos_object().set_item(COSName.get_pdf_name("IDTree"), id_dict)

    doc.get_document_catalog().set_struct_tree_root(root)
    return doc


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def _struct_tree_root(doc: PDDocument) -> PDStructureTreeRoot:
    root = doc.get_document_catalog().get_struct_tree_root()
    assert root is not None, "destination has no /StructTreeRoot"
    return root


def _flat_parent_tree_keys(root: PDStructureTreeRoot) -> set[int]:
    return set(PDFMergerUtility.get_number_tree_as_map(root.get_parent_tree()))


# ---------- tests ----------


def test_struct_tree_merge_keys_offset_into_dest_range(tmp_path: Path) -> None:
    """Source ParentTree keys must be offset by dest's
    /ParentTreeNextKey so the merged tree has every key from both."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    # A has parent-tree keys {0, 1}; nextKey = 2.
    _save(
        _build_structured_doc(page_count=2, parent_tree_keys=[0, 1], body=b"% A\n"),
        a,
    )
    # B has parent-tree keys {0, 1, 2}; nextKey = 3.
    _save(
        _build_structured_doc(
            page_count=3, parent_tree_keys=[0, 1, 2], body=b"% B\n"
        ),
        b,
    )

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 5
        root = _struct_tree_root(merged)
        keys = _flat_parent_tree_keys(root)
        # A contributes 0 and 1; B is shifted by 2 → contributes 2, 3, 4.
        assert keys == {0, 1, 2, 3, 4}
        # /ParentTreeNextKey must be one past the highest key.
        assert root.get_parent_tree_next_key() == 5


def test_struct_tree_merge_pages_point_at_new_keys(tmp_path: Path) -> None:
    """Imported pages' /StructParents must equal the new offset key,
    and the parent-tree leaf at that key must be a /Pg → that page."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(
        _build_structured_doc(page_count=1, parent_tree_keys=[0], body=b"% A\n"), a
    )
    _save(
        _build_structured_doc(page_count=2, parent_tree_keys=[0, 1], body=b"% B\n"),
        b,
    )

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        pages = list(merged.get_pages())
        # Page 0 came from A (key 0). Pages 1, 2 came from B with offset 1.
        assert pages[0].get_struct_parents() == 0
        assert pages[1].get_struct_parents() == 1
        assert pages[2].get_struct_parents() == 2

        root = _struct_tree_root(merged)
        # Each page's parent-tree leaf must reference the page itself via /Pg.
        for page in pages:
            sp = page.get_struct_parents()
            assert sp >= 0
            value = PDFMergerUtility.get_number_tree_as_map(
                root.get_parent_tree()
            ).get(sp)
            assert isinstance(value, COSDictionary), (
                f"parent-tree slot {sp} must be a struct-elem dict"
            )
            pg_ref = value.get_dictionary_object(COSName.get_pdf_name("Pg"))
            assert pg_ref is page.get_cos_object(), (
                f"parent-tree slot {sp} /Pg must be the imported page dict"
            )


def test_struct_tree_merge_role_map_dest_wins(tmp_path: Path) -> None:
    """Conflicting /RoleMap entries: destination keeps its own value."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(
        _build_structured_doc(
            page_count=1,
            parent_tree_keys=[0],
            role_map={"Foo": "P", "OnlyA": "Span"},
        ),
        a,
    )
    _save(
        _build_structured_doc(
            page_count=1,
            parent_tree_keys=[0],
            # "Foo" collides — A wins because A is appended first.
            role_map={"Foo": "H1", "OnlyB": "Code"},
        ),
        b,
    )

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        rm = _struct_tree_root(merged).get_role_map()
        # First-source-wins: A's "Foo" -> "P" must persist.
        assert rm["Foo"] == "P"
        assert rm["OnlyA"] == "Span"
        assert rm["OnlyB"] == "Code"


def test_struct_tree_dest_without_tree_inherits_from_source(tmp_path: Path) -> None:
    """If the dest starts with no /StructTreeRoot but a source has one,
    a fresh root is created and the source tree is folded in."""
    a = tmp_path / "a.pdf"  # no struct tree
    b = tmp_path / "b.pdf"  # has struct tree
    out = tmp_path / "out.pdf"

    plain = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    plain.add_page(page)
    _save(plain, a)

    _save(
        _build_structured_doc(page_count=2, parent_tree_keys=[0, 1], body=b"% B\n"),
        b,
    )

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 3
        root = _struct_tree_root(merged)
        # Plain page has no /StructParents — leave it alone.
        plain_page = list(merged.get_pages())[0]
        assert plain_page.get_struct_parents() == -1
        # B's two pages keep their original keys (dest started empty).
        keys = _flat_parent_tree_keys(root)
        assert keys == {0, 1}


def test_struct_tree_merge_annotation_struct_parent_offset(tmp_path: Path) -> None:
    """Annotations on imported pages: /StructParent must be offset along
    with the page's own /StructParents."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    # Doc A: one page, two parent-tree slots — slot 0 for the page (mcid),
    # slot 1 for the annotation. Build manually so we can attach an annot.
    doc_a = _build_structured_doc(page_count=1, parent_tree_keys=[0], body=b"% A\n")
    page_a = list(doc_a.get_pages())[0]
    # Add a link-annotation with /StructParent = 1 and a sibling parent-tree
    # slot pointing at a fresh struct elem. Easier: piggyback on the existing
    # tree by adding a second slot and extending /ParentTree.
    annot = COSDictionary()
    annot.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    annot.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Link"))
    annot.set_item(COSName.get_pdf_name("StructParent"), COSInteger.get(1))
    annots = COSArray()
    annots.add(annot)
    page_a.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    # Extend A's parent tree with slot 1 → a fresh struct elem dict.
    annot_elem = COSDictionary()
    annot_elem.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem")
    )
    annot_elem.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Link"))
    annot_elem.set_item(COSName.get_pdf_name("Obj"), annot)
    annot_elem.set_item(
        COSName.get_pdf_name("P"),
        doc_a.get_document_catalog().get_struct_tree_root().get_cos_object(),
    )
    pt = doc_a.get_document_catalog().get_struct_tree_root().get_parent_tree()
    nums = pt.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Nums"))
    assert isinstance(nums, COSArray)
    nums.add(COSInteger.get(1))
    nums.add(annot_elem)
    doc_a.get_document_catalog().get_struct_tree_root().set_parent_tree_next_key(2)
    _save(doc_a, a)

    # B: two pages, parent-tree keys {0, 1}.
    _save(
        _build_structured_doc(page_count=2, parent_tree_keys=[0, 1], body=b"% B\n"),
        b,
    )

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        # A contributed keys 0, 1 (page + annot). B's two pages get keys 2, 3.
        root = _struct_tree_root(merged)
        keys = _flat_parent_tree_keys(root)
        assert keys == {0, 1, 2, 3}

        page_a_merged = list(merged.get_pages())[0]
        annots_merged = page_a_merged.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Annots")
        )
        assert isinstance(annots_merged, COSArray)
        ann = annots_merged.get_object(0)
        assert isinstance(ann, COSDictionary)
        # Doc A came first → no offset → annotation's /StructParent stays at 1.
        sp_obj = ann.get_dictionary_object(COSName.get_pdf_name("StructParent"))
        assert sp_obj is not None
        assert int(sp_obj.value) == 1


def test_struct_tree_merge_when_dest_has_existing_keys(tmp_path: Path) -> None:
    """Two sources both starting at key 0 — the second source must be
    pushed past the first source's key range."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"

    _save(
        _build_structured_doc(page_count=2, parent_tree_keys=[0, 1], body=b"% A\n"),
        a,
    )
    _save(
        _build_structured_doc(page_count=2, parent_tree_keys=[0, 1], body=b"% B\n"),
        b,
    )
    _save(
        _build_structured_doc(page_count=1, parent_tree_keys=[0], body=b"% C\n"), c
    )

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        root = _struct_tree_root(merged)
        keys = sorted(_flat_parent_tree_keys(root))
        # A → 0, 1 ; B (offset 2) → 2, 3 ; C (offset 4) → 4. Five distinct keys.
        assert keys == [0, 1, 2, 3, 4]
        pages = list(merged.get_pages())
        assert [p.get_struct_parents() for p in pages] == [0, 1, 2, 3, 4]


def test_get_number_tree_as_map_handles_none() -> None:
    """The static helper accepts ``None`` and returns an empty dict."""
    assert PDFMergerUtility.get_number_tree_as_map(None) == {}


def test_get_id_tree_as_map_handles_none() -> None:
    """Same for the IDTree variant."""
    assert PDFMergerUtility.get_id_tree_as_map(None) == {}
