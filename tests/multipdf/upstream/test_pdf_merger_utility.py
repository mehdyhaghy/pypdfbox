"""Ported subset of upstream ``PDFMergerUtilityTest``.

The upstream test file is large (~1500 LOC) and overwhelmingly leans on
fixture PDFs from ``pdfbox/src/test/resources/input`` plus rendering-
based comparisons that exercise the full text/rendering stack — both
deferred in pypdfbox.

What we port here is the structural / contract surface that does NOT
depend on those:

- file-deletion-after-merge contract (testFileDeletion)
- enum equality / default-mode contracts (no upstream method, but
  exercises the same getter/setter that upstream tests touch in setUp)

Skipped (with one-line marks): every upstream test that opens a fixture
under ``input/PDFA_check.pdf`` / ``input/152074.pdf`` / ``input/PDFBOX-*``
or that requires structure-tree merging, JPEG / CCITT image streams,
PDFRenderer comparisons, or the FDF module — none of those are wired in
pypdfbox yet. See ``CHANGES.md`` for the divergence list.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"


def _seed_page(page: PDPage) -> None:
    s = COSStream()
    s.set_raw_data(b"q Q\n")
    page.set_contents(s)


def _build_doc(num_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage()
        _seed_page(page)
        doc.add_page(page)
    return doc


def test_file_deletion(tmp_path: Path) -> None:
    """Ported from ``testFileDeletion`` — sources must be releasable after
    the merge completes."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    src_a = _build_doc(1)
    src_a.save(a)
    src_a.close()
    src_b = _build_doc(1)
    src_b.save(b)
    src_b.close()

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    # Sources must be closed by the utility — file is removable on Windows
    # too. We probe with os.remove to reproduce upstream's `Files.delete`.
    os.remove(a)
    os.remove(b)
    assert not a.exists()
    assert not b.exists()
    assert out.exists()


def test_default_document_merge_mode_is_legacy() -> None:
    """Ports the implicit default-mode contract exercised by upstream's
    `mergerUtility` field initialisation across many tests."""
    util = PDFMergerUtility()
    assert util.get_document_merge_mode() == DocumentMergeMode.PDFBOX_LEGACY_MODE


def test_default_acroform_merge_mode_is_legacy() -> None:
    util = PDFMergerUtility()
    assert util.get_acro_form_merge_mode() == AcroFormMergeMode.PDFBOX_LEGACY_MODE


def test_setters_round_trip_modes() -> None:
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    assert (
        util.get_document_merge_mode() == DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    )
    assert (
        util.get_acro_form_merge_mode()
        == AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    )


# ---------- skipped upstream tests (one-line stubs) ----------


@pytest.mark.skip(
    reason="needs upstream input/PDFA_check.pdf binary fixture (not bundled) and "
    "pixel-exact PDFRenderer parity against a Java-rendered model — "
    "byte-exact raster output across rasterisers is unachievable"
)
def test_pdf_merger_utility() -> None: ...


@pytest.mark.skip(
    reason="needs upstream input/152074.pdf compressed-resource fixture (not bundled) "
    "and pixel-exact PDFRenderer parity against a Java-rendered model"
)
def test_pdf_merger_utility_2() -> None: ...


@pytest.mark.skip(
    reason="needs upstream JPEG/CCITT image-stream fixtures and pixel-exact "
    "PDFRenderer parity against a Java-rendered model"
)
def test_jpeg_ccitt() -> None: ...


@pytest.mark.skip(reason="OpenAction destination uses upstream fixture")
def test_pdf_merger_open_action() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py and "
    "test_pdf_merger_utility_struct_tree.py"
)
def test_structure_tree_merge() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py"
)
def test_structure_tree_merge_2() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py"
)
def test_structure_tree_merge_3() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py"
)
def test_structure_tree_merge_4() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py"
)
def test_structure_tree_merge_5() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py"
)
def test_structure_tree_merge_6() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — covered synthetically by "
    "tests/multipdf/test_merger_struct_tree.py"
)
def test_structure_tree_merge_7() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — synthetic equivalent in "
    "tests/multipdf/test_pdf_merger_utility_struct_tree.py "
    "(test_struct_tree_merge_keys_offset_into_dest_range)"
)
def test_missing_parent_tree_next_key() -> None: ...


@pytest.mark.skip(
    reason="upstream input/PDFA-1b.pdf fixture — synthetic equivalent in "
    "tests/multipdf/test_merger_struct_tree.py "
    "(test_id_tree_collision_dest_wins_with_warning)"
)
def test_structure_tree_merge_id_tree() -> None: ...


def test_merge_bogus_struct_parents_1(tmp_path: Path) -> None:
    """Synthetic equivalent of upstream ``testMergeBogusStructParents1``
    (PDFBOX-4429).

    Upstream loads ``PDFBOX-4408.pdf`` twice, then on the *destination*:

    * nulls out ``/StructTreeRoot``;
    * sets ``/StructParents`` on page 0 to ``9999`` (off-tree);
    * sets ``/StructParent`` on the first annotation of page 0 to ``9998``.

    It then calls ``appendDocument(dst, src)`` and verifies the merge
    completes without crashing. We reproduce the same shape using a
    synthetic tagged source PDF (``_build_struct_doc_for_5198``) plus a
    synthetic destination that carries the *bogus* off-tree
    ``/StructParents`` markers — and assert the merger:

    * does NOT raise;
    * bootstraps a fresh ``/StructTreeRoot`` on the destination;
    * strips the bogus ``/StructParents``/``/StructParent`` entries from
      pre-existing destination pages so they don't dangle off-tree
      (lines 1460-1474 in ``pdf_merger_utility.py`` — the PDFBOX-4429
      defence);
    * produces a destination whose ``/ParentTree`` has a non-negative
      ``ParentTreeNextKey`` and whose ``/K`` is non-null
      (the upstream ``checkWithNumberTree`` / ``checkForPageOrphans``
      surface).
    """
    from pypdfbox.cos import COSArray, COSDictionary, COSName
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
        PDAnnotationText,
    )

    src_path = tmp_path / "src.pdf"
    dst_path = tmp_path / "dst.pdf"
    out_path = tmp_path / "out.pdf"

    # Source: a real tagged single-page document.
    src_doc = _build_struct_doc_for_5198(1)
    src_doc.save(str(src_path))
    src_doc.close()

    # Destination: a tagged document, then we strip its struct tree and
    # poison its page + annotation with off-tree /StructParents values.
    dst_doc = _build_struct_doc_for_5198(1)
    dst_doc.get_document_catalog().set_structure_tree_root(None)
    dst_page = dst_doc.get_page(0)
    dst_page.set_struct_parents(9999)
    # Add a single annotation carrying a bogus /StructParent — mirrors
    # ``dst.getPage(0).getAnnotations().get(0).setStructParent(9998)``.
    annot = PDAnnotationText()
    annot.set_struct_parent(9998)
    annots = COSArray()
    annots.add(annot.get_cos_object())
    dst_page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    dst_doc.save(str(dst_path))
    dst_doc.close()

    with (
        PDDocument.load(str(src_path)) as src,
        PDDocument.load(str(dst_path)) as dst,
    ):
        # Sanity: before merge, dst has the bogus values + no struct tree.
        assert dst.get_document_catalog().get_struct_tree_root() is None
        assert dst.get_page(0).get_struct_parents() == 9999

        util = PDFMergerUtility()
        # Must not raise — this is the PDFBOX-4429 regression guard.
        util.append_document(dst, src)

        # After merge: dst gained a bootstrapped struct tree from src.
        merged_root = dst.get_document_catalog().get_struct_tree_root()
        assert merged_root is not None
        # Bogus /StructParents on the pre-existing dst page must have
        # been stripped (so it no longer points off-tree).
        assert dst.get_page(0).get_struct_parents() == -1
        # And the bogus /StructParent on the dst annotation too.
        merged_annots = dst.get_page(0).get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Annots")
        )
        assert isinstance(merged_annots, COSArray)
        for i in range(merged_annots.size()):
            entry = merged_annots.get_object(i)
            assert isinstance(entry, COSDictionary)
            sp = entry.get_dictionary_object(COSName.get_pdf_name("StructParent"))
            assert sp is None, "bogus /StructParent should have been stripped"
        # /ParentTree must be well-formed and /K must be present.
        assert merged_root.get_parent_tree_next_key() != -1
        assert merged_root.get_k() is not None
        # /ParentTree exists and is the typed wrapper.
        assert merged_root.get_parent_tree() is not None

        # Sanity-check: total page count = dst (1) + src (1) = 2.
        assert dst.get_number_of_pages() == 2
        # And the round-trip survives a save+reload (no dangling refs).
        dst.save(str(out_path))

    with PDDocument.load(str(out_path)) as reloaded:
        assert reloaded.get_number_of_pages() == 2
        rt_root = reloaded.get_document_catalog().get_struct_tree_root()
        assert rt_root is not None
        assert rt_root.get_parent_tree_next_key() != -1


def test_merge_bogus_struct_parents_2(tmp_path: Path) -> None:
    """Synthetic equivalent of upstream ``testMergeBogusStructParents2``
    (PDFBOX-4429, mirror of variant 1).

    Variant 2 puts the bogus ``/StructParents``/``/StructParent`` values
    on the *source* side and nulls out the *source*'s struct tree. The
    destination keeps its struct tree intact. The merger must still
    complete without crashing; because the source has no struct tree,
    the imported pages have ``/StructParents`` / ``/StructParent``
    stripped on clone (``merge_struct_tree == False`` path in
    ``pdf_merger_utility.py`` lines 983-985).
    """
    from pypdfbox.cos import COSArray, COSDictionary, COSName
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
        PDAnnotationText,
    )

    src_path = tmp_path / "src.pdf"
    dst_path = tmp_path / "dst.pdf"
    out_path = tmp_path / "out.pdf"

    # Destination: a real tagged single-page document.
    dst_doc = _build_struct_doc_for_5198(1)
    dst_doc.save(str(dst_path))
    dst_doc.close()

    # Source: tagged document with struct tree stripped + bogus /StructParents.
    src_doc = _build_struct_doc_for_5198(1)
    src_doc.get_document_catalog().set_structure_tree_root(None)
    src_page = src_doc.get_page(0)
    src_page.set_struct_parents(9999)
    annot = PDAnnotationText()
    annot.set_struct_parent(9998)
    annots = COSArray()
    annots.add(annot.get_cos_object())
    src_page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    src_doc.save(str(src_path))
    src_doc.close()

    with (
        PDDocument.load(str(src_path)) as src,
        PDDocument.load(str(dst_path)) as dst,
    ):
        # Sanity: before merge, src has bogus values + no struct tree.
        assert src.get_document_catalog().get_struct_tree_root() is None
        assert src.get_page(0).get_struct_parents() == 9999

        util = PDFMergerUtility()
        # Must not raise.
        util.append_document(dst, src)

        # After merge: dst's original struct tree is intact, and the
        # imported page no longer carries the bogus off-tree
        # /StructParents (it was stripped on the non-struct-tree path).
        merged_root = dst.get_document_catalog().get_struct_tree_root()
        assert merged_root is not None
        # /ParentTree well-formed, /K present.
        assert merged_root.get_parent_tree_next_key() != -1
        assert merged_root.get_k() is not None
        # The imported (formerly src) page is at index 1.
        imported_page = dst.get_page(1)
        # Bogus /StructParents must have been stripped on import.
        assert imported_page.get_struct_parents() == -1
        imp_annots = imported_page.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Annots")
        )
        assert isinstance(imp_annots, COSArray)
        for i in range(imp_annots.size()):
            entry = imp_annots.get_object(i)
            assert isinstance(entry, COSDictionary)
            sp = entry.get_dictionary_object(COSName.get_pdf_name("StructParent"))
            assert sp is None, "bogus /StructParent should have been stripped"

        assert dst.get_number_of_pages() == 2
        dst.save(str(out_path))

    with PDDocument.load(str(out_path)) as reloaded:
        assert reloaded.get_number_of_pages() == 2


def test_parent_tree(tmp_path) -> None:
    """Synthetic equivalent of upstream ``testParentTree``.

    Upstream loads ``PDFBOX-3999-GeneralForbearance.pdf`` (not shipped in
    pypdfbox) and asserts the page count of ``getNumberTreeAsMap`` matches
    ``getParentTreeNextKey``. We instead build a synthetic one-page
    tagged document, write a few ``/StructParents`` keys into the
    parent-tree's ``/Nums`` leaf, and confirm:

    * :meth:`PDStructureTreeRoot.get_parent_tree` returns a typed
      :class:`PDStructureElementNumberTreeNode`.
    * ``PDFMergerUtility.get_number_tree_as_map`` flattens it into the
      expected ``{key: value}`` mapping.
    * :meth:`PDStructureTreeRoot.get_parent_tree_next_key` returns the
      sentinel value (``len(map)`` for a dense allocator-style tree).
    """
    from pypdfbox.cos import (
        COSArray,
        COSDictionary,
        COSInteger,
        COSName,
    )
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
        PDStructureTreeRoot,
    )

    doc = _build_doc(1)
    root = PDStructureTreeRoot()
    doc_dict = COSDictionary()
    doc_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    doc_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Document"))
    doc_dict.set_item(COSName.get_pdf_name("P"), root.get_cos_object())
    root.get_cos_object().set_item(COSName.get_pdf_name("K"), doc_dict)

    # Build a /Nums leaf with three keys (0, 1, 2) each holding a
    # struct-element dictionary (the value type the parent-tree exposes
    # via PDParentTreeValue).
    parent_tree = PDStructureElementNumberTreeNode()
    nums = COSArray()
    for key in range(3):
        elem = COSDictionary()
        elem.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem")
        )
        elem.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("P"))
        elem.set_item(COSName.get_pdf_name("P"), doc_dict)
        nums.add(COSInteger.get(key))
        nums.add(elem)
    parent_tree.get_cos_object().set_item(COSName.get_pdf_name("Nums"), nums)
    root.set_parent_tree(parent_tree)
    root.set_parent_tree_next_key(3)
    doc.get_document_catalog().set_struct_tree_root(root)

    out = tmp_path / "out.pdf"
    doc.save(str(out))
    doc.close()

    with PDDocument.load(str(out)) as reloaded:
        struct_root = reloaded.get_document_catalog().get_struct_tree_root()
        pt = struct_root.get_parent_tree()
        assert pt is not None
        # Upstream assertion: getValue(0) succeeds (returns first leaf
        # entry as a typed PDStructureElement-backed COSObjectable).
        first = pt.get_value(0)
        assert first is not None
        flat = PDFMergerUtility.get_number_tree_as_map(pt)
        assert len(flat) == 3
        assert max(flat.keys()) + 1 == 3
        assert min(flat.keys()) == 0
        assert struct_root.get_parent_tree_next_key() == 3
        # Each leaf entry is reachable as a wrapped PDParentTreeValue
        # via get_parent_tree_value (the typed accessor).
        pv0 = struct_root.get_parent_tree_value(0)
        assert pv0 is not None


def _build_struct_doc_for_5198(num_pages: int = 1):
    """Build a tagged PDF with the PDF/UA-style /K shape PDFBOX-5198
    exercises: top-level /K is a single ``/Document`` whose own /K array
    is a list of per-page ``/Part`` dicts.
    """
    from pypdfbox.cos import (
        COSArray,
        COSDictionary,
        COSInteger,
        COSName,
    )
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )

    doc = _build_doc(num_pages)
    root = PDStructureTreeRoot()
    doc_dict = COSDictionary()
    doc_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    doc_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Document"))
    doc_dict.set_item(COSName.get_pdf_name("P"), root.get_cos_object())
    k_array = COSArray()
    pages = list(doc.get_pages())
    for i, page in enumerate(pages):
        page_cos = page.get_cos_object()
        page_cos.set_item(
            COSName.get_pdf_name("StructParents"), COSInteger.get(i)
        )
        part = COSDictionary()
        part.set_item(
            COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem")
        )
        part.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Part"))
        part.set_item(COSName.get_pdf_name("P"), doc_dict)
        part.set_item(COSName.get_pdf_name("Pg"), page_cos)
        part.set_item(COSName.get_pdf_name("K"), COSInteger.get(0))
        k_array.add(part)
    doc_dict.set_item(COSName.get_pdf_name("K"), k_array)
    root.get_cos_object().set_item(COSName.get_pdf_name("K"), doc_dict)

    # Minimal parent tree so the merger's offset logic has something to
    # work with.
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureElementNumberTreeNode,
    )

    parent_tree = PDStructureElementNumberTreeNode()
    nums = COSArray()
    for i in range(len(pages)):
        nums.add(COSInteger.get(i))
        part_for_page = k_array.get_object(i)
        nums.add(part_for_page)
    parent_tree.get_cos_object().set_item(COSName.get_pdf_name("Nums"), nums)
    root.set_parent_tree(parent_tree)
    root.set_parent_tree_next_key(len(pages))

    doc.get_document_catalog().set_struct_tree_root(root)
    return doc


def _check_pdf_box_5198_parts(merged_path: str) -> None:
    """Replicate upstream's ``checkParts``: the merged document's
    top-level /K must be a single ``/Document`` whose /K array contains
    one ``/Part`` dict per page, all pointing at the Document dict via /P.
    """
    from pypdfbox.cos import COSArray, COSDictionary, COSName

    with PDDocument.load(merged_path) as doc:
        struct_root = doc.get_document_catalog().get_struct_tree_root()
        top_k = struct_root.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("K")
        )
        # Upstream's checkParts assumes a single top-level Document dict.
        # The merger wraps multi-source merges under a fresh /Document
        # dict — when both sources already each have a /Document at /K,
        # the destination /K becomes either that fresh wrapper dict or
        # (depending on the dst /K shape) an array carrying a single
        # element pointing at it. Normalise: if /K is a singleton array
        # holding a /Document dict, peel the wrapper.
        if isinstance(top_k, COSArray) and top_k.size() == 1:
            inner = top_k.get_object(0)
            if isinstance(inner, COSDictionary) and inner.get_name(
                COSName.get_pdf_name("S")
            ) == "Document":
                top_k = inner
        assert isinstance(top_k, COSDictionary)
        assert top_k.get_name(COSName.get_pdf_name("S")) == "Document"
        assert (
            top_k.get_dictionary_object(COSName.get_pdf_name("P"))
            is struct_root.get_cos_object()
        )
        k_array = top_k.get_dictionary_object(COSName.get_pdf_name("K"))
        assert isinstance(k_array, COSArray)
        num_pages = doc.get_number_of_pages()
        assert k_array.size() == num_pages
        for i in range(k_array.size()):
            entry = k_array.get_object(i)
            assert isinstance(entry, COSDictionary)
            assert entry.get_name(COSName.get_pdf_name("S")) == "Part"
            assert (
                entry.get_dictionary_object(COSName.get_pdf_name("P"))
                is top_k
            )


def test_pdf_box_5198_2(tmp_path) -> None:
    """Synthetic equivalent of upstream ``testPDFBox5198_2``.

    Upstream merges two ``PDFA3A.pdf`` copies and asserts the merged
    /StructTreeRoot's /K is a single /Document whose /K array is one
    /Part dict per page. We reproduce the same merge with synthetic
    tagged PDFs and run the upstream ``checkParts`` shape check.
    """
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"

    src_a = _build_struct_doc_for_5198(1)
    src_a.save(str(a))
    src_a.close()
    src_b = _build_struct_doc_for_5198(1)
    src_b.save(str(b))
    src_b.close()

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    _check_pdf_box_5198_parts(str(out))


def test_pdf_box_5198_3(tmp_path) -> None:
    """Synthetic equivalent of upstream ``testPDFBox5198_3`` (three-way
    merge variant)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"

    for path in (a, b, c):
        src = _build_struct_doc_for_5198(1)
        src.save(str(path))
        src.close()

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    _check_pdf_box_5198_parts(str(out))


# --------------------------------------------------------------------------
# Splitter tests that upstream parks inside PDFMergerUtilityTest (1200..1530).
# Ported in Wave 1290 — fixtures bundled from upstream Apache 2.0 corpus at
# pdfbox/src/test/resources/input/merge/. Deep-orphan invariants
# (checkForPageOrphans / checkWithNumberTree in upstream) are covered by
# tests/multipdf/test_splitter_struct_tree.py on synthetic structures, so we
# port only the surface-visible page/annotation/destination assertions.
# --------------------------------------------------------------------------


def test_split_with_structure_tree() -> None:
    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-4417-001031.pdf")) as doc:
        splitter = Splitter()
        splitter.set_start_page(1)
        splitter.set_end_page(2)
        splitter.set_split_at_page(2)
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 2
            structure_tree_root = (
                dst_doc.get_document_catalog().get_structure_tree_root()
            )
            assert (
                len(
                    PDFMergerUtility.get_id_tree_as_map(
                        structure_tree_root.get_id_tree()
                    )
                )
                == 126
            )
            assert (
                len(
                    PDFMergerUtility.get_number_tree_as_map(
                        structure_tree_root.get_parent_tree()
                    )
                )
                == 2
            )
            assert len(structure_tree_root.get_role_map()) == 6


def test_split_with_structure_tree_and_destinations() -> None:
    # PDFBOX-5762: Splitter must rewrite cross-page link destinations.
    # The chunk keeps the first two pages, so only the first two of the
    # five link annotations should retarget to chunk-local pages; the
    # remaining three point at pages that didn't follow the split and
    # have their /D[0] nulled out.
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
        PDActionGoTo,
    )
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
        PDPageDestination,
    )

    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-5762-722238.pdf")) as doc:
        splitter = Splitter()
        splitter.set_start_page(1)
        splitter.set_end_page(2)
        splitter.set_split_at_page(2)
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 2
            # Status-quo structure-tree assertions — match upstream
            # ``testSplitWithStructureTreeAndDestinations``.
            structure_tree_root = (
                dst_doc.get_document_catalog().get_structure_tree_root()
            )
            assert (
                len(
                    PDFMergerUtility.get_number_tree_as_map(
                        structure_tree_root.get_parent_tree()
                    )
                )
                == 7
            )
            assert len(structure_tree_root.get_role_map()) == 4

            # Check that destinations are fixed — only the first two
            # point at pages in the chunk; the remaining three are nulled.
            annotations = dst_doc.get_page(0).get_annotations()
            assert len(annotations) == 5
            links = []
            for ann in annotations:
                assert isinstance(ann, PDAnnotationLink)
                links.append(ann)
            actions = [link.get_action() for link in links]
            for action in actions:
                assert isinstance(action, PDActionGoTo)
            destinations = [action.get_destination() for action in actions]
            for destination in destinations:
                assert isinstance(destination, PDPageDestination)
            page_tree = dst_doc.get_pages()
            assert page_tree.index_of(destinations[0].get_page()) == 0
            assert page_tree.index_of(destinations[1].get_page()) == 1
            assert destinations[2].get_page() is None
            assert destinations[3].get_page() is None
            assert destinations[4].get_page() is None


def test_split_with_structure_tree_and_destinations_and_removed_annotations() -> None:
    # PDFBOX-5929: when /Annots are cleared from the source pages first,
    # the splitter still produces a well-formed chunk with the expected
    # page count (deep orphan-check covered by test_splitter_struct_tree).
    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-5762-722238.pdf")) as doc:
        splitter = Splitter()
        for page in doc.get_pages():
            page.set_annotations([])
        splitter.set_start_page(1)
        splitter.set_end_page(2)
        splitter.set_split_at_page(2)
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 2


def test_single_page_split() -> None:
    # PDFBOX-5792 — destination outside target document used to NPE in the
    # next call of ``Splitter.fix_destinations``. We assert the same
    # invariants upstream's ``testSinglePageSplit`` asserts: every chunk
    # has one page, every link annotation's ``GoTo`` destination has its
    # page nulled out, and the per-chunk /ParentTree + /RoleMap sizes
    # match upstream's expected narrowing.
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
        PDActionGoTo,
    )
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
        PDPageDestination,
    )

    expected_pt_sizes = [6, 6, 6, 5, 1, 1]
    expected_role_map_sizes = [3, 3, 4, 4, 6, 7]

    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-5792-240045.pdf")) as doc:
        splitter = Splitter()
        splitter.set_split_at_page(1)
        split_result = splitter.split(doc)
        assert len(split_result) == 6
        for dst_doc in split_result:
            assert dst_doc.get_number_of_pages() == 1
            for ann in dst_doc.get_page(0).get_annotations():
                assert isinstance(ann, PDAnnotationLink)
                action = ann.get_action()
                assert isinstance(action, PDActionGoTo)
                destination = action.get_destination()
                assert isinstance(destination, PDPageDestination)
                assert destination.get_page() is None
        for index, dst_doc in enumerate(split_result):
            structure_tree_root = (
                dst_doc.get_document_catalog().get_structure_tree_root()
            )
            assert (
                len(
                    PDFMergerUtility.get_number_tree_as_map(
                        structure_tree_root.get_parent_tree()
                    )
                )
                == expected_pt_sizes[index]
            ), f"chunk {index} parent-tree size"
            assert (
                len(structure_tree_root.get_role_map())
                == expected_role_map_sizes[index]
            ), f"chunk {index} role-map size"
        for dst_doc in split_result:
            dst_doc.close()


def test_split_with_popup_annotations() -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
        PDAnnotationPopup,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
        PDAnnotationText,
    )

    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-5809-509329.pdf")) as doc:
        splitter = Splitter()
        splitter.set_start_page(3)
        splitter.set_end_page(3)
        splitter.set_split_at_page(1)
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 1
            annotations = dst_doc.get_page(0).get_annotations()
            assert len(annotations) == 5
            annotation_text3 = annotations[3]
            annotation_popup4 = annotations[4]
            assert isinstance(annotation_text3, PDAnnotationText)
            assert isinstance(annotation_popup4, PDAnnotationPopup)
            # Markup's /Popup → cloned popup dict; popup's /Parent →
            # cloned markup dict; markup's /P → cloned page dict.
            # Upstream uses default Object.equals (identity); our
            # PDAnnotation.__eq__ is identity-by-dict, so the comparison
            # against PDAnnotationPopup/PDAnnotationText wrappers reads
            # the same on both sides.
            assert annotation_text3.get_popup() == annotation_popup4
            assert annotation_popup4.get_parent_markup() == annotation_text3
            assert annotation_text3.get_page() is dst_doc.get_page(0).get_cos_object()
        # Source document is untouched — same identity invariants hold
        # against the original page.
        annotations = doc.get_page(2).get_annotations()
        assert len(annotations) == 5
        annotation_text3 = annotations[3]
        annotation_popup4 = annotations[4]
        assert isinstance(annotation_text3, PDAnnotationText)
        assert isinstance(annotation_popup4, PDAnnotationPopup)
        assert annotation_text3.get_popup() == annotation_popup4
        assert annotation_popup4.get_parent_markup() == annotation_text3
        assert annotation_text3.get_page() is doc.get_page(2).get_cos_object()


def test_split_with_broken_destination() -> None:
    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-5811-362972.pdf")) as doc:
        splitter = Splitter()
        splitter.set_start_page(2)
        splitter.set_end_page(2)
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 1
            annotations = dst_doc.get_page(0).get_annotations()
            assert len(annotations) == 1
            link = annotations[0]
            assert isinstance(link, PDAnnotationLink)
            assert link.get_destination() is None
        # The original (unmodified) link still has the broken /Dest and
        # raises (upstream raises IOException; we map to OSError per
        # CLAUDE.md exception mapping).
        annotations = doc.get_page(1).get_annotations()
        assert len(annotations) == 1
        link = annotations[0]
        assert isinstance(link, PDAnnotationLink)
        with pytest.raises(OSError):
            link.get_destination()


def test_split_with_named_destinations() -> None:
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
        PDActionGoTo,
    )
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (  # noqa: E501
        PDNamedDestination,
    )
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
        PDPageDestination,
    )

    with PDDocument.load(str(_FIXTURE_DIR / "PDFBOX-5840-410609.pdf")) as doc:
        splitter = Splitter()
        splitter.set_split_at_page(6)
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 6
            annotations = dst_doc.get_page(0).get_annotations()
            assert len(annotations) == 5
            link1 = annotations[0]
            link2 = annotations[1]
            link3 = annotations[2]
            link4 = annotations[3]
            link5 = annotations[4]
            assert isinstance(link1, PDAnnotationLink)
            assert isinstance(link2, PDAnnotationLink)
            assert isinstance(link3, PDAnnotationLink)
            assert isinstance(link4, PDAnnotationLink)
            assert isinstance(link5, PDAnnotationLink)
            action1 = link1.get_action()
            action2 = link2.get_action()
            action3 = link3.get_action()
            action4 = link4.get_action()
            action5 = link5.get_action()
            assert isinstance(action1, PDActionGoTo)
            assert isinstance(action2, PDActionGoTo)
            assert isinstance(action3, PDActionGoTo)
            assert isinstance(action4, PDActionGoTo)
            assert isinstance(action5, PDActionGoTo)
            pd1 = action1.get_destination()
            pd2 = action2.get_destination()
            pd3 = action3.get_destination()
            pd4 = action4.get_destination()
            pd5 = action5.get_destination()
            assert isinstance(pd1, PDPageDestination)
            assert isinstance(pd2, PDPageDestination)
            assert isinstance(pd3, PDPageDestination)
            assert isinstance(pd4, PDPageDestination)
            assert isinstance(pd5, PDPageDestination)
            page_tree = dst_doc.get_pages()
            assert page_tree.index_of(pd1.get_page()) == 0
            assert page_tree.index_of(pd2.get_page()) == 1
            assert page_tree.index_of(pd3.get_page()) == 3
            assert page_tree.index_of(pd4.get_page()) == 3
            assert page_tree.index_of(pd5.get_page()) == 5

            assert dst_doc.get_document_catalog().get_metadata() is not None

            import io

            baos = io.BytesIO()
            dst_doc.save(baos)
            with PDDocument.load(baos.getvalue()) as reloaded_doc:
                assert (
                    reloaded_doc.get_document_catalog().get_metadata()
                    is not None
                )

        # Check that source document is unchanged
        annotations = doc.get_page(0).get_annotations()
        assert len(annotations) == 5
        link = annotations[0]
        assert isinstance(link, PDAnnotationLink)
        src_action = link.get_action()
        assert isinstance(src_action, PDActionGoTo)
        # Upstream returns PDNamedDestination from PDActionGoTo.getDestination()
        # for ``/D`` of name/string form; our port surfaces the raw ``str``
        # (see test_pd_action_go_to_parity.test_get_destination_dispatches_*).
        # The contract that matters here — source document untouched, ``/D``
        # still a name reference — holds in either form.
        src_dest = src_action.get_destination()
        assert isinstance(src_dest, (PDNamedDestination, str))


@pytest.mark.skip(
    reason=(
        "PDFBOX-6009 fixture lives in upstream TARGETPDFDIR (network-fetched "
        "issue attachment), not in pdfbox/src/test/resources — not bundled"
    )
)
def test_split_with_pg_entry_at_the_top() -> None: ...


def test_split_with_orphan_popup_annotation() -> None:
    # PDFBOX-6018: Split a PDF with popup annotations that are NOT in the
    # annotation list. Verify that after splitting, they still link back
    # to their markup annotation and the markup to the page.
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
        PDAnnotationText,
    )

    with PDDocument.load(
        str(_FIXTURE_DIR / "PDFBOX-6018-099267-p9-OrphanPopups.pdf")
    ) as doc:
        splitter = Splitter()
        split_result = splitter.split(doc)
        assert len(split_result) == 1
        with split_result[0] as dst_doc:
            assert dst_doc.get_number_of_pages() == 1
            page = dst_doc.get_page(0)
            annotations = page.get_annotations()
            assert len(annotations) == 2
            ann0 = annotations[0]
            ann1 = annotations[1]
            assert isinstance(ann0, PDAnnotationText)
            assert isinstance(ann1, PDAnnotationText)
            # Markup /P points at the chunk's page; popup-clone /Parent
            # points back at the cloned markup (Splitter mirrors the
            # orphan-popup re-link from upstream processAnnotations).
            assert ann0.get_page() is page.get_cos_object()
            assert ann1.get_page() is page.get_cos_object()
            assert ann0.get_popup().get_parent_markup() == ann0
            assert ann1.get_popup().get_parent_markup() == ann1


def test_outlines_self_parent(tmp_path: Path) -> None:
    """Synthetic equivalent of upstream ``testOutlinesSelfParent``
    (PDFBOX-5939).

    Upstream loads ``PDFBOX-5939-google-docs-1.pdf`` (a Google-Docs export
    where one outline item's ``/Parent`` points at itself, forming a
    self-cycle in the outline tree) twice as the merge source and asserts
    that ``mergeDocuments`` does NOT stack-overflow.

    We rebuild the same structural pathology synthetically:

    * One outline item whose ``/Parent`` entry resolves back to itself —
      same indirect-reference cycle Google Docs emits.
    * Source = destination = the same synthetic file added twice.
    * Assert ``mergeDocuments`` returns cleanly and the merged document
      has the expected page count (2).

    The defence under test is the ``id(parent.get_cos_object()) is
    self._dictionary`` check in
    ``PDOutlineNode.update_parent_open_count`` and the ``visited`` guard
    in ``PDFMergerUtility._merge_outline``.
    """
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
        PDDocumentOutline,
        PDOutlineItem,
    )

    src_path = tmp_path / "self-parent.pdf"
    out_path = tmp_path / "out.pdf"

    # Build a single-page document with a self-parenting outline item.
    doc = _build_doc(1)
    outline = PDDocumentOutline()
    # Wire the outline root <-> item as parent/child first so the item is
    # reachable from the outline root...
    item = PDOutlineItem()
    item.set_title("Self-Parent")
    outline.add_last(item)
    # ...then *break* its /Parent so it points at itself rather than the
    # outline root. This is the PDFBOX-5939 pathology Google Docs emits.
    item.get_cos_object().set_item(
        COSName.get_pdf_name("Parent"), item.get_cos_object()
    )
    doc.get_document_catalog().set_document_outline(outline)
    doc.save(str(src_path))
    doc.close()

    util = PDFMergerUtility()
    util.add_source(str(src_path))
    util.add_source(str(src_path))
    util.set_destination_file_name(str(out_path))
    # Must not stack-overflow / infinite-loop.
    util.merge_documents()

    with PDDocument.load(str(out_path)) as merged:
        assert merged.get_number_of_pages() == 2
        # The merged outline is present and walking it terminates (the
        # ``visited`` guard in ``_merge_outline`` + the self-parent guard
        # in ``update_parent_open_count`` keep us out of the cycle).
        merged_outline = merged.get_document_catalog().get_document_outline()
        if merged_outline is not None:
            seen: set[int] = set()
            cursor = merged_outline.get_first_child()
            steps = 0
            while cursor is not None and steps < 50:
                cid = id(cursor.get_cos_object())
                if cid in seen:
                    break
                seen.add(cid)
                cursor = cursor.get_next_sibling()
                steps += 1
            # We must have terminated naturally (not via the safety cap).
            assert steps < 50, "outline walk failed to terminate"


@pytest.mark.skip(reason="PDFBOX-515 stream-cloning fixture not ported")
def test_pdf_box_515() -> None: ...
