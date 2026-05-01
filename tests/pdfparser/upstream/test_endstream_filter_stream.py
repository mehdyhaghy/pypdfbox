"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/pdfparser/EndstreamFilterStreamTest.java

The upstream test has two methods. ``testEndstreamFilterStream`` walks
five hand-built byte-sequence scenarios and is a direct translation.
``testPDFBox2079EmbeddedFile`` exercises the high-level ``Loader`` /
``PDDocument`` / embedded-file plumbing on the ``embedded_zip.pdf``
fixture; it is skipped here because it really tests the upstream
``readUntilEndStream`` integration rather than the filter helper, and
the fixture isn't part of our test corpus.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdfparser import EndstreamFilterStream


def test_endstream_filter_stream():
    feos = EndstreamFilterStream()
    tab1 = bytes([1, 2, 3, 4])
    tab2 = bytes([5, 6, 7, ord("\r"), ord("\n")])
    tab3 = bytes([8, 9, ord("\r"), ord("\n")])
    feos.filter(tab1, 0, len(tab1))
    feos.filter(tab2, 0, len(tab2))
    feos.filter(tab3, 0, len(tab3))
    expected_result_1 = bytes([1, 2, 3, 4, 5, 6, 7, ord("\r"), ord("\n"), 8, 9])
    assert feos.calculate_length() == len(expected_result_1)

    feos = EndstreamFilterStream()
    tab4 = bytes([1, 2, 3, 4])
    tab5 = bytes([5, 6, 7, ord("\r")])
    tab6 = bytes([8, 9, ord("\n")])
    feos.filter(tab4, 0, len(tab4))
    feos.filter(tab5, 0, len(tab5))
    feos.filter(tab6, 0, len(tab6))
    expected_result_2 = bytes([1, 2, 3, 4, 5, 6, 7, ord("\r"), 8, 9])
    assert feos.calculate_length() == len(expected_result_2)

    feos = EndstreamFilterStream()
    tab7 = bytes([1, 2, 3, 4, ord("\r")])
    tab8 = bytes([ord("\n"), 5, 6, 7, ord("\n")])
    tab9 = bytes([8, 9, ord("\r")])  # final CR is not to be discarded
    feos.filter(tab7, 0, len(tab7))
    feos.filter(tab8, 0, len(tab8))
    feos.filter(tab9, 0, len(tab9))
    expected_result_3 = bytes(
        [1, 2, 3, 4, ord("\r"), ord("\n"), 5, 6, 7, ord("\n"), 8, 9, ord("\r")]
    )
    assert feos.calculate_length() == len(expected_result_3)

    feos = EndstreamFilterStream()
    tab10 = bytes([1, 2, 3, 4, ord("\r")])
    tab11 = bytes([ord("\n"), 5, 6, 7, ord("\r")])
    tab12 = bytes([8, 9, ord("\r")])
    tab13 = bytes([ord("\n")])  # final CR LF across buffers
    feos.filter(tab10, 0, len(tab10))
    feos.filter(tab11, 0, len(tab11))
    feos.filter(tab12, 0, len(tab12))
    feos.filter(tab13, 0, len(tab13))
    expected_result_4 = bytes(
        [1, 2, 3, 4, ord("\r"), ord("\n"), 5, 6, 7, ord("\r"), 8, 9]
    )
    assert feos.calculate_length() == len(expected_result_4)

    feos = EndstreamFilterStream()
    tab14 = bytes([1, 2, 3, 4, ord("\r")])
    tab15 = bytes([ord("\n"), 5, 6, 7, ord("\r")])
    tab16 = bytes([8, 9, ord("\n")])
    tab17 = bytes([ord("\r")])  # final CR is not to be discarded
    feos.filter(tab14, 0, len(tab14))
    feos.filter(tab15, 0, len(tab15))
    feos.filter(tab16, 0, len(tab16))
    feos.filter(tab17, 0, len(tab17))
    expected_result_5 = bytes(
        [1, 2, 3, 4, ord("\r"), ord("\n"), 5, 6, 7, ord("\r"), 8, 9, ord("\n"), ord("\r")]
    )
    assert feos.calculate_length() == len(expected_result_5)


# Upstream: testPDFBox2079EmbeddedFile — exercises Loader + embedded-file
# round-trip on a PDF whose stream omits /Length. The fixture isn't in
# our corpus and the test really covers ``readUntilEndStream`` plumbing
# rather than EndstreamFilterStream itself.
@pytest.mark.skip(
    reason="High-level Loader/embedded-file integration; fixture not in pypdfbox corpus"
)
def test_pdfbox_2079_embedded_file():  # pragma: no cover
    pass
