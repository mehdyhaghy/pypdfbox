from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .filtered_text_stripper import (
        AngleCollector,
        FilteredTextStripper,
        get_angle,
    )
    from .legacy_pdf_stream_engine import LegacyPDFStreamEngine
    from .line_item import LineItem
    from .pdf_marked_content_extractor import PDFMarkedContentExtractor
    from .pdf_text_stripper import PDFTextStripper
    from .pdf_text_stripper_by_area import PDFTextStripperByArea
    from .position_wrapper import PositionWrapper
    from .text_metrics import TextMetrics
    from .text_position import TextPosition
    from .text_position_comparator import TextPositionComparator
    from .word_with_text_positions import WordWithTextPositions

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AngleCollector": ".filtered_text_stripper",
        "FilteredTextStripper": ".filtered_text_stripper",
        "get_angle": ".filtered_text_stripper",
        "LegacyPDFStreamEngine": ".legacy_pdf_stream_engine",
        "LineItem": ".line_item",
        "PDFMarkedContentExtractor": ".pdf_marked_content_extractor",
        "PDFTextStripper": ".pdf_text_stripper",
        "PDFTextStripperByArea": ".pdf_text_stripper_by_area",
        "PositionWrapper": ".position_wrapper",
        "TextMetrics": ".text_metrics",
        "TextPosition": ".text_position",
        "TextPositionComparator": ".text_position_comparator",
        "WordWithTextPositions": ".word_with_text_positions",
    },
)

__all__ = [
    "AngleCollector",
    "FilteredTextStripper",
    "LegacyPDFStreamEngine",
    "LineItem",
    "PDFMarkedContentExtractor",
    "PDFTextStripper",
    "PDFTextStripperByArea",
    "PositionWrapper",
    "TextMetrics",
    "TextPosition",
    "TextPositionComparator",
    "WordWithTextPositions",
    "get_angle",
]
