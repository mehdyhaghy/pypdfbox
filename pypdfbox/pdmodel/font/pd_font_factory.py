from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream

from .pd_cid_font_type0 import PDCIDFontType0
from .pd_font import PDFont
from .pd_mm_type1_font import PDMMType1Font
from .pd_true_type_font import PDTrueTypeFont
from .pd_type0_font import PDType0Font
from .pd_type1_font import PDType1Font
from .pd_type1c_font import PDType1CFont
from .pd_type3_font import PDType3Font

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_TYPE1C: str = "Type1C"
_CID_FONT_TYPE0C: str = "CIDFontType0C"


def _font_file3_subtype(font_dict: COSDictionary) -> str | None:
    """Return ``font_dict /FontDescriptor /FontFile3 /Subtype`` as a name
    string, or ``None`` if any link in the chain is absent or the wrong
    type. Uses typed accessors only — does not assume any particular
    dict layout beyond what ``COSDictionary`` exposes.
    """
    descriptor = font_dict.get_dictionary_object(_FONT_DESCRIPTOR)
    if not isinstance(descriptor, COSDictionary):
        return None
    font_file3 = descriptor.get_dictionary_object(_FONT_FILE3)
    if not isinstance(font_file3, COSStream):
        return None
    return font_file3.get_name(_SUBTYPE)


class PDFontFactory:
    """Static dispatch from a font ``COSDictionary`` to the right
    ``PDFont`` subclass, keyed on ``/Subtype`` (with ``/FontDescriptor
    /FontFile3 /Subtype`` consulted to disambiguate Type1C / CIDFontType0C
    embedded CFF programs). Mirrors PDFBox
    ``PDFontFactory.createFont(COSDictionary)``.
    """

    @staticmethod
    def create_font(font_dict: COSDictionary) -> PDFont | None:
        if font_dict is None:
            return None
        if not isinstance(font_dict, COSDictionary):
            raise TypeError(
                f"PDFontFactory.create_font expects COSDictionary, "
                f"got {type(font_dict).__name__}"
            )
        sub_type = font_dict.get_name(_SUBTYPE)
        if sub_type == PDType1Font.SUB_TYPE:
            # /Type1 with /FontDescriptor /FontFile3 /Subtype /Type1C is
            # a CFF-backed Type 1 font; route to PDType1CFont so the CFF
            # program is consulted for widths / outlines. Plain /Type1
            # (no FontFile3, or FontFile3 of /Subtype /OpenType etc.)
            # stays on PDType1Font.
            if _font_file3_subtype(font_dict) == _TYPE1C:
                return PDType1CFont(font_dict)
            return PDType1Font(font_dict)
        if sub_type == PDTrueTypeFont.SUB_TYPE:
            return PDTrueTypeFont(font_dict)
        if sub_type == PDType0Font.SUB_TYPE:
            return PDType0Font(font_dict)
        if sub_type == PDType3Font.SUB_TYPE:
            return PDType3Font(font_dict)
        if sub_type == PDMMType1Font.SUB_TYPE:
            return PDMMType1Font(font_dict)
        if sub_type == PDCIDFontType0.SUB_TYPE:
            # CIDFontType0 is normally reached via PDType0Font.get_descendant_font;
            # when it appears as the top-level /Subtype with a CFF /FontFile3
            # (/Subtype /CIDFontType0C) we wrap it directly. Without that
            # marker we leave it to the Type0 descendant path (returns None).
            if _font_file3_subtype(font_dict) == _CID_FONT_TYPE0C:
                return PDCIDFontType0(font_dict)
            return None
        # CIDFontType2 dispatch deferred (descendant of /Type0; reachable
        # via PDType0Font.get_descendant_font).
        return None


__all__ = ["PDFontFactory"]
