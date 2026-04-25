"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSUpdateInfo.java

Upstream tests the ``COSUpdateInfo`` interface plus ``COSDocumentState``
machinery used by the incremental-save path. pypdfbox's current
``set_needs_to_be_updated`` is a flat flag — the document-state-aware
update logic belongs with the pdfwriter cluster (incremental save).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="needs COSDocumentState / COSUpdateInfo (pdfwriter cluster)")
def test_is_set_need_to_be_update() -> None:
    pass
