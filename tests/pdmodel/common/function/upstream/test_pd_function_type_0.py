"""Ported upstream coverage for ``PDFunctionType0``.

Apache PDFBox 3.0.x has no dedicated ``TestPDFunctionType0.java`` JUnit
class under ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/function/``
— sampled-function evaluation is exercised upstream only indirectly via
shading and ICC-profile rendering integration tests that depend on
fixtures we have not ported.

Direct port: not applicable. Hand-written eval and round-out coverage
lives in:
- ``tests/pdmodel/common/function/test_pd_function_type0_eval.py`` —
  encode/clamp/n-linear-interp/decode pipeline across multiple
  ``/BitsPerSample`` widths (1, 2, 4, 8, 12, 16) and 1D / 2D layouts
  including cubic ``/Order = 3`` and unsupported-order fallback.
- ``tests/pdmodel/common/function/test_pd_function_type_0.py`` —
  accessor / setter round-trips, ``get_samples`` lazy decode + cache
  invalidation, and 1-in/1-out + 2-in/3-out eval parity.
"""

from __future__ import annotations


def test_no_upstream_pd_function_type_0_test_to_port() -> None:
    """Sentinel: documents the absence of an upstream test class so this
    file shows up in test runs and grep-able audits."""
    assert True
