"""Tests ported from PDFBox 3.0 ``ASCII85InputStreamTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/filter/ASCII85InputStreamTest.java``
on the apache/pdfbox 3.0 branch (PDFBOX-6317, PDFBOX-6330).
"""

import io

from pypdfbox.filter.ascii85_input_stream import ASCII85InputStream


def _decode_string(input_string: str) -> str:
    stream = ASCII85InputStream(io.BytesIO(input_string.encode("ascii")))
    return stream.read().decode("ascii")


def test_pdfbox6317() -> None:
    """Port of ``ASCII85InputStreamTest#testPDFBOX6317``."""
    end_marker = "~>"
    s1 = '87cURD]i,"Ebo80'
    s2 = "87cURD]i"
    s3 = "z"
    assert _decode_string(s1 + end_marker) == "Hello World!"
    assert _decode_string(s1) == "Hello World!"
    assert _decode_string(s2 + end_marker) == "Hello "
    assert _decode_string(s2) == "Hello "
    assert _decode_string(s3) == "\x00\x00\x00\x00"


def test_pdfbox6330() -> None:
    """Port of ``ASCII85InputStreamTest#testPDFBox6330``."""
    s1 = "6<#'\\7PQ#@\t1a#b0+?)%u\t2_Zp.<+I+\"\t87cURD]hkE\t7RD$<.3MT)\t+@T6:~>"
    assert _decode_string(s1) == "BT /F1 24 Tf 72 700 Td (Hello PDFBox) Tj ET\n"
