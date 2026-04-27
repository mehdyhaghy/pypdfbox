"""Ported upstream coverage for ``PDFunctionType3``.

Apache PDFBox 3.0 has no dedicated ``PDFunctionType3`` JUnit test class
(only ``TestPDFunctionType4.java`` exists under
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/``).
Stitching is exercised upstream only indirectly through shading / smooth
shading integration tests that require rendering fixtures we have not
ported.

Direct port: not applicable. Hand-written eval coverage lives in
``tests/pdmodel/common/function/test_pd_function_type3_eval.py``.
"""

from __future__ import annotations


def test_no_upstream_pd_function_type3_test_to_port() -> None:
    """Sentinel: documents the absence of an upstream test class so the
    file shows up in test runs and grep-able audits."""
    assert True
