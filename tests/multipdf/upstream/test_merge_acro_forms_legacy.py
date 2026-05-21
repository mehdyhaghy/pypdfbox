"""Tests ported from PDFBox 3.0 ``MergeAcroFormsTest`` (legacy-mode slice).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/MergeAcroFormsTest.java``
on the apache/pdfbox 3.0 branch — the ``testLegacyModeMerge`` field-by-
field equality assertion.

The other upstream fixtures (``PDFBOX-1031`` / ``PDFBOX-1100``) live
under Maven-downloaded ``target/pdfs/`` and remain skipped in
:mod:`tests.multipdf.upstream.test_merge_acro_forms`.

``AcroFormForMerge.pdf`` and ``PDFBoxLegacyMerge-SameMerged.pdf`` are
bundled in-tree under ``src/test/resources/org/apache/pdfbox/multipdf/``
on the upstream PDFBox repo (license: Apache 2.0). We copy them into
``tests/fixtures/multipdf/`` and exercise the full upstream comparison.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.multipdf import AcroFormMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"

# Subset of field-dictionary keys upstream compares (skips /AP — recursive
# appearance dicts can stack-overflow ``COSBase.toString``).
_FIELD_KEYS = ("FT", "T", "TU", "TM", "Ff", "V", "DV", "Opts", "TI", "I", "Rect", "DA")


def _compare_field_properties(source_field, compared_field) -> None:
    """Port of upstream's private ``compareFieldProperties``."""
    source_cos: COSDictionary = source_field.get_cos_object()
    compared_cos: COSDictionary = compared_field.get_cos_object()
    for key in _FIELD_KEYS:
        source_base = source_cos.get_dictionary_object(key)
        compared_base = compared_cos.get_dictionary_object(key)
        if source_base is not None:
            assert isinstance(source_base, COSBase)
            assert compared_base is not None
            assert str(source_base) == str(compared_base), (
                f"The content of field property /{key} differs"
            )
        else:
            assert compared_base is None, (
                f"Source has no /{key} but compared field does"
            )


def test_legacy_mode_merge(tmp_path: Path) -> None:
    """Port of ``MergeAcroFormsTest#testLegacyModeMerge``.

    Self-merges ``AcroFormForMerge.pdf`` (the source listed twice as the
    merger input — upstream supplies the same file via two different
    input shapes; we just use the path twice). The merged result is
    compared field-by-field against the upstream gold reference
    ``PDFBoxLegacyMerge-SameMerged.pdf``.
    """
    pytest.importorskip("pypdfbox.pdmodel.interactive.form")

    to_be_merged = _FIXTURE_DIR / "AcroFormForMerge.pdf"
    reference = _FIXTURE_DIR / "PDFBoxLegacyMerge-SameMerged.pdf"
    pdf_output = tmp_path / "PDFBoxLegacyMerge-SameMerged.pdf"

    merger = PDFMergerUtility()
    merger.set_destination_file_name(str(pdf_output))
    assert merger.get_destination_file_name() == str(pdf_output)
    merger.add_source(str(to_be_merged))
    merger.add_source(str(to_be_merged))
    merger.merge_documents(None)

    merger.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    assert merger.get_acro_form_merge_mode() == AcroFormMergeMode.PDFBOX_LEGACY_MODE

    with (
        PDDocument.load(str(reference)) as compliant_document,
        PDDocument.load(str(pdf_output)) as to_be_compared,
    ):
        compliant_form = compliant_document.get_document_catalog().get_acro_form()
        compared_form = to_be_compared.get_document_catalog().get_acro_form()

        assert len(compliant_form.get_fields()) == len(compared_form.get_fields()), (
            "There shall be the same number of root fields"
        )

        for compliant_field in compliant_form.get_field_tree():
            fqn = compliant_field.get_fully_qualified_name()
            matched = compared_form.get_field(fqn)
            assert matched is not None, f"There shall be a field with FQN={fqn!r}"
            _compare_field_properties(compliant_field, matched)

        for compared_field in compared_form.get_field_tree():
            fqn = compared_field.get_fully_qualified_name()
            matched = compliant_form.get_field(fqn)
            assert matched is not None, f"There shall be a field with FQN={fqn!r}"
            _compare_field_properties(compared_field, matched)
