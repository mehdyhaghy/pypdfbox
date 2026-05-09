"""Ported upstream tests for PDFDocEncoding.

Translated from
``pdfbox/src/test/java/org/apache/pdfbox/cos/PDFDocEncodingTest.java``.
Upstream keeps PDFDocEncoding package-private under ``cos``; pypdfbox
implements the encoding helpers in ``pdmodel.common`` and wires them into
``COSString``.
"""

from __future__ import annotations

from pypdfbox.cos import COSString

_DEVIATIONS: tuple[str, ...] = (
    "˘",
    "ˇ",
    "ˆ",
    "˙",
    "˝",
    "˛",
    "˚",
    "˜",
    "•",
    "†",
    "‡",
    "…",
    "—",
    "–",
    "ƒ",
    "⁄",
    "‹",
    "›",
    "−",
    "‰",
    "„",
    "“",
    "”",
    "‘",
    "’",
    "‚",
    "™",
    "ﬁ",
    "ﬂ",
    "Ł",
    "Œ",
    "Š",
    "Ÿ",
    "Ž",
    "ı",
    "ł",
    "œ",
    "š",
    "ž",
    "€",
)


def test_deviations() -> None:
    for deviation in _DEVIATIONS:
        assert COSString(deviation).get_string() == deviation


def test_pdfbox3864() -> None:
    for i in range(256):
        hex_text = f"FEFF{i:04X}"
        cs1 = COSString.parse_hex(hex_text)
        cs2 = COSString(cs1.get_string())
        assert cs1.get_string() == cs2.get_string()
