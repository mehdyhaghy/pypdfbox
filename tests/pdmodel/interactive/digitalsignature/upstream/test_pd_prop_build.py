"""Ported upstream tests for ``PDPropBuild`` / ``PDPropBuildDataDict``.

PDFBox 3.0 ships no dedicated JUnit test class for either build
properties wrapper (verified 2026-04-27 against the ``apache/pdfbox``
``3.0`` branch — no
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/digitalsignature/PDPropBuild*Test.java``
exists). The wrappers are validated indirectly upstream through the
``ShowSignatureTest`` end-to-end suite. Hand-written coverage of the
pypdfbox surface lives in
``tests/pdmodel/interactive/digitalsignature/test_pd_prop_build.py``.
"""

from __future__ import annotations


def test_no_upstream_tests_for_pd_prop_build() -> None:
    """Sentinel — upstream has no test class for ``PDPropBuild``."""
    assert True
