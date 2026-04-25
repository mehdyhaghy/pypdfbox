"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/PDFDocEncodingTest.java

PDFDocEncoding is a custom 8-bit encoding with deviations from Latin-1
in the 0x18..0x9F band; pypdfbox's ``COSString`` currently approximates
text via Latin-1 and will be revisited when fontbox/PDFDocEncoding lands.
The deviation round-trip and PDFBOX-3864 hex round-trip both depend on
that proper encoder, so they are skipped here.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="needs PDFDocEncoding (fontbox cluster, not yet ported)")
def test_deviations() -> None:
    pass


@pytest.mark.skip(reason="needs PDFDocEncoding (PDFBOX-3864) — fontbox cluster not yet ported")
def test_pdfbox3864() -> None:
    pass
