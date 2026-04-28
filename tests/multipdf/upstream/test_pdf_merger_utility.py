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
from pypdfbox.pdmodel import PDDocument, PDPage


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


@pytest.mark.skip(reason="upstream PDFA_check.pdf fixture + rendering not ported")
def test_pdf_merger_utility() -> None: ...


@pytest.mark.skip(reason="upstream compressed-resource fixture + rendering not ported")
def test_pdf_merger_utility_2() -> None: ...


@pytest.mark.skip(reason="JPEG/CCITT image-stream comparison not ported")
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


@pytest.mark.skip(reason="bogus StructParents fixture not ported")
def test_merge_bogus_struct_parents_1() -> None: ...


@pytest.mark.skip(reason="bogus StructParents fixture not ported")
def test_merge_bogus_struct_parents_2() -> None: ...


@pytest.mark.skip(reason="ParentTree numeric-tree mapping deferred")
def test_parent_tree() -> None: ...


@pytest.mark.skip(reason="PDFBOX-5198 Document/Parts structure deferred")
def test_pdf_box_5198_2() -> None: ...


@pytest.mark.skip(reason="PDFBOX-5198 Document/Parts structure deferred")
def test_pdf_box_5198_3() -> None: ...


@pytest.mark.skip(reason="Splitter-side tests live with the splitter port")
def test_split_with_structure_tree() -> None: ...


@pytest.mark.skip(reason="Splitter-side tests live with the splitter port")
def test_split_with_structure_tree_and_destinations() -> None: ...


@pytest.mark.skip(reason="Splitter-side tests live with the splitter port")
def test_split_with_structure_tree_and_destinations_and_removed_annotations() -> (
    None
): ...


@pytest.mark.skip(reason="Splitter-side test")
def test_single_page_split() -> None: ...


@pytest.mark.skip(reason="Splitter-side test")
def test_split_with_popup_annotations() -> None: ...


@pytest.mark.skip(reason="Splitter-side test")
def test_split_with_broken_destination() -> None: ...


@pytest.mark.skip(reason="Splitter-side test")
def test_split_with_named_destinations() -> None: ...


@pytest.mark.skip(reason="Splitter-side test")
def test_split_with_pg_entry_at_the_top() -> None: ...


@pytest.mark.skip(reason="Splitter-side test")
def test_split_with_orphan_popup_annotation() -> None: ...


@pytest.mark.skip(reason="Self-parent outline fixture not ported")
def test_outlines_self_parent() -> None: ...


@pytest.mark.skip(reason="PDFBOX-515 stream-cloning fixture not ported")
def test_pdf_box_515() -> None: ...
