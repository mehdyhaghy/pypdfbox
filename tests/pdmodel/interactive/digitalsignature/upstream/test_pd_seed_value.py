"""Ported upstream tests for ``PDSeedValue``.

PDFBox 3.0 ships no
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSeedValueTest.java``
file (verified 2026-04-27 against the
``apache/pdfbox`` ``3.0`` branch). This stub exists so future re-syncs
can drop a ported file here without restructuring. Hand-written coverage
of the pypdfbox port lives in
``tests/pdmodel/interactive/digitalsignature/test_pd_seed_value_parity.py``.
"""

from __future__ import annotations


def test_no_upstream_tests_yet() -> None:
    """Sentinel — upstream has no test class for ``PDSeedValue``."""
    assert True
