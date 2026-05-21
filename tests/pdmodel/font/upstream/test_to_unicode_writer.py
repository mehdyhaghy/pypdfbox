"""Ported upstream tests for ``ToUnicodeWriter``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/TestToUnicodeWriter.java``
(PDFBox 3.0.x).

The bulk of upstream's ``TestToUnicodeWriter`` was already ported to
``tests/pdmodel/font/test_to_unicode_writer.py`` in an earlier wave.
This file (a) reaffirms the upstream method list lives under the
``upstream/`` subtree for discoverability, and (b) ports the one
upstream method that the earlier port omitted —
``testAllowDestinationRangeSurrogates``.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.to_unicode_writer import ToUnicodeWriter


def test_allow_destination_range_surrogates() -> None:
    """Port of upstream ``testAllowDestinationRangeSurrogates``.

    Cross-plane jumps (end-of-BMP → start-of-SMP) are denied; sequential
    SMP code points (CJK supplementary block) are allowed; non-sequential
    jumps within the SMP are denied.
    """
    end_of_bmp = chr(0xFFFF)
    beyond_bmp = chr(0x10000)
    cjk1 = chr(0x2F884)
    cjk2 = chr(0x2F885)
    cjk3 = chr(0x2F886)

    # Cross-plane overflow.
    assert ToUnicodeWriter.allow_destination_range(end_of_bmp, beyond_bmp) is False
    # Sequential surrogate-pair-encoded SMP codepoints.
    assert ToUnicodeWriter.allow_destination_range(cjk1, cjk2) is True
    assert ToUnicodeWriter.allow_destination_range(cjk2, cjk3) is True
    # Non-sequential within the SMP.
    assert ToUnicodeWriter.allow_destination_range(cjk1, cjk3) is False
