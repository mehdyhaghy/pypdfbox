"""UI primitives for the Tkinter-based pypdfbox debugger.

Mirrors ``org.apache.pdfbox.debugger.ui``. Class names and public method
signatures are preserved (camelCase only converted to snake_case) so PDFBox
developers can navigate the port by muscle memory.
"""

from .array_entry import ArrayEntry
from .debug_log import DebugLog
from .document_entry import DocumentEntry
from .error_dialog import ErrorDialog
from .file_open_save_dialog import FileOpenSaveDialog
from .high_resolution_image_icon import HighResolutionImageIcon
from .image_type_menu import ImageTypeMenu
from .image_util import ImageUtil
from .log_dialog import LogDialog
from .map_entry import MapEntry
from .menu_base import MenuBase
from .osx_adapter import OSXAdapter
from .page_entry import PageEntry
from .pdf_tree_cell_renderer import PDFTreeCellRenderer
from .pdf_tree_model import PDFTreeModel
from .print_dpi_menu import PrintDpiMenu
from .reader_bottom_panel import ReaderBottomPanel
from .recent_files import RecentFiles
from .render_destination_menu import RenderDestinationMenu
from .rotation_menu import RotationMenu
from .text_dialog import TextDialog
from .text_stripper_menu import TextStripperMenu
from .tree import Tree
from .tree_view_menu import TreeViewMenu
from .view_menu import ViewMenu
from .window_prefs import WindowPrefs
from .xref_entries import XrefEntries
from .xref_entry import XrefEntry
from .zoom_menu import ZoomMenu

__all__ = [
    "ArrayEntry",
    "DebugLog",
    "DocumentEntry",
    "ErrorDialog",
    "FileOpenSaveDialog",
    "HighResolutionImageIcon",
    "ImageTypeMenu",
    "ImageUtil",
    "LogDialog",
    "MapEntry",
    "MenuBase",
    "OSXAdapter",
    "PDFTreeCellRenderer",
    "PDFTreeModel",
    "PageEntry",
    "PrintDpiMenu",
    "ReaderBottomPanel",
    "RecentFiles",
    "RenderDestinationMenu",
    "RotationMenu",
    "TextDialog",
    "TextStripperMenu",
    "Tree",
    "TreeViewMenu",
    "ViewMenu",
    "WindowPrefs",
    "XrefEntries",
    "XrefEntry",
    "ZoomMenu",
]
