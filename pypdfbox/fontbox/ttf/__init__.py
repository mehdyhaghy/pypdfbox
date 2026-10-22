from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .cff_table import CFFTable
    from .cmap_lookup import CmapLookup
    from .cmap_subtable import CmapSubtable
    from .control_value_program_table import ControlValueProgramTable
    from .control_value_table import ControlValueTable
    from .digital_signature_table import DigitalSignatureTable
    from .font_program_table import FontProgramTable
    from .gasp_table import GaspTable
    from .glyf_composite_comp import GlyfCompositeComp
    from .glyf_composite_descript import GlyfCompositeDescript
    from .glyf_descript import GlyfDescript
    from .glyf_simple_descript import GlyfSimpleDescript
    from .glyph_data import (
        BoundingBox,
        GlyphData,
        GlyphDescription,
    )
    from .glyph_positioning_table import GlyphPositioningTable
    from .glyph_renderer import GlyphRenderer
    from .glyph_substitution_table import GlyphSubstitutionTable
    from .glyph_table import GlyphTable
    from .header_table import HeaderTable
    from .horizontal_header_table import HorizontalHeaderTable
    from .horizontal_metrics_table import HorizontalMetricsTable
    from .index_to_location_table import IndexToLocationTable
    from .kerning_subtable import KerningSubtable
    from .kerning_table import KerningTable
    from .maximum_profile_table import MaximumProfileTable
    from .name_record import NameRecord
    from .naming_table import NamingTable
    from .open_type_font import OpenTypeFont
    from .os2_windows_metrics_table import OS2WindowsMetricsTable
    from .otf_parser import OTFParser
    from .otl_table import OTLTable
    from .post_script_table import PostScriptTable
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import (
        MemoryTTFDataStream,
        RandomAccessReadDataStream,
        TTFDataStream,
    )
    from .ttf_parser import TTFParser
    from .ttf_subsetter import TTFSubsetter
    from .ttf_table import TTFTable
    from .vertical_header_table import VerticalHeaderTable
    from .vertical_metrics_table import VerticalMetricsTable

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CFFTable": ".cff_table",
        "CmapLookup": ".cmap_lookup",
        "CmapSubtable": ".cmap_subtable",
        "ControlValueProgramTable": ".control_value_program_table",
        "ControlValueTable": ".control_value_table",
        "DigitalSignatureTable": ".digital_signature_table",
        "FontProgramTable": ".font_program_table",
        "GaspTable": ".gasp_table",
        "GlyfCompositeComp": ".glyf_composite_comp",
        "GlyfCompositeDescript": ".glyf_composite_descript",
        "GlyfDescript": ".glyf_descript",
        "GlyfSimpleDescript": ".glyf_simple_descript",
        "BoundingBox": ".glyph_data",
        "GlyphData": ".glyph_data",
        "GlyphDescription": ".glyph_data",
        "GlyphPositioningTable": ".glyph_positioning_table",
        "GlyphRenderer": ".glyph_renderer",
        "GlyphSubstitutionTable": ".glyph_substitution_table",
        "GlyphTable": ".glyph_table",
        "HeaderTable": ".header_table",
        "HorizontalHeaderTable": ".horizontal_header_table",
        "HorizontalMetricsTable": ".horizontal_metrics_table",
        "IndexToLocationTable": ".index_to_location_table",
        "KerningSubtable": ".kerning_subtable",
        "KerningTable": ".kerning_table",
        "MaximumProfileTable": ".maximum_profile_table",
        "NameRecord": ".name_record",
        "NamingTable": ".naming_table",
        "OpenTypeFont": ".open_type_font",
        "OS2WindowsMetricsTable": ".os2_windows_metrics_table",
        "OTFParser": ".otf_parser",
        "OTLTable": ".otl_table",
        "PostScriptTable": ".post_script_table",
        "TrueTypeFont": ".true_type_font",
        "MemoryTTFDataStream": ".ttf_data_stream",
        "RandomAccessReadDataStream": ".ttf_data_stream",
        "TTFDataStream": ".ttf_data_stream",
        "TTFParser": ".ttf_parser",
        "TTFSubsetter": ".ttf_subsetter",
        "TTFTable": ".ttf_table",
        "VerticalHeaderTable": ".vertical_header_table",
        "VerticalMetricsTable": ".vertical_metrics_table",
    },
)

__all__ = [
    "BoundingBox",
    "CFFTable",
    "CmapLookup",
    "CmapSubtable",
    "ControlValueProgramTable",
    "ControlValueTable",
    "DigitalSignatureTable",
    "FontProgramTable",
    "GaspTable",
    "GlyfCompositeComp",
    "GlyfCompositeDescript",
    "GlyfDescript",
    "GlyfSimpleDescript",
    "GlyphData",
    "GlyphDescription",
    "GlyphPositioningTable",
    "GlyphRenderer",
    "GlyphSubstitutionTable",
    "GlyphTable",
    "HeaderTable",
    "HorizontalHeaderTable",
    "HorizontalMetricsTable",
    "IndexToLocationTable",
    "KerningSubtable",
    "KerningTable",
    "MaximumProfileTable",
    "MemoryTTFDataStream",
    "NameRecord",
    "NamingTable",
    "OS2WindowsMetricsTable",
    "OTFParser",
    "OTLTable",
    "OpenTypeFont",
    "PostScriptTable",
    "RandomAccessReadDataStream",
    "TTFDataStream",
    "TTFParser",
    "TTFSubsetter",
    "TTFTable",
    "TrueTypeFont",
    "VerticalHeaderTable",
    "VerticalMetricsTable",
]
