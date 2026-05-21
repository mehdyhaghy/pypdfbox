"""Ported from upstream PDFBox 3.0
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/documentinterchange/logicalstructure/PDStructureElementTest.java``.

This file covers the ``testSimple`` case (Java lines 168-214) — the
fixture-free portion of the upstream test that exercises the public
accessors / mutators on a fresh :class:`PDStructureElement`. The two
heavy fixture-driven tests (``testPDFBox4197`` and ``testClassMap``) are
ported in ``test_pd_structure_element.py`` against synthetic structure
trees.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDMarkedContentReference,
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent


def test_simple() -> None:
    """Mirrors upstream ``testSimple`` (Java lines 168-214)."""
    structure_element = PDStructureElement("S", None)
    assert structure_element.get_type() == PDStructureElement.TYPE
    assert structure_element.get_structure_type() == "S"
    assert structure_element.get_parent() is None

    structure_element.set_structure_type("T")
    assert structure_element.get_structure_type() == "T"

    structure_element.set_element_identifier("Ident")
    assert structure_element.get_element_identifier() == "Ident"

    structure_element.set_revision_number(33)
    assert structure_element.get_revision_number() == 33

    structure_element.increment_revision_number()
    assert structure_element.get_revision_number() == 34

    # Upstream: assertThrows(IllegalArgumentException, ...);
    # pypdfbox raises ``ValueError`` (Python's closest analogue).
    with pytest.raises(ValueError):
        structure_element.set_revision_number(-1)

    structure_element.set_title("Title")
    assert structure_element.get_title() == "Title"

    structure_element.set_language("Klingon")
    assert structure_element.get_language() == "Klingon"

    structure_element.set_alternate_description("Alto")
    assert structure_element.get_alternate_description() == "Alto"

    structure_element.set_actual_text("Actual")
    assert structure_element.get_actual_text() == "Actual"

    structure_element.set_expanded_form("ExpF")
    assert structure_element.get_expanded_form() == "ExpF"

    # appendKid(-1) — MCID rejection.
    with pytest.raises(ValueError):
        structure_element.append_kid(-1)

    structure_element.append_kid(0)

    mcr1 = PDMarkedContentReference()
    mcr1.set_mcid(1)
    structure_element.append_kid(mcr1)

    mcr2 = PDMarkedContentReference()
    mcr2.set_mcid(2)
    mc2 = PDMarkedContent.create(COSName.get_pdf_name("S"), mcr2.get_cos_object())
    structure_element.append_kid(mc2)

    # An MCR with /MCID = -1 is illegal: upstream goes through
    # ``setInt`` to set it post-construction (the setter validates).
    mcr_sub_zero = PDMarkedContentReference()
    with pytest.raises(ValueError):
        mcr_sub_zero.set_mcid(-1)
    mcr_sub_zero.get_cos_object().set_int(COSName.get_pdf_name("MCID"), -1)
    mc_sub_zero = PDMarkedContent.create(COSName.get_pdf_name("S"), mcr_sub_zero.get_cos_object())
    with pytest.raises(ValueError):
        structure_element.append_kid(mc_sub_zero)

    kids = structure_element.get_kids()
    assert len(kids) == 3
    assert kids[0] == 0
    mcr1 = kids[1]
    assert (
        mcr1.get_cos_object().get_name_as_string(COSName.TYPE)
        == PDMarkedContentReference.TYPE
    )
    assert mcr1.get_mcid() == 1
    assert kids[2] == 2
