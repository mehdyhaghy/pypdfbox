"""Wave 1370 — PDFMergerUtility round-out (agent E).

Covers append-time invariants that are easy to assert structurally:

- Page-order preservation across a multi-source append (no swap, no
  duplicate, no dropped page).
- ``/Names`` *name-tree* merge: when both sources expose a non-trivial
  ``/Names /Dests`` name tree, the merged catalog contains the union of
  both source keys.
- ``/AcroForm`` legacy mode renames a same-named field to
  ``dummyFieldName<N>`` rather than dropping it.
- ``/AcroForm`` legacy mode bumps ``N`` past any pre-existing
  ``dummyFieldName<K>`` in the destination so consecutive merges never
  collide.
- ``/AcroForm`` join-fields mode keeps the original name on both copies
  (concatenation, no rename).
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

_NAMES = COSName.get_pdf_name("Names")
_DESTS = COSName.get_pdf_name("Dests")
_FIELDS = COSName.get_pdf_name("Fields")
_T = COSName.get_pdf_name("T")
_FT = COSName.get_pdf_name("FT")


def _seed_page(page: PDPage, marker: bytes) -> None:
    s = COSStream()
    s.set_raw_data(marker)
    page.set_contents(s)


def _build_doc_with_markers(markers: list[bytes]) -> PDDocument:
    doc = PDDocument()
    for marker in markers:
        page = PDPage()
        _seed_page(page, marker)
        doc.add_page(page)
    return doc


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def _page_marker(page: PDPage) -> bytes:
    contents = page.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Contents")
    )
    if isinstance(contents, COSStream):
        return contents.get_raw_data() or b""
    if isinstance(contents, COSArray) and contents.size() > 0:
        first = contents.get_object(0)
        if isinstance(first, COSStream):
            return first.get_raw_data() or b""
    return b""


# ---------- page-order preservation ----------


def test_three_source_merge_preserves_page_order(tmp_path: Path) -> None:
    """Pages appear in destination in source-add order; no reorder."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_doc_with_markers([b"% A1\n", b"% A2\n"]), a)
    _save(_build_doc_with_markers([b"% B1\n"]), b)
    _save(_build_doc_with_markers([b"% C1\n", b"% C2\n", b"% C3\n"]), c)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 6
        markers = [_page_marker(p) for p in merged.get_pages()]
        # Markers appear in the order pages were added across sources.
        assert markers == [
            b"% A1\n",
            b"% A2\n",
            b"% B1\n",
            b"% C1\n",
            b"% C2\n",
            b"% C3\n",
        ]


def test_single_source_appended_twice_doubles_page_count(tmp_path: Path) -> None:
    """Appending the same file twice produces 2N pages — verifies the
    merger doesn't deduplicate pages by content/identity."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save(_build_doc_with_markers([b"% 1\n", b"% 2\n"]), a)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 4


# ---------- /Names name-tree merge ----------


def _build_doc_with_name_tree(
    names_dict_entries: list[tuple[str, COSArray]],
) -> PDDocument:
    """Build a doc with a /Names /Dests tree whose root has /Names = [k1,v1,k2,v2,...]."""
    doc = PDDocument()
    doc.add_page(PDPage())
    catalog_dict = doc.get_document_catalog().get_cos_object()
    names_root = COSDictionary()
    dests_root = COSDictionary()
    nums = COSArray()
    for key, value in names_dict_entries:
        nums.add(COSName.get_pdf_name(key))  # leaf key strings encoded as names
        nums.add(value)
    dests_root.set_item(COSName.get_pdf_name("Names"), nums)
    names_root.set_item(_DESTS, dests_root)
    catalog_dict.set_item(_NAMES, names_root)
    return doc


def test_names_tree_merge_union_of_both_sources(tmp_path: Path) -> None:
    """/Names /Dests name-tree gets the union of source keys merged in."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    arr_a = COSArray()
    arr_a.add(COSName.get_pdf_name("Fit"))
    src_a_entries = [("DestA1", arr_a)]

    arr_b = COSArray()
    arr_b.add(COSName.get_pdf_name("Fit"))
    src_b_entries = [("DestB1", arr_b)]

    _save(_build_doc_with_name_tree(src_a_entries), a)
    _save(_build_doc_with_name_tree(src_b_entries), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        names_dict = merged.get_document_catalog().get_cos_object().get_dictionary_object(_NAMES)
        assert isinstance(names_dict, COSDictionary)
        dests_root = names_dict.get_dictionary_object(_DESTS)
        assert isinstance(dests_root, COSDictionary)
        leaf_names = dests_root.get_dictionary_object(COSName.get_pdf_name("Names"))
        assert isinstance(leaf_names, COSArray)
        # Collect leaf-key names (every-other slot).
        collected = []
        for i in range(0, leaf_names.size(), 2):
            entry = leaf_names.get_object(i)
            if isinstance(entry, COSName):
                collected.append(entry.get_name())
        assert "DestA1" in collected
        assert "DestB1" in collected


# ---------- /AcroForm legacy mode ----------


def _build_acroform_doc(field_names: list[str]) -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage())
    form = PDAcroForm(doc)
    fields = COSArray()
    for name in field_names:
        field = COSDictionary()
        field.set_item(_FT, COSName.get_pdf_name("Tx"))
        field.set_string(_T, name)
        fields.add(field)
    form.get_cos_object().set_item(_FIELDS, fields)
    doc.get_document_catalog().set_acro_form(form)
    return doc


def test_acroform_legacy_mode_renames_dup_to_dummy(tmp_path: Path) -> None:
    """Both sources have field 'name' — legacy mode keeps the destination's
    original and renames the source one to ``dummyFieldName1``."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_acroform_doc(["name"]), a)
    _save(_build_acroform_doc(["name"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        partials = sorted(f.get_partial_name() or "" for f in form.get_fields())
        # Original kept, duplicate renamed.
        assert "name" in partials
        renamed = [p for p in partials if p.startswith("dummyFieldName")]
        assert len(renamed) >= 1


def test_acroform_legacy_mode_skips_next_num_past_existing_dummy(
    tmp_path: Path,
) -> None:
    """If destination already has ``dummyFieldName7``, the next rename must
    use 8+ to avoid collision."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    # First source already has dummyFieldName7 baked in.
    _save(_build_acroform_doc(["name", "dummyFieldName7"]), a)
    _save(_build_acroform_doc(["name"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        partials = [f.get_partial_name() or "" for f in form.get_fields()]
        # No two fields share the same partial name.
        assert len(partials) == len(set(partials))
        # And dummyFieldName7 still exists (wasn't overwritten).
        assert "dummyFieldName7" in partials


def test_acroform_join_fields_mode_renames_duplicate_like_legacy(
    tmp_path: Path,
) -> None:
    """JOIN_FORM_FIELDS_MODE delegates to legacy mode in PDFBox 3.0.x, so a
    destination field-name collision is renamed to ``dummyFieldName1`` —
    exactly as legacy mode does (oracle-confirmed via MergeFormFieldsModeProbe:
    both modes emit ``dummyFieldName1`` + ``name``). It does NOT keep two
    fields both named ``name``."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_acroform_doc(["name"]), a)
    _save(_build_acroform_doc(["name"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        names = sorted(f.get_partial_name() for f in form.get_fields())
        # Original kept; collision renamed to dummyFieldName1 (not a 2nd "name").
        assert names == ["dummyFieldName1", "name"]
        assert names.count("name") == 1


def test_acroform_first_source_only_carries_acroform_unchanged(
    tmp_path: Path,
) -> None:
    """When only first source has an /AcroForm, the merged form must
    contain exactly the original fields with no renames/duplicates."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    _save(_build_acroform_doc(["alpha", "beta"]), a)
    # b has no /AcroForm at all.
    bdoc = PDDocument()
    bdoc.add_page(PDPage())
    _save(bdoc, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        names = sorted(f.get_partial_name() or "" for f in form.get_fields())
        assert names == ["alpha", "beta"]


def test_acroform_second_source_only_becomes_destination_form(
    tmp_path: Path,
) -> None:
    """When only the *second* source has an /AcroForm, the merge clones
    it onto the destination — no fields lost."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    adoc = PDDocument()
    adoc.add_page(PDPage())
    _save(adoc, a)
    _save(_build_acroform_doc(["gamma"]), b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        assert form is not None
        names = [f.get_partial_name() for f in form.get_fields()]
        assert names == ["gamma"]
