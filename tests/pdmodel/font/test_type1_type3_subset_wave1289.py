"""Type 1 / Type 3 font subsetting parity (Wave 1289).

Upstream PDFBox raises ``UnsupportedOperationException`` from
:py:meth:`PDSimpleFont.subset` / :py:meth:`PDSimpleFont.addToSubset`
("only TTF subsetting via PDType0Font is currently supported"). pypdfbox
keeps that upstream-faithful behaviour but overrides Type 1 and Type 3
with more specific messages (Type 1 — fontTools t1Lib has no public
subset entry point; Type 3 — glyphs are inline in ``/CharProcs`` so
subsetting has no meaning).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font


def _type1_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    d.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("Helvetica"),
    )
    return d


def _type3_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type3"))
    return d


def test_type1_will_be_subset_is_false() -> None:
    font = PDType1Font(_type1_dict())
    assert font.will_be_subset() is False


def test_type1_subset_raises_not_implemented_error() -> None:
    font = PDType1Font(_type1_dict())
    with pytest.raises(NotImplementedError, match="Type 1 font subsetting"):
        font.subset()


def test_type1_add_to_subset_raises_not_implemented_error() -> None:
    font = PDType1Font(_type1_dict())
    with pytest.raises(NotImplementedError, match="Type 1 font subsetting"):
        font.add_to_subset(0x41)


def test_type3_will_be_subset_is_false() -> None:
    font = PDType3Font(_type3_dict())
    assert font.will_be_subset() is False


def test_type3_subset_raises_with_charprocs_message() -> None:
    font = PDType3Font(_type3_dict())
    with pytest.raises(NotImplementedError, match="Type 3"):
        font.subset()


def test_type3_add_to_subset_raises_with_charprocs_message() -> None:
    font = PDType3Font(_type3_dict())
    with pytest.raises(NotImplementedError, match=r"/CharProcs"):
        font.add_to_subset(0x41)
