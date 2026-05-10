"""Upstream port stub for :class:`PDTrueTypeFont`.

Upstream PDFBox 3.0.x ships *no* ``PDTrueTypeFontTest.java`` — the
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/`` directory
covers ``PDType1Font``, ``PDFontTest`` (cross-class fixtures), and
``PDCIDFontType2``, but the TrueType simple-font path is exercised only
indirectly through integration tests against rendered PDFs.

When upstream eventually adds a dedicated test class, port it here.
Until then this file holds a single skipped placeholder so the parity
scanner can find an upstream-test row for the class without churning
through a missing-file warning.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="upstream PDFBox 3.0.x has no PDTrueTypeFontTest.java to port"
)
def test_upstream_pd_true_type_font_placeholder() -> None:
    """Placeholder — see module docstring."""
