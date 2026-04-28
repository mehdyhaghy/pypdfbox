"""Upstream-ported placeholder for splitter CID-font preservation.

Apache PDFBox 3.0 has no dedicated ``SplitterCIDFontTest.java`` —
embedded-CID-subset preservation across splits is implicitly exercised
by ``PDFMergerUtilityTest`` fixtures (e.g. ``PDFBOX-3262.pdf`` and the
``CJK*.pdf`` family) that we don't carry yet.

The behaviour we mirror: ``PDDocument.import_page`` deep-copies the
page tree including ``/Resources /Font /<X> /DescendantFonts /
FontDescriptor /FontFile2`` (and ``/FontFile3`` for OTF/CFF), copying
the encoded subset stream verbatim. The splitter relies on this and
adds no font-specific cloning.

Hand-written coverage lives in
:mod:`tests.multipdf.test_splitter_cid_fonts`.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "Upstream has no SplitterCIDFontTest.java; CID-font-related splitter "
        "coverage lives in tests/multipdf/test_splitter_cid_fonts.py"
    )
)
def test_upstream_splitter_cid_font_test_class_does_not_exist() -> None:
    pass
