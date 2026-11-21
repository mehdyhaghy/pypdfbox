"""Tests ported from PDFBox 3.0 ``ASCIIHexFilterTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/filter/ASCIIHexFilterTest.java``
on the apache/pdfbox 3.0 branch (PDFBOX-6330).
"""

import io

from pypdfbox.cos import COSDictionary
from pypdfbox.filter.ascii_hex_filter import ASCIIHexFilter


def test_pdfbox6330() -> None:
    """Port of ``ASCIIHexFilterTest#testPDFBox6330``."""
    s = (
        "4254202F46312032342054662037322\n"
        "0373030205464202848656C6C6F2050\n"
        "4446426F782920546A2045540A>"
    )
    bais = io.BytesIO(s.encode("ascii"))
    baos = io.BytesIO()
    ASCIIHexFilter().decode(bais, baos, COSDictionary(), 0)
    decoded = baos.getvalue().decode("ascii")
    assert decoded == "BT /F1 24 Tf 72 700 Td (Hello PDFBox) Tj ET\n"
