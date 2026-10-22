"""UI primitives for the Tkinter-based pypdfbox debugger.

Mirrors ``org.apache.pdfbox.debugger.ui``. Class names and public method
signatures are preserved (camelCase only converted to snake_case) so PDFBox
developers can navigate the port by muscle memory.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
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
    from .pdf_tree_cell_renderer import (
        OverlayIcon,
        PDFTreeCellRenderer,
    )
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

__getattr__, __dir__ = _attach(
    __name__,
    {
        "ArrayEntry": ".array_entry",
        "DebugLog": ".debug_log",
        "DocumentEntry": ".document_entry",
        "ErrorDialog": ".error_dialog",
        "FileOpenSaveDialog": ".file_open_save_dialog",
        "HighResolutionImageIcon": ".high_resolution_image_icon",
        "ImageTypeMenu": ".image_type_menu",
        "ImageUtil": ".image_util",
        "LogDialog": ".log_dialog",
        "MapEntry": ".map_entry",
        "MenuBase": ".menu_base",
        "OSXAdapter": ".osx_adapter",
        "PageEntry": ".page_entry",
        "OverlayIcon": ".pdf_tree_cell_renderer",
        "PDFTreeCellRenderer": ".pdf_tree_cell_renderer",
        "PDFTreeModel": ".pdf_tree_model",
        "PrintDpiMenu": ".print_dpi_menu",
        "ReaderBottomPanel": ".reader_bottom_panel",
        "RecentFiles": ".recent_files",
        "RenderDestinationMenu": ".render_destination_menu",
        "RotationMenu": ".rotation_menu",
        "TextDialog": ".text_dialog",
        "TextStripperMenu": ".text_stripper_menu",
        "Tree": ".tree",
        "TreeViewMenu": ".tree_view_menu",
        "ViewMenu": ".view_menu",
        "WindowPrefs": ".window_prefs",
        "XrefEntries": ".xref_entries",
        "XrefEntry": ".xref_entry",
        "ZoomMenu": ".zoom_menu",
    },
)

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
    "OverlayIcon",
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
