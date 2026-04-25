"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSName.java

Every test in upstream's TestCOSName drives PDDocument / Loader / PDPage,
none of which pypdfbox ships yet. They are kept here as skipped placeholders
so the porting log stays one-to-one with upstream.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="needs PDDocument/Loader/PDPage (pdmodel cluster, not yet ported)")
def test_pdfbox4076() -> None:
    pass


@pytest.mark.skip(reason="needs PDDocument/Loader/PDField (pdmodel cluster, not yet ported)")
def test_pdfbox6178() -> None:
    pass


@pytest.mark.skip(reason="needs PDDocument/Loader/PDField (pdmodel cluster, not yet ported)")
def test_name_with_ascii_nul() -> None:
    pass
