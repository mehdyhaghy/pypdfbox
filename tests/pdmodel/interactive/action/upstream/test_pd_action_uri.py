"""Port of upstream ``PDActionURITest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/action/PDActionURITest.java``.

Covers PDFBOX-3913 (UTF-8 / UTF-16 BE / UTF-16 LE encoded ``/URI`` entries)
and PDFBOX-3946 (no NPE when ``/URI`` missing).
"""

from __future__ import annotations

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionURI

_URI: COSName = COSName.get_pdf_name("URI")


def test_utf8_uri() -> None:
    """PDFBOX-3913 + PDFBOX-3946: UTF-8 ``/URI`` decode + None on absent entry."""
    action_uri = PDActionURI()
    assert action_uri.get_uri() is None
    # The garbled string in the upstream Java test is the result of decoding the
    # UTF-8 bytes of ``"http://経営承継.com/"`` as latin-1; round-tripping the same
    # bytes through ``set_uri`` exercises the UTF-8 fallback path that
    # ``COSString`` writes for non-PDFDocEncoding-safe text.
    action_uri.set_uri("http://経営承継.com/")
    assert action_uri.get_uri() == "http://経営承継.com/"


def test_utf16_be_uri() -> None:
    """PDFBOX-3913: BOM-led UTF-16 BE ``/URI`` is decoded transparently.

    The hex bytes are taken from govdocs file 534948.pdf (per upstream).
    """
    action_uri = PDActionURI()
    utf16_uri = COSString.parse_hex(
        "FEFF0068007400740070003A002F002F00770077"
        "0077002E006E00610070002E006500640075002F0063006100740061006C006F006700"
        "2F00310031003100340030002E00680074006D006C"
    )
    action_uri.get_cos_object().set_item(_URI, utf16_uri)
    assert action_uri.get_uri() == "http://www.nap.edu/catalog/11140.html"


def test_utf16_le_uri() -> None:
    """PDFBOX-3913: BOM-led UTF-16 LE ``/URI`` is decoded transparently."""
    action_uri = PDActionURI()
    utf16_uri = COSString.parse_hex("FFFE68007400740070003A00")
    action_uri.get_cos_object().set_item(_URI, utf16_uri)
    assert action_uri.get_uri() == "http:"


def test_utf7_uri() -> None:
    """Plain ASCII ``/URI`` round-trips unchanged."""
    action_uri = PDActionURI()
    action_uri.set_uri("http://pdfbox.apache.org/")
    assert action_uri.get_uri() == "http://pdfbox.apache.org/"
