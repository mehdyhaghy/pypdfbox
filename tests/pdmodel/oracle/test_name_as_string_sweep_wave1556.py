"""Differential audit for the get_name vs get_name_as_string parity-bug class.

Mirrors ``oracle/probes/NameAsStringSweepProbe.java`` against the live Apache
PDFBox 3.0.7 jar (wave 1556).

Across waves 1539-1555 we repeatedly found production accessors reading a
NAME-valued PDF dictionary key via ``COSDictionary.get_name(...)`` (COSName-only)
where upstream reads it via ``getNameAsString(...)`` (COSName OR COSString). Each
mismatch silently dropped a string-typed value to the default. This wave swept
the remaining occurrences. For every accessor that was changed, this test stores
the relevant key as a ``COSString`` — the value the old name-only reader would
drop — and pins the pypdfbox result equal to the live PDFBox oracle.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceNAttributes
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import PDAnnotationLine
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _put(dictionary: COSDictionary, key: str, value: str) -> None:
    """Store ``value`` as a COSString under ``key`` (the dropped-value case)."""
    dictionary.set_item(_N(key), COSString(value))


def _nz(value: str | bool | None) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


# Each entry: accessor id (matches the Java probe switch) -> pypdfbox callable.
def _encryption_filter() -> str | None:
    d = COSDictionary()
    _put(d, "Filter", "MyFilter")
    return PDEncryption(d).get_filter()


def _encryption_sub_filter() -> str | None:
    d = COSDictionary()
    _put(d, "SubFilter", "MySub")
    return PDEncryption(d).get_sub_filter()


def _font_type() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("Type1"))
    _put(d, "Type", "Font")
    return PDType1Font(d).get_type()


def _font_subtype() -> str | None:
    d = COSDictionary()
    _put(d, "Subtype", "Type1")
    d.set_item(_N("BaseFont"), _N("Helvetica"))
    return PDType1Font(d).get_sub_type()


def _font_base_font() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("Type1"))
    _put(d, "BaseFont", "Helvetica")
    return PDType1Font(d).get_name()


def _type0_base_font() -> str | None:
    descendant = COSDictionary()
    descendant.set_item(_N("Type"), _N("Font"))
    descendant.set_item(_N("Subtype"), _N("CIDFontType2"))
    descendant.set_item(_N("BaseFont"), _N("MyComposite"))
    cid_system_info = COSDictionary()
    cid_system_info.set_item(_N("Registry"), COSString("Adobe"))
    cid_system_info.set_item(_N("Ordering"), COSString("Identity"))
    cid_system_info.set_item(_N("Supplement"), COSInteger.get(0))
    descendant.set_item(_N("CIDSystemInfo"), cid_system_info)
    descendants = COSArray()
    descendants.add(descendant)
    d = COSDictionary()
    d.set_item(_N("Type"), _N("Font"))
    d.set_item(_N("Subtype"), _N("Type0"))
    d.set_item(_N("Encoding"), _N("Identity-H"))
    d.set_item(_N("DescendantFonts"), descendants)
    _put(d, "BaseFont", "MyComposite")
    return PDType0Font(d).get_base_font()


def _cid_base_font() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("CIDFontType2"))
    _put(d, "BaseFont", "MyCIDFont")
    return PDCIDFontType2(d, None).get_base_font()


def _type3_name() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("Type3"))
    _put(d, "Name", "MyType3")
    return PDType3Font(d).get_name()


def _font_stretch() -> str | None:
    d = COSDictionary()
    _put(d, "FontStretch", "Condensed")
    return PDFontDescriptor(d).get_font_stretch()


def _structure_type() -> str | None:
    d = COSDictionary()
    _put(d, "S", "Sect")
    return PDStructureElement(d).get_structure_type()


def _structure_node_type() -> str | None:
    d = COSDictionary()
    _put(d, "Type", "StructElem")
    return PDStructureElement(d).get_type()


def _markup_reply_type() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("Text"))
    _put(d, "RT", "Group")
    return PDAnnotationMarkup(d).get_reply_type()


def _markup_intent() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("Text"))
    _put(d, "IT", "LineArrow")
    return PDAnnotationMarkup(d).get_intent()


def _freetext_line_ending() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("FreeText"))
    _put(d, "LE", "OpenArrow")
    return PDAnnotationFreeText(d).get_line_ending_style()


def _line_caption_positioning() -> str | None:
    d = COSDictionary()
    d.set_item(_N("Subtype"), _N("Line"))
    _put(d, "CP", "Top")
    return PDAnnotationLine(d).get_caption_positioning()


def _border_effect_style() -> str | None:
    d = COSDictionary()
    _put(d, "S", "C")
    return PDBorderEffectDictionary(d).get_style()


def _device_n_is_n_channel() -> bool:
    d = COSDictionary()
    _put(d, "Subtype", "NChannel")
    return PDDeviceNAttributes(d).is_n_channel()


_ACCESSORS = {
    "encryption_filter": _encryption_filter,
    "encryption_sub_filter": _encryption_sub_filter,
    "font_type": _font_type,
    "font_subtype": _font_subtype,
    "font_base_font": _font_base_font,
    "type0_base_font": _type0_base_font,
    "cid_base_font": _cid_base_font,
    "type3_name": _type3_name,
    "font_stretch": _font_stretch,
    "structure_type": _structure_type,
    "structure_node_type": _structure_node_type,
    "markup_reply_type": _markup_reply_type,
    "markup_intent": _markup_intent,
    "freetext_line_ending": _freetext_line_ending,
    "line_caption_positioning": _line_caption_positioning,
    "border_effect_style": _border_effect_style,
    "device_n_is_n_channel": _device_n_is_n_channel,
}

# The string value each accessor must surface from its COSString-typed key. This
# is a value-level pin so the test also fails if pypdfbox regresses to the
# name-only reader (which would return the default / None / "S" instead).
_EXPECTED = {
    "encryption_filter": "MyFilter",
    "encryption_sub_filter": "MySub",
    "font_type": "Font",
    "font_subtype": "Type1",
    "font_base_font": "Helvetica",
    "type0_base_font": "MyComposite",
    "cid_base_font": "MyCIDFont",
    "type3_name": "MyType3",
    "font_stretch": "Condensed",
    "structure_type": "Sect",
    "structure_node_type": "StructElem",
    "markup_reply_type": "Group",
    "markup_intent": "LineArrow",
    "freetext_line_ending": "OpenArrow",
    "line_caption_positioning": "Top",
    "border_effect_style": "C",
    "device_n_is_n_channel": "true",
}


@pytest.mark.parametrize("accessor", sorted(_ACCESSORS))
def test_name_as_string_accessor_decodes_cos_string(accessor: str) -> None:
    """pypdfbox decodes a COSString-typed name key (not drop to the default)."""
    assert _nz(_ACCESSORS[accessor]()) == _EXPECTED[accessor]


@requires_oracle
@pytest.mark.parametrize("accessor", sorted(_ACCESSORS))
def test_name_as_string_accessor_matches_pdfbox(accessor: str) -> None:
    """pypdfbox equals the live Apache PDFBox 3.0.7 oracle for each accessor."""
    java = run_probe_text("NameAsStringSweepProbe", accessor).strip()
    assert java == f"value={_EXPECTED[accessor]}"
    assert _nz(_ACCESSORS[accessor]()) == _EXPECTED[accessor]
