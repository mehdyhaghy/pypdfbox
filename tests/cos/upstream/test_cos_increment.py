"""
Upstream ``pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java``
exercises ``PDDocument`` / ``PDPageContentStream`` / ``saveIncremental``,
which sit in the ``pdmodel`` + ``pdfwriter`` clusters rather than ``cos``.

The full port lives at
``tests/pdfwriter/upstream/test_save_incremental.py`` where the cluster
boundary fits. This module is intentionally empty — kept around as a
package-shaped breadcrumb so future upstream re-syncs can still find the
test-package mapping for ``cos/TestCOSIncrement.java`` and follow the
docstring to the actual port. No skipped stubs (which would otherwise
double-count as "unported" in the parity audit) live here.
"""

from __future__ import annotations
