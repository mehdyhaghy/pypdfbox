"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/color/PDICCBasedTest.java

Upstream baseline: PDFBox 3.0.x. Validates ``PDICCBased`` empty constructor
behavior (PDFBOX-2812).

Upstream's ``PDICCBased(PDDocument)`` constructor exists to register the
empty profile stream with the document on close. pypdfbox's matching empty
constructor is the no-arg ``PDICCBased()`` form (the array slot 1 stream is
created locally and attached when the color space is wired into a resource
dictionary). The test's surface contract — ``get_name() == "ICCBased"`` and
the underlying ``PDStream`` exists — holds for both.
"""
from __future__ import annotations

from pypdfbox.pdmodel.graphics.color import PDICCBased


def test_constructor() -> None:
    """Test of constructor for PDFBOX-2812."""
    icc_based = PDICCBased()
    assert icc_based.get_name() == "ICCBased"
    assert icc_based.get_pd_stream() is not None
