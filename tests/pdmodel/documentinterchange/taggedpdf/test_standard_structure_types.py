"""Hand-written tests for :class:`StandardStructureTypes`.

Mirrors the upstream Java definition at ``pdfbox/src/main/java/org/apache/
pdfbox/pdmodel/documentinterchange/taggedpdf/StandardStructureTypes.java``
(PDFBox 3.0). The upstream class is a non-instantiable constants holder that
declares one ``public static final String`` per standard structure type and
exposes a sorted ``types`` list gathered reflectively from those fields.

PDFBox 3.0 ships no dedicated ``StandardStructureTypesTest`` Java file, so
these are hand-written and cover the constant values, the sorted ``types``
collection, and the non-instantiable contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.documentinterchange.taggedpdf import StandardStructureTypes


def test_grouping_element_constants() -> None:
    assert StandardStructureTypes.DOCUMENT == "Document"
    assert StandardStructureTypes.PART == "Part"
    assert StandardStructureTypes.ART == "Art"
    assert StandardStructureTypes.SECT == "Sect"
    assert StandardStructureTypes.DIV == "Div"
    assert StandardStructureTypes.BLOCK_QUOTE == "BlockQuote"
    assert StandardStructureTypes.CAPTION == "Caption"
    assert StandardStructureTypes.TOC == "TOC"
    assert StandardStructureTypes.TOCI == "TOCI"
    assert StandardStructureTypes.INDEX == "Index"
    assert StandardStructureTypes.NON_STRUCT == "NonStruct"
    assert StandardStructureTypes.PRIVATE == "Private"


def test_block_level_element_constants() -> None:
    assert StandardStructureTypes.P == "P"
    assert StandardStructureTypes.H == "H"
    assert StandardStructureTypes.H1 == "H1"
    assert StandardStructureTypes.H6 == "H6"
    assert StandardStructureTypes.L == "L"
    assert StandardStructureTypes.LI == "LI"
    assert StandardStructureTypes.LBL == "Lbl"
    assert StandardStructureTypes.L_BODY == "LBody"
    assert StandardStructureTypes.TABLE == "Table"
    assert StandardStructureTypes.TR == "TR"
    assert StandardStructureTypes.TH == "TH"
    assert StandardStructureTypes.TD == "TD"
    assert StandardStructureTypes.T_HEAD == "THead"
    assert StandardStructureTypes.T_BODY == "TBody"
    assert StandardStructureTypes.T_FOOT == "TFoot"


def test_inline_level_element_constants() -> None:
    assert StandardStructureTypes.SPAN == "Span"
    assert StandardStructureTypes.QUOTE == "Quote"
    assert StandardStructureTypes.NOTE == "Note"
    assert StandardStructureTypes.REFERENCE == "Reference"
    assert StandardStructureTypes.BIB_ENTRY == "BibEntry"
    assert StandardStructureTypes.CODE == "Code"
    assert StandardStructureTypes.LINK == "Link"
    assert StandardStructureTypes.ANNOT == "Annot"
    assert StandardStructureTypes.RUBY == "Ruby"
    assert StandardStructureTypes.RB == "RB"
    assert StandardStructureTypes.RT == "RT"
    assert StandardStructureTypes.RP == "RP"
    assert StandardStructureTypes.WARICHU == "Warichu"
    assert StandardStructureTypes.WT == "WT"
    assert StandardStructureTypes.WP == "WP"


def test_illustration_element_constants() -> None:
    # Upstream preserves the capitalised ``Figure`` field name.
    assert StandardStructureTypes.Figure == "Figure"
    assert StandardStructureTypes.FORMULA == "Formula"
    assert StandardStructureTypes.FORM == "Form"


def test_types_is_sorted_and_complete() -> None:
    types = StandardStructureTypes.types
    # 49 standard structure type constants are declared upstream (one
    # ``public static final String`` per type); ``types`` collects them all.
    assert len(types) == 49
    assert types == sorted(types)
    # Spot-check membership of representatives from each group.
    for value in ("Document", "P", "H1", "Span", "Figure", "Form", "Table"):
        assert value in types
    # Sorted order places "Annot" first and "Warichu" last among these.
    assert types[0] == "Annot"


def test_types_has_no_duplicates() -> None:
    types = StandardStructureTypes.types
    assert len(types) == len(set(types))


def test_not_instantiable() -> None:
    with pytest.raises(TypeError):
        StandardStructureTypes()
