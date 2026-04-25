"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java

Every test here exercises PDDocument / Loader / PDPageContentStream /
font subsetting / annotations / incremental save — all in the pdmodel and
pdfwriter clusters that pypdfbox does not yet ship. Re-port with those
clusters so the upstream surface stays one-to-one.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="needs PDDocument / incremental save (pdmodel + pdfwriter clusters)")
def test_incrementally_create_document() -> None:
    pass


@pytest.mark.skip(reason="needs PDDocument / Loader / fixture PDF (pdmodel cluster)")
def test_concurrent_modification() -> None:
    pass


@pytest.mark.skip(reason="needs font subsetting / pdmodel.font (fontbox + pdmodel clusters)")
def test_subsetting() -> None:
    pass
