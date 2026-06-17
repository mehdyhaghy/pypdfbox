"""Port of fontbox/src/test/java/org/apache/fontbox/pfb/PfbParserTest.java

Upstream baseline: PDFBox 3.0.7.

``testPfb`` and ``testPfbPDFBox5713`` are skipped: they read large PFB
fonts (``OpenSans-Regular.pfb``, ``DejaVuSerifCondensed.pfb``) that
upstream downloads into ``target/fonts/`` at build time and that the
repo does not bundle. The two pure-logic methods — the empty-input and
negative-record-size guards — are portable and ported here. ``IOException``
maps to ``OSError`` per the project's test-porting conventions.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.pfb.pfb_parser import PfbParser
from pypdfbox.fontbox.type1.type1_font import Type1Font


def test_empty() -> None:
    """Test 0 length font."""
    with pytest.raises(OSError):
        Type1Font.create_with_pfb(b"")


def test_negative_record_size() -> None:
    """A PFB with a negative size field (integer overflow) must raise
    ``OSError`` instead of crashing. A crafted 18-byte PFB whose size
    bytes ``01 00 00 FF`` overflow the signed int to -16777215 bypasses
    the upper-bound check upstream — pypdfbox treats the unsigned value
    as larger-than-input and rejects it the same way.
    """
    crash_input = bytes(
        [
            0x80,
            0x01,  # header
            0x01,
            0x00,
            0x00,
            0xFF,  # size: overflows to negative
            0xFF,
            0xFF,
            0xFF,  # garbage data
            0xFF,
            0xFF,
            0xFF,
            0x27,
            0x05,
            0xF8,
            0xFF,
            0xD2,
            0x40,
        ]
    )
    with pytest.raises(OSError):
        PfbParser(crash_input)
