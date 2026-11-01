from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .base_parser import BaseParser
    from .brute_force_parser import BruteForceParser
    from .cos_parser import COSParser
    from .endstream_filter_stream import EndstreamFilterStream
    from .fdf_parser import FDFParser
    from .linearization_hint_table import (
        HintTableParseError,
        PageOffsetEntry,
        PageOffsetHintHeader,
        PageOffsetHintTable,
        SharedObjectEntry,
        SharedObjectHintHeader,
        SharedObjectHintTable,
        ThumbnailEntry,
        ThumbnailHintHeader,
        ThumbnailHintTable,
        parse_page_offset_hint_header,
        parse_page_offset_hint_table,
        parse_shared_object_hint_header,
        parse_shared_object_hint_table,
        parse_thumbnail_hint_header,
        parse_thumbnail_hint_table,
    )
    from .object_numbers import ObjectNumbers
    from .parse_error import PDFParseError
    from .pdf_object_stream_parser import PDFObjectStreamParser
    from .pdf_parser import PDFParser
    from .pdf_stream_parser import (
        Operator,
        PDFStreamParser,
    )
    from .pdf_xref_stream import PDFXRefStream
    from .pdf_xref_stream_parser import PDFXrefStreamParser
    from .xref_parser import XrefParser
    from .xref_trailer_obj import XrefTrailerObj
    from .xref_trailer_resolver import (
        XrefEntry,
        XrefTrailerResolver,
        XrefType,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BaseParser": ".base_parser",
        "BruteForceParser": ".brute_force_parser",
        "COSParser": ".cos_parser",
        "EndstreamFilterStream": ".endstream_filter_stream",
        "FDFParser": ".fdf_parser",
        "HintTableParseError": ".linearization_hint_table",
        "PageOffsetEntry": ".linearization_hint_table",
        "PageOffsetHintHeader": ".linearization_hint_table",
        "PageOffsetHintTable": ".linearization_hint_table",
        "SharedObjectEntry": ".linearization_hint_table",
        "SharedObjectHintHeader": ".linearization_hint_table",
        "SharedObjectHintTable": ".linearization_hint_table",
        "ThumbnailEntry": ".linearization_hint_table",
        "ThumbnailHintHeader": ".linearization_hint_table",
        "ThumbnailHintTable": ".linearization_hint_table",
        "parse_page_offset_hint_header": ".linearization_hint_table",
        "parse_page_offset_hint_table": ".linearization_hint_table",
        "parse_shared_object_hint_header": ".linearization_hint_table",
        "parse_shared_object_hint_table": ".linearization_hint_table",
        "parse_thumbnail_hint_header": ".linearization_hint_table",
        "parse_thumbnail_hint_table": ".linearization_hint_table",
        "ObjectNumbers": ".object_numbers",
        "PDFParseError": ".parse_error",
        "PDFObjectStreamParser": ".pdf_object_stream_parser",
        "PDFParser": ".pdf_parser",
        "Operator": ".pdf_stream_parser",
        "PDFStreamParser": ".pdf_stream_parser",
        "PDFXRefStream": ".pdf_xref_stream",
        "PDFXrefStreamParser": ".pdf_xref_stream_parser",
        "XrefParser": ".xref_parser",
        "XrefTrailerObj": ".xref_trailer_obj",
        "XrefEntry": ".xref_trailer_resolver",
        "XrefTrailerResolver": ".xref_trailer_resolver",
        "XrefType": ".xref_trailer_resolver",
    },
)

__all__ = [
    "BaseParser",
    "BruteForceParser",
    "COSParser",
    "EndstreamFilterStream",
    "FDFParser",
    "HintTableParseError",
    "ObjectNumbers",
    "Operator",
    "PDFObjectStreamParser",
    "PDFParseError",
    "PDFParser",
    "PDFStreamParser",
    "PDFXRefStream",
    "PDFXrefStreamParser",
    "PageOffsetEntry",
    "PageOffsetHintHeader",
    "PageOffsetHintTable",
    "SharedObjectEntry",
    "SharedObjectHintHeader",
    "SharedObjectHintTable",
    "ThumbnailEntry",
    "ThumbnailHintHeader",
    "ThumbnailHintTable",
    "XrefEntry",
    "XrefParser",
    "XrefTrailerObj",
    "XrefTrailerResolver",
    "XrefType",
    "parse_page_offset_hint_header",
    "parse_page_offset_hint_table",
    "parse_shared_object_hint_header",
    "parse_shared_object_hint_table",
    "parse_thumbnail_hint_header",
    "parse_thumbnail_hint_table",
]
