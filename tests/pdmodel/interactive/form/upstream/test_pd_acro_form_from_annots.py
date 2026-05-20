"""Upstream port of ``PDAcroFormFromAnnotsTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/
pdmodel/interactive/form/PDAcroFormFromAnnotsTest.java`` (PDFBox 3.0.x).

Every upstream test fetches a fixture PDF from
``https://issues.apache.org/jira/secure/attachment/<id>/...`` at
runtime. pypdfbox tests never make network calls — fixtures must live
under ``tests/fixtures``. This port keeps the test class shape but
``pytest.skip``s every method with a one-line reason so the upstream
↔ pypdfbox 1:1 mapping in PROVENANCE.md is preserved.

The ``AcroFormDefaultFixup`` / ``AcroFormOrphanWidgetsProcessor`` /
``AbstractFixup`` classes do exist in pypdfbox
(``pypdfbox/pdmodel/fixup``), so a future wave that copies the
fixtures into ``tests/fixtures/pdmodel/interactive/form/`` (and adds
matching ``PROVENANCE.md`` rows) can drop the skips.
"""

from __future__ import annotations

import pytest

# Skipped upstream methods — all depend on the same network-fetched fixtures:
#   testFromAnnots4985DefaultMode   — POPPLER-806.pdf
#   testFromAnnots4985CorrectionMode
#   testFromAnnots4985WithoutCorrectionMode
#   testFromAnnots3891DontCreateFields
#   testFromAnnots3891CreateFields
#   testFromAnnots3891ValidateFont
#   testFromAnnots3891NullField


@pytest.mark.skip(reason="network-fetched fixture (POPPLER-806.pdf via Jira HTTPS)")
def test_from_annots_4985_default_mode() -> None:
    """Upstream: ``testFromAnnots4985DefaultMode`` (PDFBOX-4985)."""


@pytest.mark.skip(reason="network-fetched fixture (POPPLER-806.pdf via Jira HTTPS)")
def test_from_annots_4985_correction_mode() -> None:
    """Upstream: ``testFromAnnots4985CorrectionMode`` (PDFBOX-4985)."""


@pytest.mark.skip(reason="network-fetched fixture (POPPLER-806.pdf via Jira HTTPS)")
def test_from_annots_4985_without_correction_mode() -> None:
    """Upstream: ``testFromAnnots4985WithoutCorrectionMode`` (PDFBOX-4985)."""


@pytest.mark.skip(reason="network-fetched fixture (merge-test.pdf via Jira HTTPS)")
def test_from_annots_3891_dont_create_fields() -> None:
    """Upstream: ``testFromAnnots3891DontCreateFields`` (PDFBOX-3891)."""


@pytest.mark.skip(reason="network-fetched fixture (merge-test.pdf via Jira HTTPS)")
def test_from_annots_3891_create_fields() -> None:
    """Upstream: ``testFromAnnots3891CreateFields`` (PDFBOX-3891)."""


@pytest.mark.skip(reason="network-fetched fixture (merge-test.pdf via Jira HTTPS)")
def test_from_annots_3891_validate_font() -> None:
    """Upstream: ``testFromAnnots3891ValidateFont`` (PDFBOX-3891)."""


@pytest.mark.skip(reason="network-fetched fixture (poppler-14433-0.pdf via Jira HTTPS)")
def test_from_annots_3891_null_field() -> None:
    """Upstream: ``testFromAnnots3891NullField`` (PDFBOX-3891)."""
