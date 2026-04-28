"""Ported upstream tests for ``PDSignature``.

PDFBox 3.0 ships no
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDSignatureTest.java``
file (verified 2026-04-27 against the ``apache/pdfbox`` ``3.0`` branch).
End-to-end signing behavior is exercised upstream through
``CreateSignatureTest`` / ``ShowSignatureTest`` in ``pdfbox-examples``,
which require live keystores and signed sample PDFs we don't ship here.
Hand-written coverage of the pypdfbox surface lives in
``tests/pdmodel/interactive/digitalsignature/test_pd_signature.py``.
"""

from __future__ import annotations


def test_no_upstream_tests_for_pd_signature() -> None:
    """Sentinel — upstream has no test class for ``PDSignature``."""
    assert True
