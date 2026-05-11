"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSIncrement.java

Upstream lives in the ``cos`` test package; the body exercises
``PDDocument``/``PDPageContentStream``/``saveIncremental`` which sit
in pdmodel + pdfwriter. The full ports of
``testIncrementallyCreateDocument`` and ``testSubsetting`` live in
``tests/pdfwriter/upstream/test_save_incremental.py`` where the cluster
boundary fits — this module stays a stub at the cos location so future
upstream re-syncs still find the package mapping.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason=(
        "Duplicate of upstream cos/TestCOSIncrement.java — full port lives at "
        "tests/pdfwriter/upstream/test_save_incremental.py (cluster fit)."
    )
)
def test_incrementally_create_document() -> None:
    pass


@pytest.mark.skip(
    reason=(
        "Duplicate of upstream cos/TestCOSIncrement.java — port covered "
        "at tests/pdfwriter/upstream/test_save_incremental.py; still requires "
        "the network-fetched PDFBOX-5263 fixture."
    )
)
def test_concurrent_modification() -> None:
    pass


@pytest.mark.skip(
    reason=(
        "Duplicate of upstream cos/TestCOSIncrement.java — port covered "
        "at tests/pdfwriter/upstream/test_save_incremental.py."
    )
)
def test_subsetting() -> None:
    pass
