"""Tests ported from PDFBox 3.0 ``PDFMergerUtilityTest`` (PDFBOX-5198 slice).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/PDFMergerUtilityTest.java``
on the apache/pdfbox 3.0 branch — the ``testPDFBox5198_2`` /
``testPDFBox5198_3`` regressions on ``PDFA3A.pdf``.

Both tests confirm that after merging multiple copies of a PDF/A-3a
source, the merged ``/StructTreeRoot/K`` is a single top-level
``/Document`` whose ``/K`` array contains exactly one ``/Part`` per
page. The fixture lives in ``src/test/resources/input/merge/`` upstream
(Apache 2.0); we bundle it under ``tests/fixtures/multipdf/``.

Synthetic equivalents already live in
:mod:`tests.multipdf.upstream.test_pdf_merger_utility`
(``test_pdf_box_5198_2`` and ``test_pdf_box_5198_3``); these are
fixture-driven companion ports that exercise the exact upstream input.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.io import create_memory_only_stream_cache
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"


def _check_parts(file_path: Path) -> None:
    """Port of upstream's private ``PDFMergerUtilityTest.checkParts``."""
    with PDDocument.load(str(file_path)) as doc:
        structure_tree_root = doc.get_document_catalog().get_structure_tree_root()
        top_dict = structure_tree_root.get_k()
        assert isinstance(top_dict, COSDictionary)
        assert top_dict.get_item(COSName.get_pdf_name("S")) == COSName.get_pdf_name(
            "Document"
        )
        assert top_dict.get_cos_dictionary(
            COSName.get_pdf_name("P")
        ) is structure_tree_root.get_cos_object()
        k_array = top_dict.get_cos_array(COSName.get_pdf_name("K"))
        assert isinstance(k_array, COSArray)
        assert k_array.size() == doc.get_number_of_pages()
        for i in range(k_array.size()):
            entry = k_array.get_object(i)
            assert isinstance(entry, COSDictionary)
            assert entry.get_item(COSName.get_pdf_name("S")) == COSName.get_pdf_name(
                "Part"
            )
            assert entry.get_cos_dictionary(COSName.get_pdf_name("P")) is top_dict


def test_pdf_box_5198_2(tmp_path: Path) -> None:
    """Port of ``PDFMergerUtilityTest#testPDFBox5198_2`` — fixture-driven
    two-way merge of ``PDFA3A.pdf``."""
    fixture = _FIXTURE_DIR / "PDFA3A.pdf"
    out_path = tmp_path / "PDFA3A-merged2.pdf"

    pdf_merger_utility = PDFMergerUtility()
    pdf_merger_utility.add_source(str(fixture))
    pdf_merger_utility.add_source(str(fixture))
    pdf_merger_utility.set_destination_file_name(str(out_path))
    pdf_merger_utility.merge_documents(create_memory_only_stream_cache())

    _check_parts(out_path)


def test_pdf_box_5198_3(tmp_path: Path) -> None:
    """Port of ``PDFMergerUtilityTest#testPDFBox5198_3`` — fixture-driven
    three-way merge of ``PDFA3A.pdf``."""
    fixture = _FIXTURE_DIR / "PDFA3A.pdf"
    out_path = tmp_path / "PDFA3A-merged3.pdf"

    pdf_merger_utility = PDFMergerUtility()
    pdf_merger_utility.add_source(str(fixture))
    pdf_merger_utility.add_source(str(fixture))
    pdf_merger_utility.add_source(str(fixture))
    pdf_merger_utility.set_destination_file_name(str(out_path))
    pdf_merger_utility.merge_documents(create_memory_only_stream_cache())

    _check_parts(out_path)
