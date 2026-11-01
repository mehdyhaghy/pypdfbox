from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .cid_system_info import CIDSystemInfo
    from .file_system_font_provider import FileSystemFontProvider
    from .font_cache import FontCache
    from .font_mapper_impl import FontMapperImpl
    from .font_match import FontMatch
    from .fs_font_info import FSFontInfo
    from .pd_cid_font import PDCIDFont
    from .pd_cid_font_type0 import PDCIDFontType0
    from .pd_cid_font_type2 import PDCIDFontType2
    from .pd_cid_font_type2_embedder import PDCIDFontType2Embedder
    from .pd_cid_system_info import PDCIDSystemInfo
    from .pd_font import PDFont
    from .pd_font_descriptor import PDFontDescriptor
    from .pd_font_factory import PDFontFactory
    from .pd_font_like import PDFontLike
    from .pd_mm_type1_font import PDMMType1Font
    from .pd_simple_font import PDSimpleFont
    from .pd_true_type_font import PDTrueTypeFont
    from .pd_true_type_font_embedder import PDTrueTypeFontEmbedder
    from .pd_type0_font import PDType0Font
    from .pd_type1_font import PDType1Font
    from .pd_type1_font_embedder import PDType1FontEmbedder
    from .pd_type1c_font import PDType1CFont
    from .pd_type3_char_proc import PDType3CharProc
    from .pd_type3_font import PDType3Font
    from .pd_vector_font import PDVectorFont
    from .standard14_fonts import Standard14Fonts
    from .subsetter import Subsetter
    from .to_unicode_writer import ToUnicodeWriter
    from .true_type_embedder import TrueTypeEmbedder
    from .uni_util import (
        UniUtil,
        get_uni_name_of_code_point,
    )
    from .vertical_displacement_range import VerticalDisplacementRange

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CIDSystemInfo": ".cid_system_info",
        "FileSystemFontProvider": ".file_system_font_provider",
        "FontCache": ".font_cache",
        "FontMapperImpl": ".font_mapper_impl",
        "FontMatch": ".font_match",
        "FSFontInfo": ".fs_font_info",
        "PDCIDFont": ".pd_cid_font",
        "PDCIDFontType0": ".pd_cid_font_type0",
        "PDCIDFontType2": ".pd_cid_font_type2",
        "PDCIDFontType2Embedder": ".pd_cid_font_type2_embedder",
        "PDCIDSystemInfo": ".pd_cid_system_info",
        "PDFont": ".pd_font",
        "PDFontDescriptor": ".pd_font_descriptor",
        "PDFontFactory": ".pd_font_factory",
        "PDFontLike": ".pd_font_like",
        "PDMMType1Font": ".pd_mm_type1_font",
        "PDSimpleFont": ".pd_simple_font",
        "PDTrueTypeFont": ".pd_true_type_font",
        "PDTrueTypeFontEmbedder": ".pd_true_type_font_embedder",
        "PDType0Font": ".pd_type0_font",
        "PDType1Font": ".pd_type1_font",
        "PDType1FontEmbedder": ".pd_type1_font_embedder",
        "PDType1CFont": ".pd_type1c_font",
        "PDType3CharProc": ".pd_type3_char_proc",
        "PDType3Font": ".pd_type3_font",
        "PDVectorFont": ".pd_vector_font",
        "Standard14Fonts": ".standard14_fonts",
        "Subsetter": ".subsetter",
        "ToUnicodeWriter": ".to_unicode_writer",
        "TrueTypeEmbedder": ".true_type_embedder",
        "UniUtil": ".uni_util",
        "get_uni_name_of_code_point": ".uni_util",
        "VerticalDisplacementRange": ".vertical_displacement_range",
    },
)

__all__ = [
    "CIDSystemInfo",
    "FSFontInfo",
    "FileSystemFontProvider",
    "FontCache",
    "FontMapperImpl",
    "FontMatch",
    "PDCIDFont",
    "PDCIDFontType0",
    "PDCIDFontType2",
    "PDCIDFontType2Embedder",
    "PDCIDSystemInfo",
    "PDFont",
    "PDFontDescriptor",
    "PDFontFactory",
    "PDFontLike",
    "PDMMType1Font",
    "PDSimpleFont",
    "PDTrueTypeFont",
    "PDTrueTypeFontEmbedder",
    "PDType0Font",
    "PDType1CFont",
    "PDType1Font",
    "PDType1FontEmbedder",
    "PDType3CharProc",
    "PDType3Font",
    "PDVectorFont",
    "Standard14Fonts",
    "Subsetter",
    "ToUnicodeWriter",
    "TrueTypeEmbedder",
    "UniUtil",
    "VerticalDisplacementRange",
    "get_uni_name_of_code_point",
]
