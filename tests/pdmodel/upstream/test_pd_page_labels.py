"""Upstream-mirror module for ``PDPageLabels``.

Apache PDFBox 3.0 ships **no** dedicated JUnit class for ``PDPageLabels``
or ``PDPageLabelRange`` (verified against
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/`` — only
``COSArrayListTest``, ``PDImmutableRectangleTest``,
``PDIntegerNameTreeNode``, ``PDStreamTest``, ``TestEmbeddedFiles``,
``TestPDNameTreeNode``, ``TestPDNumberTreeNode`` are present at the time
of porting). The behaviour is exercised indirectly through the upstream
``PDNumberTreeNode`` tests, which require a full ``PDNumberTreeNode``
port (deferred — see ``CHANGES.md``).

Hand-written coverage lives in ``tests/pdmodel/test_pd_page_labels.py``.
"""

from __future__ import annotations
