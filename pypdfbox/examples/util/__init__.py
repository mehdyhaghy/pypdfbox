"""Ports of ``org.apache.pdfbox.examples.util`` — utility examples
demonstrating text extraction, image/text location reporting, merging,
watermarking, and page splitting.

Each module mirrors a single upstream class one-to-one (class name
preserved, method names ``camelCase -> snake_case``)."""

from pypdfbox.examples.util.add_watermark_text import AddWatermarkText
from pypdfbox.examples.util.connected_input_stream import ConnectedInputStream
from pypdfbox.examples.util.draw_print_text_locations import DrawPrintTextLocations
from pypdfbox.examples.util.extract_text_by_area import ExtractTextByArea
from pypdfbox.examples.util.extract_text_simple import ExtractTextSimple
from pypdfbox.examples.util.pdf_highlighter import PDFHighlighter
from pypdfbox.examples.util.pdf_merger_example import PDFMergerExample
from pypdfbox.examples.util.print_image_locations import PrintImageLocations
from pypdfbox.examples.util.print_text_colors import PrintTextColors
from pypdfbox.examples.util.print_text_locations import PrintTextLocations
from pypdfbox.examples.util.remove_all_text import RemoveAllText
from pypdfbox.examples.util.split_booklet import SplitBooklet

__all__ = [
    "AddWatermarkText",
    "ConnectedInputStream",
    "DrawPrintTextLocations",
    "ExtractTextByArea",
    "ExtractTextSimple",
    "PDFHighlighter",
    "PDFMergerExample",
    "PrintImageLocations",
    "PrintTextColors",
    "PrintTextLocations",
    "RemoveAllText",
    "SplitBooklet",
]
