"""Tests ported from PDFBox 3.0 ``PDFMergerUtilityTest`` (struct-tree slice #4).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFMergerUtilityTest.java``
on the apache/pdfbox 3.0 branch — the ``testStructureTreeMerge4``
self-merge regression on ``PDFBOX-4417-001031.pdf``.

The fixture ships in ``src/test/resources/org/apache/pdfbox/multipdf/``
upstream (Apache 2.0); we already bundle it under
``tests/fixtures/multipdf/PDFBOX-4417-001031.pdf`` and re-use it here.

Upstream's private ``ElementCounter`` walker is re-implemented in
this module as ``_ElementCounter`` — kept verbatim in structure so the
upstream-vs-port comparison is line-of-sight. The other
``checkWithNumberTree`` / ``checkForPageOrphans`` /
``checkStructTreeRootCount`` helpers traverse much wider invariants
(/StructTreeRoot count across the saved file, /Pg pointers vs the page
tree, etc.) — porting them is large and orthogonal to the regression
this test guards, so they're left for a later wave.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSObject
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"


class _ElementCounter:
    """Port of upstream's private ``PDFMergerUtilityTest.ElementCounter``."""

    def __init__(self) -> None:
        self.cnt = 0
        self.set: set[int] = set()  # identity set — COSDictionary unhashable

    def walk(self, base: COSBase | None) -> None:
        if base is None:
            return
        if isinstance(base, COSArray):
            for base2 in base:
                if isinstance(base2, COSObject):
                    base2 = base2.get_object()
                self.walk(base2)
            return
        if isinstance(base, COSDictionary):
            kdict = base
            pg = COSName.get_pdf_name("Pg")
            k_key = COSName.get_pdf_name("K")
            mcid = COSName.get_pdf_name("MCID")
            if kdict.contains_key(pg):
                self.cnt += 1
                self.set.add(id(kdict))
            elif kdict.contains_key(k_key):
                # at least 1 kid with dict with /Pg, /MCID — happens with
                # confidential file from PDFBOX-6009.
                kid_array = kdict.get_cos_array(k_key)
                if kid_array is not None:
                    for i in range(kid_array.size()):
                        base2 = kid_array.get_object(i)
                        if (
                            isinstance(base2, COSDictionary)
                            and base2.contains_key(pg)
                            and base2.contains_key(mcid)
                        ):
                            self.cnt += 1
                            self.set.add(id(kdict))
                            break
            if kdict.contains_key(k_key):
                self.walk(kdict.get_dictionary_object(k_key))


def _self_merge_and_count(fixture: Path, out_path: Path) -> tuple[int, int, int, int]:
    """Helper: self-merge ``fixture`` into ``out_path`` and return
    ``(src_cnt, src_set, merged_cnt, merged_set)``.

    Centralises the ``testStructureTreeMerge4`` / ``testStructureTreeMerge5``
    common shape so each upstream-port test stays a one-liner above the
    upstream-pinned expected counts.
    """
    pdf_merger_utility = PDFMergerUtility()
    with PDDocument.load(str(fixture)) as src:
        src_counter = _ElementCounter()
        src_counter.walk(
            src.get_document_catalog().get_structure_tree_root().get_k()
        )
        dst = PDDocument.load(str(fixture))
        try:
            pdf_merger_utility.append_document(dst, src)
            dst.save(str(out_path))
        finally:
            dst.close()
    with PDDocument.load(str(out_path)) as merged:
        merged_counter = _ElementCounter()
        merged_counter.walk(
            merged.get_document_catalog().get_structure_tree_root().get_k()
        )
    return (
        src_counter.cnt,
        len(src_counter.set),
        merged_counter.cnt,
        len(merged_counter.set),
    )


def test_structure_tree_merge_4(tmp_path: Path) -> None:
    """Port of ``PDFMergerUtilityTest#testStructureTreeMerge4`` — self-
    merge ``PDFBOX-4417-001031.pdf`` and confirm the merged structure
    tree's element count is exactly double the source's.
    """
    fixture = _FIXTURE_DIR / "PDFBOX-4417-001031.pdf"
    out_path = tmp_path / "PDFBOX-4417-001031-merged.pdf"
    src_cnt, src_set, merged_cnt, merged_set = _self_merge_and_count(fixture, out_path)
    assert src_cnt == 104
    assert src_set == 104
    assert merged_cnt == src_cnt * 2
    assert merged_set == src_set * 2


def test_structure_tree_merge_id_tree(tmp_path: Path) -> None:
    """Port of ``PDFMergerUtilityTest#testStructureTreeMergeIDTree``
    (PDFBOX-4416 / PDFBOX-4009).

    Two-step merge over the ``/IDTree`` of two distinct source files:

    1. Pull the source's ID tree into an empty destination; the new
       destination's ``/StructTreeRoot/ParentTreeNextKey`` must be 4
       (the upstream expectation pinned for PDFBOX-4009).
    2. Append that intermediate into a real second source; the merged
       ``/IDTree`` size must match the sum of the two original tree
       sizes (192 entries upstream).

    ``checkWithNumberTree`` / ``checkForPageOrphans`` /
    ``checkStructTreeRootCount`` are not ported (see module docstring
    in :mod:`tests.multipdf.upstream.test_pdf_merger_utility_structure_tree`).
    """
    fixture_src = _FIXTURE_DIR / "PDFBOX-4417-001031.pdf"
    fixture_dst = _FIXTURE_DIR / "PDFBOX-4417-054080.pdf"
    out_path = tmp_path / "PDFBOX-4416-IDTree-merged.pdf"

    pdf_merger_utility = PDFMergerUtility()
    with (
        PDDocument.load(str(fixture_src)) as src_doc,
        PDDocument.load(str(fixture_dst)) as dst_doc,
    ):
        src_root = src_doc.get_document_catalog().get_structure_tree_root()
        dst_root = dst_doc.get_document_catalog().get_structure_tree_root()
        src_id_tree = src_root.get_id_tree()
        src_map = PDFMergerUtility.get_id_tree_as_map(src_id_tree)
        dst_id_tree = dst_root.get_id_tree()
        dst_map = PDFMergerUtility.get_id_tree_as_map(dst_id_tree)
        expected_total = len(src_map) + len(dst_map)
        assert expected_total == 192

        # PDFBOX-4009: empty dest doc still merges structure tree
        empty_dest = PDDocument()
        try:
            pdf_merger_utility.append_document(empty_dest, src_doc)
            assert (
                empty_dest.get_document_catalog()
                .get_structure_tree_root()
                .get_parent_tree_next_key()
                == 4
            )

            pdf_merger_utility.append_document(dst_doc, empty_dest)
        finally:
            empty_dest.close()

        dst_doc.save(str(out_path))

    with PDDocument.load(str(out_path)) as merged:
        merged_root = merged.get_document_catalog().get_structure_tree_root()
        merged_id_tree = merged_root.get_id_tree()
        merged_map = PDFMergerUtility.get_id_tree_as_map(merged_id_tree)
        assert len(merged_map) == expected_total


def test_structure_tree_merge_5(tmp_path: Path) -> None:
    """Port of ``PDFMergerUtilityTest#testStructureTreeMerge5``.

    PDFBOX-4417 regression: same shape as ``testStructureTreeMerge4``
    against ``PDFBOX-4417-054080.pdf``, whose ``/K`` tree starts with
    two dictionaries (not an array) — broke the pre-PDFBOX-4417 merge
    code path. Upstream doesn't pin the singleton count for this
    fixture (the assertion is structural only: merged == 2 × source);
    we follow that and re-port the doubling invariant verbatim.
    """
    fixture = _FIXTURE_DIR / "PDFBOX-4417-054080.pdf"
    out_path = tmp_path / "PDFBOX-4417-054080-merged.pdf"
    src_cnt, src_set, merged_cnt, merged_set = _self_merge_and_count(fixture, out_path)
    assert merged_cnt == src_cnt * 2
    assert merged_set == src_set * 2
