from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .fdf_annotation import FDFAnnotation
    from .fdf_annotation_caret import FDFAnnotationCaret
    from .fdf_annotation_circle import FDFAnnotationCircle
    from .fdf_annotation_file_attachment import FDFAnnotationFileAttachment
    from .fdf_annotation_free_text import FDFAnnotationFreeText
    from .fdf_annotation_highlight import FDFAnnotationHighlight
    from .fdf_annotation_ink import FDFAnnotationInk
    from .fdf_annotation_line import FDFAnnotationLine
    from .fdf_annotation_link import FDFAnnotationLink
    from .fdf_annotation_polygon import FDFAnnotationPolygon
    from .fdf_annotation_polyline import FDFAnnotationPolyline
    from .fdf_annotation_sound import FDFAnnotationSound
    from .fdf_annotation_square import FDFAnnotationSquare
    from .fdf_annotation_squiggly import FDFAnnotationSquiggly
    from .fdf_annotation_stamp import FDFAnnotationStamp
    from .fdf_annotation_strike_out import FDFAnnotationStrikeOut
    from .fdf_annotation_text import FDFAnnotationText
    from .fdf_annotation_text_markup import FDFAnnotationTextMarkup
    from .fdf_annotation_underline import FDFAnnotationUnderline
    from .fdf_catalog import FDFCatalog
    from .fdf_dictionary import FDFDictionary
    from .fdf_document import FDFDocument
    from .fdf_field import FDFField
    from .fdf_java_script import FDFJavaScript
    from .fdf_option_element import FDFOptionElement
    from .fdf_page import FDFPage
    from .fdf_page_info import FDFPageInfo
    from .fdf_template import FDFTemplate
    from .fdf_utils import FDFUtils

__getattr__, __dir__ = _attach(
    __name__,
    {
        "FDFAnnotation": ".fdf_annotation",
        "FDFAnnotationCaret": ".fdf_annotation_caret",
        "FDFAnnotationCircle": ".fdf_annotation_circle",
        "FDFAnnotationFileAttachment": ".fdf_annotation_file_attachment",
        "FDFAnnotationFreeText": ".fdf_annotation_free_text",
        "FDFAnnotationHighlight": ".fdf_annotation_highlight",
        "FDFAnnotationInk": ".fdf_annotation_ink",
        "FDFAnnotationLine": ".fdf_annotation_line",
        "FDFAnnotationLink": ".fdf_annotation_link",
        "FDFAnnotationPolygon": ".fdf_annotation_polygon",
        "FDFAnnotationPolyline": ".fdf_annotation_polyline",
        "FDFAnnotationSound": ".fdf_annotation_sound",
        "FDFAnnotationSquare": ".fdf_annotation_square",
        "FDFAnnotationSquiggly": ".fdf_annotation_squiggly",
        "FDFAnnotationStamp": ".fdf_annotation_stamp",
        "FDFAnnotationStrikeOut": ".fdf_annotation_strike_out",
        "FDFAnnotationText": ".fdf_annotation_text",
        "FDFAnnotationTextMarkup": ".fdf_annotation_text_markup",
        "FDFAnnotationUnderline": ".fdf_annotation_underline",
        "FDFCatalog": ".fdf_catalog",
        "FDFDictionary": ".fdf_dictionary",
        "FDFDocument": ".fdf_document",
        "FDFField": ".fdf_field",
        "FDFJavaScript": ".fdf_java_script",
        "FDFOptionElement": ".fdf_option_element",
        "FDFPage": ".fdf_page",
        "FDFPageInfo": ".fdf_page_info",
        "FDFTemplate": ".fdf_template",
        "FDFUtils": ".fdf_utils",
    },
)

__all__ = [
    "FDFAnnotation",
    "FDFAnnotationCaret",
    "FDFAnnotationCircle",
    "FDFAnnotationFileAttachment",
    "FDFAnnotationFreeText",
    "FDFAnnotationHighlight",
    "FDFAnnotationInk",
    "FDFAnnotationLine",
    "FDFAnnotationLink",
    "FDFAnnotationPolygon",
    "FDFAnnotationPolyline",
    "FDFAnnotationSound",
    "FDFAnnotationSquare",
    "FDFAnnotationSquiggly",
    "FDFAnnotationStamp",
    "FDFAnnotationStrikeOut",
    "FDFAnnotationText",
    "FDFAnnotationTextMarkup",
    "FDFAnnotationUnderline",
    "FDFCatalog",
    "FDFDictionary",
    "FDFDocument",
    "FDFField",
    "FDFJavaScript",
    "FDFOptionElement",
    "FDFPage",
    "FDFPageInfo",
    "FDFTemplate",
    "FDFUtils",
]
