"""UI primitives for the Tkinter-based pypdfbox debugger.

Mirrors ``org.apache.pdfbox.debugger.ui``. Class names and public method
signatures are preserved (camelCase only converted to snake_case) so PDFBox
developers can navigate the port by muscle memory.
"""

from .array_entry import ArrayEntry
from .debug_log import DebugLog
from .document_entry import DocumentEntry
from .high_resolution_image_icon import HighResolutionImageIcon
from .image_util import ImageUtil
from .map_entry import MapEntry
from .page_entry import PageEntry
from .pdf_tree_model import PDFTreeModel
from .window_prefs import WindowPrefs
from .xref_entries import XrefEntries
from .xref_entry import XrefEntry

__all__ = [
    "ArrayEntry",
    "DebugLog",
    "DocumentEntry",
    "HighResolutionImageIcon",
    "ImageUtil",
    "MapEntry",
    "PDFTreeModel",
    "PageEntry",
    "WindowPrefs",
    "XrefEntries",
    "XrefEntry",
]
