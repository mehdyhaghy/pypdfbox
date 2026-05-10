"""Port of upstream JUnit ``CFFEncodingTest``.

Source: ``pdfbox/fontbox/src/test/java/org/apache/fontbox/cff/CFFEncodingTest.java``
(PDFBox 3.0). Both upstream tests are translated 1:1 — JUnit
``@Test void`` -> ``def test_...``, ``assertEquals`` -> ``assert ==``.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_expert_encoding import CFFExpertEncoding
from pypdfbox.fontbox.cff.cff_standard_encoding import CFFStandardEncoding


def test_cff_expert_encoding() -> None:
    cff_expert_encoding = CFFExpertEncoding.get_instance()
    # check some randomly chosen mappings
    assert cff_expert_encoding.get_name(0) == ".notdef"
    assert cff_expert_encoding.get_name(32) == "space"
    assert cff_expert_encoding.get_name(112) == "Psmall"
    assert cff_expert_encoding.get_name(251) == "Ucircumflexsmall"
    assert cff_expert_encoding.get_code("space") == 32
    assert cff_expert_encoding.get_code("Psmall") == 112
    assert cff_expert_encoding.get_code("Ucircumflexsmall") == 251


def test_cff_standard_encoding() -> None:
    cff_standard_encoding = CFFStandardEncoding.get_instance()
    # check some randomly chosen mappings
    assert cff_standard_encoding.get_name(0) == ".notdef"
    assert cff_standard_encoding.get_name(32) == "space"
    assert cff_standard_encoding.get_name(112) == "p"
    assert cff_standard_encoding.get_name(251) == "germandbls"
    assert cff_standard_encoding.get_code("space") == 32
    assert cff_standard_encoding.get_code("p") == 112
    assert cff_standard_encoding.get_code("germandbls") == 251
