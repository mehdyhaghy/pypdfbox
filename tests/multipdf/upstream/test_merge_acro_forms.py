"""Ported upstream tests for ``MergeAcroForms``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/multipdf/MergeAcroFormsTest.java``
(PDFBox 3.0.x).

Upstream's three tests each depend on fixture PDFs (PDFBOX-1031,
PDFBOX-1100 from ``target/pdfs/`` — Maven-downloaded; AcroFormForMerge +
PDFBoxLegacyMerge-SameMerged.pdf from
``src/test/resources/org/apache/pdfbox/multipdf/``). None ship with the
pypdfbox repo. The structural slice of the PDFMergerUtility surface
(setters, default modes, file-deletion contract) lives in
``test_pdf_merger_utility.py``; the fixture-driven AcroForm-specific
shapes below are skipped with one-line reasons each.

We additionally port the trivial AcroFormMergeMode setter contract that
upstream's ``testLegacyModeMerge`` exercises before the file-IO portion.
"""

from __future__ import annotations

import pytest

from pypdfbox.multipdf import AcroFormMergeMode, PDFMergerUtility

# --------------------------------------------------------------------- #
# testLegacyModeMerge — structural setter slice (no fixture needed).
# --------------------------------------------------------------------- #


def test_legacy_mode_merge_setter_round_trip(tmp_path) -> None:
    """Mirror the setter-round-trip prelude of upstream
    ``testLegacyModeMerge``.

    Upstream:
        merger.setDestinationFileName(pdfOutput.getAbsolutePath());
        assertEquals(pdfOutput.getAbsolutePath(), merger.getDestinationFileName());
        ...
        merger.setAcroFormMergeMode(AcroFormMergeMode.PDFBOX_LEGACY_MODE);
        assertEquals(AcroFormMergeMode.PDFBOX_LEGACY_MODE, merger.getAcroFormMergeMode());

    The fixture-driven post-merge AcroForm field-equality assertions are
    skipped (see module docstring).
    """
    merger = PDFMergerUtility()
    pdf_output = tmp_path / "PDFBoxLegacyMerge-SameMerged.pdf"
    merger.set_destination_file_name(str(pdf_output))
    assert merger.get_destination_file_name() == str(pdf_output)

    merger.set_acro_form_merge_mode(AcroFormMergeMode.PDFBOX_LEGACY_MODE)
    assert merger.get_acro_form_merge_mode() == AcroFormMergeMode.PDFBOX_LEGACY_MODE


# --------------------------------------------------------------------- #
# testLegacyModeMerge — fixture-driven body (skipped).
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="upstream needs AcroFormForMerge.pdf + a reference "
    "PDFBoxLegacyMerge-SameMerged.pdf gold-result fixture under "
    "src/test/resources/org/apache/pdfbox/multipdf/ — not bundled. The "
    "legacy-mode setter contract is covered by "
    "test_legacy_mode_merge_setter_round_trip."
)
def test_legacy_mode_merge_field_equality() -> None: ...


# --------------------------------------------------------------------- #
# testAnnotsEntry — PDFBOX-1031.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="PDFBOX-1031: requires target/pdfs/PDFBOX-1031-{1,2}.pdf "
    "fixtures (Maven-downloaded corpus) to assert /Annots-per-page "
    "after a two-source merge."
)
def test_annots_entry() -> None: ...


# --------------------------------------------------------------------- #
# testAPEntry — PDFBOX-1100.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="PDFBOX-1100: requires target/pdfs/PDFBOX-1100-{1,2}.pdf "
    "fixtures (Maven-downloaded corpus) to assert /AP + /V "
    "preservation after merging two AcroForm sources."
)
def test_ap_entry() -> None: ...
