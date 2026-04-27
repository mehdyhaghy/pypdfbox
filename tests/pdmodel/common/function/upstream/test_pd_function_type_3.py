"""Ported upstream coverage for ``PDFunctionType3`` (alias filename).

Apache PDFBox 3.0.x ships no dedicated ``TestPDFunctionType3.java`` under
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/`` —
only ``TestPDFunctionType4.java`` exists. Stitching is exercised upstream
indirectly through shading rendering integration tests we have not ported.

Direct port: not applicable. The underscored filename mirrors the brief's
requested layout; the canonical hand-written eval coverage lives in
``tests/pdmodel/common/function/test_pd_function_type3_eval.py`` and
``test_pd_function_type_3.py`` (accessor + boundary cases).
"""

from __future__ import annotations


def test_no_upstream_pd_function_type_3_test_to_port() -> None:
    """Sentinel: documents the absence of an upstream JUnit class for Type 3."""
    assert True
