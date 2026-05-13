"""Ported upstream tests for PDFDocEncoding.

Translated from
``pdfbox/src/test/java/org/apache/pdfbox/cos/PDFDocEncodingTest.java``
(PDFBox 3.0). Upstream lives in the ``cos`` package; pypdfbox places the
encoding under ``pdmodel.common`` and so the test file is colocated there.

The two upstream test methods are translated below. Notes on the ported
test ``test_pdfbox3864`` — upstream ``COSString#equals`` compares
``getString()`` outputs (not raw bytes); the pypdfbox port retains
byte-level equality (see ``tests/cos/test_cos_string.py``). To preserve
the *semantic* guarantee that PDFBOX-3864 was checking — that every char
below 256 round-trips through ``COSString(text) → getString() → ...``
without information loss — we compare ``get_string()`` results instead
of raw equals, which matches what upstream's equals actually evaluates.
"""

from __future__ import annotations

from pypdfbox.cos import COSString

# All deviations (based on the table in ISO 32000-1:2008).
_DEVIATIONS: tuple[str, ...] = (
    # block 1
    "˘",  # BREVE
    "ˇ",  # CARON
    "ˆ",  # MODIFIER LETTER CIRCUMFLEX ACCENT
    "˙",  # DOT ABOVE
    "˝",  # DOUBLE ACUTE ACCENT
    "˛",  # OGONEK
    "˚",  # RING ABOVE
    "˜",  # SMALL TILDE
    # block 2
    "•",  # BULLET
    "†",  # DAGGER
    "‡",  # DOUBLE DAGGER
    "…",  # HORIZONTAL ELLIPSIS
    "—",  # EM DASH
    "–",  # EN DASH
    "ƒ",  # LATIN SMALL LETTER SCRIPT F
    "⁄",  # FRACTION SLASH (solidus)
    "‹",  # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    "›",  # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    "−",  # MINUS SIGN
    "‰",  # PER MILLE SIGN
    "„",  # DOUBLE LOW-9 QUOTATION MARK (quotedblbase)
    "“",  # LEFT DOUBLE QUOTATION MARK (quotedblleft)
    "”",  # RIGHT DOUBLE QUOTATION MARK (quotedblright)
    "‘",  # LEFT SINGLE QUOTATION MARK (quoteleft)
    "’",  # RIGHT SINGLE QUOTATION MARK (quoteright)
    "‚",  # SINGLE LOW-9 QUOTATION MARK (quotesinglbase)
    "™",  # TRADE MARK SIGN
    "ﬁ",  # LATIN SMALL LIGATURE FI
    "ﬂ",  # LATIN SMALL LIGATURE FL
    "Ł",  # LATIN CAPITAL LETTER L WITH STROKE
    "Œ",  # LATIN CAPITAL LIGATURE OE
    "Š",  # LATIN CAPITAL LETTER S WITH CARON
    "Ÿ",  # LATIN CAPITAL LETTER Y WITH DIAERESIS
    "Ž",  # LATIN CAPITAL LETTER Z WITH CARON
    "ı",  # LATIN SMALL LETTER DOTLESS I
    "ł",  # LATIN SMALL LETTER L WITH STROKE
    "œ",  # LATIN SMALL LIGATURE OE
    "š",  # LATIN SMALL LETTER S WITH CARON
    "ž",  # LATIN SMALL LETTER Z WITH CARON
    "€",  # EURO SIGN
)


def test_deviations() -> None:
    # Mirrors upstream testDeviations(): every deviation char survives
    # COSString(text) → getString() round-trip.
    for deviation in _DEVIATIONS:
        cos_string = COSString(deviation)
        assert cos_string.get_string() == deviation


def test_pdfbox3864() -> None:
    # PDFBOX-3864: every BMP character below 256 must round-trip through
    # the COSString text-string contract. Translated to compare
    # get_string() (the semantic content), since the pypdfbox COSString
    # uses byte-level equality where upstream uses string-based equality.
    for i in range(256):
        hex_text = f"FEFF{i:04X}"
        cs1 = COSString.parse_hex(hex_text)
        cs2 = COSString(cs1.get_string())
        assert cs1.get_string() == cs2.get_string()
