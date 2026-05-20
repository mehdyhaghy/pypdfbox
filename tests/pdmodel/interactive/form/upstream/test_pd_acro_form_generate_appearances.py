"""Upstream port of ``PDAcroFormGenerateAppearancesTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/
pdmodel/interactive/form/PDAcroFormGenerateAppearancesTest.java``
(PDFBox 3.0.x).

The upstream class is one parameterised test that fetches three PDFs
from Jira at runtime and asserts that
``catalog.getAcroForm()`` doesn't throw. pypdfbox tests never make
network calls — fixtures must live under ``tests/fixtures``.

This port is shaped as a skipped pytest module so the upstream ↔
pypdfbox 1:1 mapping is preserved in PROVENANCE.md. The
``assertDoesNotThrow`` invariant is exercised on every locally-loaded
form PDF in the broader test suite (``test_acro_forms_rotation.py``,
``test_alignment.py``, ``test_fields.py``, etc.), so we keep coverage
of the underlying contract — just not against the upstream fixtures.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="network-fetched fixtures (REDHAT-1301016-0.pdf / AML1.PDF / "
    "PDFBOX-3891-5.pdf via Jira HTTPS); equivalent doesNotThrow coverage "
    "from test_acro_forms_rotation/test_alignment/test_fields"
)
@pytest.mark.parametrize(
    "source_url",
    [
        # PDFBOX-5041 Missing font descriptor
        "https://issues.apache.org/jira/secure/attachment/13016941/REDHAT-1301016-0.pdf",
        # PDFBOX-4086 Character missing for encoding
        "https://issues.apache.org/jira/secure/attachment/12908175/AML1.PDF",
        # PDFBOX-5043 PaperMetaData
        "https://issues.apache.org/jira/secure/attachment/13016992/PDFBOX-3891-5.pdf",
    ],
)
def test_get_acro_form(source_url: str) -> None:
    """Upstream: ``testGetAcroForm``."""
