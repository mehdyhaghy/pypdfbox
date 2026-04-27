"""Ported upstream coverage for ``PDFunctionType2``.

Apache PDFBox 3.0 ships no dedicated JUnit class for
``PDFunctionType2`` — exponential interpolation is exercised upstream
only through shading / colour / function-creation integration tests in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/``
(``TestPDFunctionType4.java`` is the only file there).

Direct port: not applicable. Hand-written coverage lives in
``tests/pdmodel/common/function/test_pd_function_type_2.py`` and the
broader function-base parity tests in
``tests/pdmodel/common/function/test_pd_function.py``.
"""

from __future__ import annotations


def test_no_upstream_pd_function_type2_test_to_port() -> None:
    """Sentinel: documents the absence of an upstream test class so the
    file shows up in test runs and grep-able audits."""
    assert True
