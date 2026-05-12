"""Edge-case tests for ``PDFMergerUtility``'s structure-tree merge.

Complements ``test_pdf_merger_utility_struct_tree.py`` (the broader
"happy-path" matrix) with the round-out cases called out in the
PDFBox-port roadmap:

- RoleMap conflict resolution: same key, different mappings → warn +
  destination wins (upstream's ``mergeRoleMap`` policy).
- MCID-indexed parent-tree leaves: per-page MCID arrays survive cloning
  and end up keyed under the offset slot in the destination.
- /Pg rewriting on cloned struct-elem dicts (so cloned tree references
  the destination page, not the source page).
- ``set_destination_document_information`` and ``set_destination_metadata``
  override values that would otherwise be carried in from the first
  source's /Info / /Metadata.
- ``set_acro_form_merge_mode(JOIN_FORM_FIELDS_MODE | PDFBOX_LEGACY_MODE)``
  smoke test — the chosen mode must be the one exercised at merge time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDMetadata
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm

# ---------- helpers ----------


def _seed_page_contents(page: PDPage, body: bytes = b"q Q\n") -> None:
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _make_struct_elem(
    *,
    s_type: str,
    parent: COSDictionary,
    page: COSDictionary | None = None,
    k: COSArray | COSDictionary | int | None = None,
) -> COSDictionary:
    elem = COSDictionary()
    elem.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    elem.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name(s_type))
    elem.set_item(COSName.get_pdf_name("P"), parent)
    if page is not None:
        elem.set_item(COSName.get_pdf_name("Pg"), page)
    if k is not None:
        if isinstance(k, int):
            elem.set_item(COSName.get_pdf_name("K"), COSInteger.get(k))
        else:
            elem.set_item(COSName.get_pdf_name("K"), k)
    return elem


def _build_minimal_struct_doc(
    *,
    body: bytes = b"q Q\n",
    role_map: dict[str, str] | None = None,
    parent_tree_key: int = 0,
    extra_role_map_dict: COSDictionary | None = None,
) -> PDDocument:
    """One-page tagged PDF with a single P-typed struct elem."""
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page, body)
    doc.add_page(page)

    page.get_cos_object().set_item(
        COSName.get_pdf_name("StructParents"), COSInteger.get(parent_tree_key)
    )

    root = PDStructureTreeRoot()
    doc_dict = _make_struct_elem(
        s_type="Document",
        parent=root.get_cos_object(),
        k=COSArray(),
    )
    para = _make_struct_elem(
        s_type="P",
        parent=doc_dict,
        page=page.get_cos_object(),
        k=0,  # MCID 0
    )
    doc_dict.get_dictionary_object(COSName.get_pdf_name("K")).add(para)
    root.get_cos_object().set_item(COSName.get_pdf_name("K"), doc_dict)

    parent_tree = PDStructureElementNumberTreeNode()
    parent_tree.set_numbers({parent_tree_key: PDStructureElement(para)})
    root.set_parent_tree(parent_tree)
    root.set_parent_tree_next_key(parent_tree_key + 1)

    if role_map is not None:
        root.set_role_map(role_map)
    if extra_role_map_dict is not None:
        root.get_cos_object().set_item(
            COSName.get_pdf_name("RoleMap"), extra_role_map_dict
        )

    doc.get_document_catalog().set_struct_tree_root(root)
    return doc


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


# ---------- /RoleMap conflict ----------


def test_role_map_conflict_dest_wins_with_warning(
    tmp_path: Path, caplog
) -> None:
    """Same key, different mapping → destination keeps its mapping; a
    warning is logged. Mirrors upstream ``mergeRoleMap``."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_minimal_struct_doc(role_map={"Hdr": "P", "OnlyA": "Span"}), a)
    _save(
        # "Hdr" maps to a *different* standard type — must not overwrite A's.
        _build_minimal_struct_doc(role_map={"Hdr": "H1", "OnlyB": "Code"}),
        b,
    )

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        rm = merged.get_document_catalog().get_struct_tree_root().get_role_map()
        # Destination (= A, which arrived first) wins on the conflict.
        assert rm["Hdr"] == "P"
        # Non-conflicting entries from both sources land in the merged map.
        assert rm["OnlyA"] == "Span"
        assert rm["OnlyB"] == "Code"
    assert any(
        "RoleMap" in rec.getMessage() and "Hdr" in rec.getMessage()
        for rec in caplog.records
    ), "expected a 'RoleMap' conflict warning mentioning the conflicting key"


def test_role_map_identical_value_is_silent(tmp_path: Path, caplog) -> None:
    """Same key + same mapping → no warning, no churn."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_minimal_struct_doc(role_map={"Hdr": "P"}), a)
    _save(_build_minimal_struct_doc(role_map={"Hdr": "P"}), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()
    assert not any("RoleMap" in rec.getMessage() for rec in caplog.records)


# ---------- MCID-indexed parent-tree leaves ----------


def test_mcid_indexed_parent_tree_leaf_offset_into_dest(tmp_path: Path) -> None:
    """A page-typed parent-tree leaf is a COSArray indexed by MCID. After
    merge, the array must land under the offset key with /Pg references on
    each child rewritten to point at the *destination* page."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    # Doc A: one page; parent-tree leaf at key 0 is a COSArray of 2 struct
    # elements (one per MCID slot).
    doc_a = PDDocument()
    page_a = PDPage()
    _seed_page_contents(page_a, b"% A\n")
    doc_a.add_page(page_a)
    page_a.get_cos_object().set_item(
        COSName.get_pdf_name("StructParents"), COSInteger.get(0)
    )
    root_a = PDStructureTreeRoot()
    doc_dict_a = _make_struct_elem(
        s_type="Document", parent=root_a.get_cos_object(), k=COSArray()
    )
    e0 = _make_struct_elem(
        s_type="P", parent=doc_dict_a, page=page_a.get_cos_object(), k=0
    )
    e1 = _make_struct_elem(
        s_type="P", parent=doc_dict_a, page=page_a.get_cos_object(), k=1
    )
    kids_a = doc_dict_a.get_dictionary_object(COSName.get_pdf_name("K"))
    kids_a.add(e0)
    kids_a.add(e1)
    root_a.get_cos_object().set_item(COSName.get_pdf_name("K"), doc_dict_a)
    mcid_array = COSArray()
    mcid_array.add(e0)
    mcid_array.add(e1)
    pt_a = PDStructureElementNumberTreeNode()
    nums_a = COSArray()
    nums_a.add(COSInteger.get(0))
    nums_a.add(mcid_array)
    pt_a.get_cos_object().set_item(COSName.get_pdf_name("Nums"), nums_a)
    root_a.set_parent_tree(pt_a)
    root_a.set_parent_tree_next_key(1)
    doc_a.get_document_catalog().set_struct_tree_root(root_a)
    _save(doc_a, a)

    # Doc B: ordinary one-page tagged PDF (parent-tree key 0).
    _save(_build_minimal_struct_doc(body=b"% B\n", parent_tree_key=0), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        pages = list(merged.get_pages())
        assert len(pages) == 2
        root = merged.get_document_catalog().get_struct_tree_root()
        flat = PDFMergerUtility.get_number_tree_as_map(root.get_parent_tree())
        # A's leaf stays at 0; B is offset by 1.
        assert set(flat) == {0, 1}
        leaf_a = flat[0]
        assert isinstance(leaf_a, COSArray)
        # Each child's /Pg references must point at the *destination* page.
        dest_page_a = pages[0].get_cos_object()
        for i in range(leaf_a.size()):
            child = leaf_a.get_object(i)
            assert isinstance(child, COSDictionary)
            assert (
                child.get_dictionary_object(COSName.get_pdf_name("Pg"))
                is dest_page_a
            )


# ---------- /Pg rewriting ----------


def test_struct_elem_pg_rewritten_to_dest_page(tmp_path: Path) -> None:
    """Each struct elem's /Pg must point at the destination page, not the
    source page (which is closed after merge)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_minimal_struct_doc(body=b"% A\n"), a)
    _save(_build_minimal_struct_doc(body=b"% B\n"), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        pages = list(merged.get_pages())
        root = merged.get_document_catalog().get_struct_tree_root()
        flat = PDFMergerUtility.get_number_tree_as_map(root.get_parent_tree())
        assert set(flat) == {0, 1}
        # Slot 0 → page 0; slot 1 → page 1 (B was offset).
        for slot, page in zip([0, 1], pages, strict=True):
            entry = flat[slot]
            assert isinstance(entry, COSDictionary)
            pg = entry.get_dictionary_object(COSName.get_pdf_name("Pg"))
            assert pg is page.get_cos_object()


# ---------- destination /Info + /Metadata overrides ----------


def test_set_destination_document_information_overrides_source(
    tmp_path: Path,
) -> None:
    """``set_destination_document_information`` wins over /Info carried in
    from sources."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    src_a = _build_minimal_struct_doc(body=b"% A\n")
    src_a.get_document_information().set_title("source-A-title")
    _save(src_a, a)
    _save(_build_minimal_struct_doc(body=b"% B\n"), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))

    # Build an override info object.
    override_doc = PDDocument()
    override_info = override_doc.get_document_information()
    override_info.set_title("override-title")
    override_info.set_author("override-author")
    util.set_destination_document_information(override_info)
    util.merge_documents()
    override_doc.close()

    with PDDocument.load(str(out)) as merged:
        info = merged.get_document_information()
        assert info.get_title() == "override-title"
        assert info.get_author() == "override-author"


def test_set_destination_metadata_overrides_source(tmp_path: Path) -> None:
    """``set_destination_metadata`` wins over /Metadata carried from the
    first source."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"

    src_a = _build_minimal_struct_doc(body=b"% A\n")
    src_md = COSStream()
    src_md.set_raw_data(b"<x:xmpmeta>source</x:xmpmeta>")
    src_a.get_document_catalog().set_metadata(PDMetadata(src_md))
    _save(src_a, a)

    override_md = COSStream()
    override_md.set_raw_data(b"<x:xmpmeta>override</x:xmpmeta>")

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.set_destination_metadata(PDMetadata(override_md))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        md = merged.get_document_catalog().get_metadata()
        assert md is not None
        body = md.get_cos_object().to_byte_array()
        assert b"override" in body
        assert b"source" not in body


# ---------- AcroForm merge mode ----------


def _build_acroform_doc(field_name: str) -> PDDocument:
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    doc.add_page(page)
    form = PDAcroForm(doc)
    field_dict = COSDictionary()
    field_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
    field_dict.set_string(COSName.get_pdf_name("T"), field_name)
    fields = COSArray()
    fields.add(field_dict)
    form.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)
    doc.get_document_catalog().set_acro_form(form)
    return doc


def test_acro_form_merge_mode_is_honoured_at_merge_time(tmp_path: Path) -> None:
    """Setting the AcroForm merge mode picks which strategy runs.

    PDFBOX_LEGACY_MODE: same-named source field gets a ``dummyFieldNameN``
    rename. JOIN_FORM_FIELDS_MODE: source field is appended verbatim, so
    *both* fields with the original name end up in the dest /Fields array.
    """
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"

    _save(_build_acroform_doc("name"), a)
    _save(_build_acroform_doc("name"), b)

    # PDFBOX_LEGACY_MODE.
    out_legacy = tmp_path / "out_legacy.pdf"
    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out_legacy))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()
    with PDDocument.load(str(out_legacy)) as merged:
        names = sorted(
            f.get_partial_name() for f in merged.get_document_catalog().get_acro_form().get_fields()
        )
        assert "name" in names
        assert any(n.startswith("dummyFieldName") for n in names if n != "name")

    # JOIN_FORM_FIELDS_MODE.
    out_join = tmp_path / "out_join.pdf"
    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out_join))
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    util.merge_documents()
    with PDDocument.load(str(out_join)) as merged:
        names = [
            f.get_partial_name() for f in merged.get_document_catalog().get_acro_form().get_fields()
        ]
        # Join-fields mode: append verbatim, so both fields keep "name".
        assert names.count("name") == 2


def test_document_merge_mode_optimize_does_not_log_fallback(
    tmp_path: Path, caplog
) -> None:
    """OPTIMIZE_RESOURCES_MODE now performs a real cross-document
    resource-deduplicating merge; the legacy-fallback info log must not
    fire for valid input."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_minimal_struct_doc(body=b"% A\n"), a)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    with caplog.at_level(logging.INFO, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()
    assert not any(
        "falling back" in rec.getMessage() for rec in caplog.records
    )
    assert out.exists() and out.stat().st_size > 0


# ---------- IDTree collision ----------


def test_id_tree_collision_dest_wins_with_warning(
    tmp_path: Path, caplog
) -> None:
    """Same /ID in both source IDTrees → destination keeps its element,
    source dropped, one warning emitted."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    def _doc_with_id(
        id_value: str, struct_type: str, *, body: bytes
    ) -> PDDocument:
        doc = _build_minimal_struct_doc(body=body)
        root = doc.get_document_catalog().get_struct_tree_root()
        # Reach into the K array and tag the only child with /ID + /S override.
        doc_dict = root.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("K")
        )
        kids = doc_dict.get_dictionary_object(COSName.get_pdf_name("K"))
        target = kids.get_object(0)
        target.set_string(COSName.get_pdf_name("ID"), id_value)
        target.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name(struct_type))
        # Build /IDTree with that one element.
        id_tree = COSDictionary()
        names_arr = COSArray()
        names_arr.add(COSString(id_value))
        names_arr.add(target)
        id_tree.set_item(COSName.get_pdf_name("Names"), names_arr)
        root.get_cos_object().set_item(COSName.get_pdf_name("IDTree"), id_tree)
        return doc

    _save(_doc_with_id("the-id", "P", body=b"% A\n"), a)
    _save(_doc_with_id("the-id", "H1", body=b"% B\n"), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        root = merged.get_document_catalog().get_struct_tree_root()
        id_tree = root.get_id_tree()
        assert id_tree is not None
        elem = id_tree.get_value("the-id")
        assert elem is not None
        # A arrived first → /S = "P" (from A) survives.
        assert elem.get_structure_type() == "P"
    assert any(
        "IDTree" in rec.getMessage() and "the-id" in rec.getMessage()
        for rec in caplog.records
    )
