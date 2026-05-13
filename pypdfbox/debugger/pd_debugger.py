"""Tkinter port of the top-level ``PDFDebugger`` shell.

Mirrors ``org.apache.pdfbox.debugger.PDFDebugger``. The Swing original
is a ``JFrame`` hosting a ``JSplitPane`` (COS tree on the left, detail
pane on the right) with a ``JMenuBar`` and a ``ReaderBottomPanel``
status bar. We translate the layout to ``ttk.PanedWindow`` +
``ttk.Treeview`` + ``tk.Menu``; the right-hand component is swapped
on each tree-selection-changed event to one of:

* :class:`PagePane` (page dictionaries),
* :class:`StreamPane` (content / image streams),
* :class:`HexEditor` (other non-content-stream binary),
* :class:`StringPane` (``COSString``),
* :class:`FontEncodingView` (font dictionaries, via
  :class:`FontEncodingPaneController`),
* :class:`CSDeviceN` / :class:`CSIndexed` / :class:`CSSeparation` /
  :class:`CSArrayBased` (colour-space arrays),
* :class:`FlagBitsPane` (flag-bearing dictionary entries),
* :class:`SignaturePane` (PKCS#7 signature ``/Contents``), or
* a generic ``ttk.Treeview`` "key=value" details panel.

The Swing original is wired against a CLI built on Picocli. The port
exposes the same surface via :meth:`PDFDebugger.main`, but the bulk
of the functionality is reusable as an embeddable Python widget:
construct a :class:`PDFDebugger` over any ``tk.Misc`` master, drive
:meth:`open_document` to load a PDF, and the panes update via the
standard ``<<TreeviewSelect>>`` virtual event.

Behavioural deviations from upstream are recorded in CHANGES.md:

* Printing (Swing ``PrinterJob``) is not ported — Python has no
  cross-platform printer API in the stdlib. The Print menu items
  exist but their handlers log a not-implemented warning.
* Reflection-based macOS hooks are replaced by the stdlib
  ``createcommand`` route in :class:`OSXAdapter`.
* Drag-and-drop (Swing ``TransferHandler``) is omitted; tkdnd is a
  third-party package not in scope for the port.
* The picocli-based CLI is replaced by ``argparse`` so ``main`` runs
  without external dependencies.
"""

from __future__ import annotations

import contextlib
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.debugger.colorpane.cs_array_based import CSArrayBased
from pypdfbox.debugger.colorpane.cs_device_n import CSDeviceN
from pypdfbox.debugger.colorpane.cs_indexed import CSIndexed
from pypdfbox.debugger.colorpane.cs_separation import CSSeparation
from pypdfbox.debugger.flagbitspane.flag_bits_pane import FlagBitsPane
from pypdfbox.debugger.fontencodingpane.font_encoding_pane_controller import (
    FontEncodingPaneController,
)
from pypdfbox.debugger.hexviewer.hex_view import HexView
from pypdfbox.debugger.pagepane.page_pane import PagePane
from pypdfbox.debugger.signaturepane.signature_pane import SignaturePane
from pypdfbox.debugger.streampane.stream_pane import StreamPane
from pypdfbox.debugger.stringpane.string_pane import StringPane
from pypdfbox.debugger.treestatus.tree_status import TreeStatus
from pypdfbox.debugger.treestatus.tree_status_pane import TreeStatusPane
from pypdfbox.debugger.ui.array_entry import ArrayEntry
from pypdfbox.debugger.ui.document_entry import DocumentEntry
from pypdfbox.debugger.ui.error_dialog import ErrorDialog
from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.osx_adapter import OSXAdapter
from pypdfbox.debugger.ui.page_entry import PageEntry
from pypdfbox.debugger.ui.pdf_tree_model import PDFTreeModel
from pypdfbox.debugger.ui.reader_bottom_panel import ReaderBottomPanel
from pypdfbox.debugger.ui.recent_files import RecentFiles
from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
from pypdfbox.debugger.ui.rotation_menu import RotationMenu
from pypdfbox.debugger.ui.tree import Tree
from pypdfbox.debugger.ui.tree_view_menu import TreeViewMenu
from pypdfbox.debugger.ui.view_menu import ViewMenu
from pypdfbox.debugger.ui.window_prefs import WindowPrefs
from pypdfbox.debugger.ui.xref_entries import XrefEntries
from pypdfbox.debugger.ui.xref_entry import XrefEntry
from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

if TYPE_CHECKING:
    from pypdfbox.pdmodel import PDDocument


_LOG = logging.getLogger(__name__)


def _is_mac_os() -> bool:
    """Return ``True`` iff we're running on macOS."""
    return sys.platform == "darwin"


# Color-space ``/Type`` first-array-entry names. Mirrors upstream
# ``PDFDebugger.SPECIALCOLORSPACES`` / ``OTHERCOLORSPACES``.
_SPECIAL_COLORSPACES: frozenset[str] = frozenset({"Indexed", "Separation", "DeviceN"})
_OTHER_COLORSPACES: frozenset[str] = frozenset(
    {"ICCBased", "Pattern", "CalGray", "CalRGB", "Lab"}
)


class PDFDebugger:
    """The top-level debugger shell.

    Instances are designed to be both used as a standalone application
    (via :py:meth:`main`) and embedded into a larger Tk application —
    pass any ``tk.Misc`` ``master`` and the debugger builds its widget
    tree as a child of that master.
    """

    TITLE = "Apache PDFBox Debugger"

    def __init__(
        self,
        master: tk.Misc | None = None,
        initial_view_mode: str | None = None,
    ) -> None:
        """Build the widget tree.

        :param master: parent widget. ``None`` means "use the implicit
            default root", typically created by :py:meth:`main`.
        :param initial_view_mode: optional tree-view mode string —
            one of :class:`TreeViewMenu`'s ``VIEW_*`` constants.
            Falls back to :attr:`TreeViewMenu.VIEW_PAGES` when ``None``
            or invalid.
        """
        self._master: tk.Misc = master if master is not None else _ensure_default_root()
        self._toplevel: tk.Misc = self._master
        # Track view mode locally so we don't depend on a TreeViewMenu
        # being instantiated for non-GUI tests.
        self._current_tree_view_mode = TreeViewMenu.VIEW_PAGES
        if initial_view_mode is not None and TreeViewMenu.is_valid_view_mode(
            initial_view_mode
        ):
            self._current_tree_view_mode = initial_view_mode

        self._document: PDDocument | None = None
        self._current_file_path: str | None = None

        # Persistent prefs / recent-files history. Mirrors upstream
        # ``WindowPrefs`` and ``RecentFiles``.
        self._window_prefs = WindowPrefs(self.__class__)
        self._recent_files = RecentFiles(self.__class__, 5)

        # Built lazily by :meth:`_init_menu_bar`.
        self._recent_files_menu: tk.Menu | None = None
        self._save_as_menu_index: int | None = None
        self._reopen_menu_index: int | None = None
        self._print_menu_index: int | None = None
        self._file_menu: tk.Menu | None = None
        self._find_menu: tk.Menu | None = None
        self._find_menu_index: int | None = None
        self._find_next_menu_index: int | None = None
        self._find_previous_menu_index: int | None = None
        self._edit_menu_index: int | None = None
        self._window_menu: tk.Menu | None = None

        # Build the body.
        self._main_frame = ttk.Frame(self._master)
        self._main_frame.pack(fill="both", expand=True)
        self._init_components()
        self._init_menu_bar()
        self._init_global_event_handlers()

        # Right-hand-side detail panel widget currently mounted.
        self._current_right_widget: tk.Widget | None = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _init_components(self) -> None:
        """Build the split-pane body + status bar."""
        # ttk.PanedWindow replaces JSplitPane(HORIZONTAL_SPLIT).
        self._paned = ttk.PanedWindow(self._main_frame, orient=tk.HORIZONTAL)

        # Tree on the left. We wrap it in a Frame so the TreeStatusPane
        # can sit *above* the tree (mirrors upstream's PAGE_START).
        left_frame = ttk.Frame(self._paned)
        self._tree = Tree(left_frame)
        self._tree_status_pane = TreeStatusPane(
            self._tree, node_lookup=self._tree.get_node
        )
        self._tree_status_pane.init()
        self._tree_status_pane.get_panel().pack(side="top", fill="x")
        tree_scroller = ttk.Scrollbar(
            left_frame, orient="vertical", command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=tree_scroller.set)
        tree_scroller.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        # Right-hand-side container — we ``forget`` and re-add a child
        # widget here on every selection change.
        self._right_frame = ttk.Frame(self._paned)

        self._paned.add(left_frame, weight=1)
        self._paned.add(self._right_frame, weight=3)
        self._paned.pack(fill="both", expand=True)

        # Status bar (Swing's ReaderBottomPanel) lives at the bottom.
        self._status_bar = ReaderBottomPanel(self._main_frame)
        self._status_bar.init()
        self._status_bar.pack(side="bottom", fill="x")

        # Wire the tree-selection event. Swing uses
        # ``addTreeSelectionListener``; Tk uses ``<<TreeviewSelect>>``.
        self._tree.bind(
            "<<TreeviewSelect>>", self._on_tree_selection_changed, add="+"
        )

        # Title and window-state restoration. ``_master`` is a Tk root or
        # Toplevel; ``ttk.Frame`` does not own ``title``.
        with contextlib.suppress(AttributeError, tk.TclError):
            self._master.title(self.TITLE)  # type: ignore[union-attr]

        with contextlib.suppress(AttributeError, tk.TclError):
            x, y, w, h = self._window_prefs.get_bounds()
            self._master.geometry(f"{w}x{h}+{x}+{y}")  # type: ignore[union-attr]

    def _init_menu_bar(self) -> None:
        """Construct the menubar and attach it to the toplevel."""
        # ``master`` may be a Frame embedded somewhere; ``winfo_toplevel``
        # always lands on the owning toplevel widget.
        toplevel = self._master.winfo_toplevel()
        self._toplevel = toplevel

        menubar = tk.Menu(toplevel)
        self._file_menu = self._create_file_menu(menubar)
        menubar.add_cascade(label="File", menu=self._file_menu, underline=0)

        edit_menu = self._create_edit_menu(menubar)
        menubar.add_cascade(label="Edit", menu=edit_menu, underline=0)
        self._edit_menu_index = menubar.index("end")

        # Reset the singleton ViewMenu so multiple tests can instantiate
        # the debugger without inheriting stale state.
        ViewMenu._reset_instance()  # noqa: SLF001
        view_menu = ViewMenu.get_instance(pdf_debugger=self, master=toplevel)
        menubar.add_cascade(label="View", menu=view_menu.get_menu(), underline=0)

        self._window_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Window", menu=self._window_menu, underline=0)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About PDFBox", command=self._show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu, underline=0)

        # Install on the toplevel.
        with contextlib.suppress(tk.TclError):
            toplevel.configure(menu=menubar)

        # Bind keyboard shortcuts (Cmd on macOS, Ctrl elsewhere).
        modifier = "Command" if _is_mac_os() else "Control"
        toplevel.bind_all(
            f"<{modifier}-o>", lambda _evt: self._open_menu_item_action_performed()
        )
        toplevel.bind_all(
            f"<{modifier}-u>", lambda _evt: self._open_url_menu_item_action_performed()
        )
        toplevel.bind_all(
            f"<{modifier}-r>", lambda _evt: self._reopen_menu_item_action_performed()
        )
        toplevel.bind_all(
            f"<{modifier}-f>", lambda _evt: self._find_menu_item_action_performed()
        )
        toplevel.bind_all(
            f"<{modifier}-p>", lambda _evt: self._print_menu_item_action_performed()
        )

    def _create_file_menu(self, parent: tk.Menu) -> tk.Menu:
        modifier = "Command" if _is_mac_os() else "Ctrl"
        file_menu = tk.Menu(parent, tearoff=0)
        file_menu.add_command(
            label="Open...",
            command=self._open_menu_item_action_performed,
            accelerator=f"{modifier}+O",
        )
        file_menu.add_command(
            label="Open URL...",
            command=self._open_url_menu_item_action_performed,
            accelerator=f"{modifier}+U",
        )
        file_menu.add_command(
            label="Reopen",
            command=self._reopen_menu_item_action_performed,
            accelerator=f"{modifier}+R",
            state="disabled",
        )
        self._reopen_menu_index = file_menu.index("end")

        self._recent_files_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(
            label="Open Recent", menu=self._recent_files_menu, state="disabled"
        )
        self._populate_recent_files_menu()

        file_menu.add_command(
            label="Save as...",
            command=self._save_as_menu_item_action_performed,
            state="disabled",
        )
        self._save_as_menu_index = file_menu.index("end")

        # Stream-saving entries (delegate to the right-hand pane when
        # available — see :meth:`_save_decoded_stream` /
        # :meth:`_save_raw_stream`).
        file_menu.add_command(
            label="Save Decoded Stream...",
            command=self._save_decoded_stream,
            state="disabled",
        )
        file_menu.add_command(
            label="Save Raw Stream...",
            command=self._save_raw_stream,
            state="disabled",
        )

        file_menu.add_separator()
        file_menu.add_command(
            label="Print",
            command=self._print_menu_item_action_performed,
            accelerator=f"{modifier}+P",
            state="disabled",
        )
        self._print_menu_index = file_menu.index("end")

        if not _is_mac_os():
            file_menu.add_separator()
            file_menu.add_command(
                label="Exit",
                command=self._exit_menu_item_action_performed,
                accelerator="Alt+F4",
            )
        return file_menu

    def _create_edit_menu(self, parent: tk.Menu) -> tk.Menu:
        modifier = "Command" if _is_mac_os() else "Ctrl"
        edit_menu = tk.Menu(parent, tearoff=0)
        edit_menu.add_command(label="Cut", state="disabled")
        edit_menu.add_command(label="Copy", state="disabled")
        edit_menu.add_command(label="Paste", state="disabled")
        edit_menu.add_command(label="Delete", state="disabled")
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Copy Tree Path",
            command=self._copy_tree_path,
        )
        edit_menu.add_separator()

        self._find_menu = tk.Menu(edit_menu, tearoff=0)
        self._find_menu.add_command(
            label="Find...",
            command=self._find_menu_item_action_performed,
            accelerator=f"{modifier}+F",
        )
        self._find_menu_index = self._find_menu.index("end")
        self._find_menu.add_command(
            label="Find Next",
            command=self._find_next_menu_item_action_performed,
            accelerator="Cmd+G" if _is_mac_os() else "F3",
        )
        self._find_next_menu_index = self._find_menu.index("end")
        self._find_menu.add_command(
            label="Find Previous",
            command=self._find_previous_menu_item_action_performed,
            accelerator="Cmd+Shift+G" if _is_mac_os() else "Shift+F3",
        )
        self._find_previous_menu_index = self._find_menu.index("end")
        edit_menu.add_cascade(label="Find", menu=self._find_menu, state="disabled")
        return edit_menu

    def _init_global_event_handlers(self) -> None:
        """Install macOS hooks via :class:`OSXAdapter` (no-op elsewhere)."""
        if not _is_mac_os():
            return
        OSXAdapter.register(
            self._toplevel,
            callbacks={
                "quit": self._exit_menu_item_action_performed,
                "about": self._show_about_dialog,
                "file": self._osx_open_file,
            },
        )

    # ------------------------------------------------------------------
    # Public API mirroring upstream
    # ------------------------------------------------------------------

    def get_tree_view_mode(self) -> str:
        """Return the active tree-view mode string."""
        return self._current_tree_view_mode

    def set_tree_view_mode(self, view_mode: str) -> None:
        """Update the active tree-view mode (no-op if invalid)."""
        if TreeViewMenu.is_valid_view_mode(view_mode):
            self._current_tree_view_mode = view_mode

    def has_document(self) -> bool:
        """Return ``True`` iff a document is currently open."""
        return self._document is not None

    def open_document(self, path: str | Path, password: str | bytes = "") -> None:
        """Load a PDF from ``path``. Mirrors upstream ``readPDFFile``."""
        self._read_pdf_file(str(path), password)

    def get_document(self) -> PDDocument | None:
        """Return the currently-loaded document, or ``None``."""
        return self._document

    def get_tree(self) -> Tree:
        """Return the underlying COS tree widget."""
        return self._tree

    def get_right_widget(self) -> tk.Widget | None:
        """Return the currently mounted detail-pane widget."""
        return self._current_right_widget

    def get_status_bar(self) -> ReaderBottomPanel:
        """Return the bottom status panel."""
        return self._status_bar

    def get_find_menu(self) -> tk.Menu | None:
        """Return the ``Edit > Find`` cascade (for ``Searcher`` wiring)."""
        return self._find_menu

    def init_tree(self) -> None:
        """Rebuild the tree for the current document and view mode."""
        if self._document is None:
            return
        cos_doc = self._document.get_document()
        tree_status = TreeStatus(cos_doc.get_trailer())
        self._tree_status_pane.update_tree_status(tree_status)
        self._tree.set_tree_status(tree_status)

        mode = self._current_tree_view_mode
        model: PDFTreeModel
        root_label: str
        root_obj: Any
        if mode == TreeViewMenu.VIEW_PAGES:
            filename = (
                Path(self._current_file_path).name
                if self._current_file_path is not None
                else "document"
            )
            doc_entry = DocumentEntry(self._document, filename)
            with contextlib.suppress(Exception):
                ZoomMenu.get_instance(master=self._toplevel).reset_zoom()
            with contextlib.suppress(Exception):
                RotationMenu.get_instance(
                    master=self._toplevel
                ).set_rotation_selection(RotationMenu.ROTATE_0_DEGREES)
            with contextlib.suppress(Exception):
                ImageTypeMenu.get_instance(
                    master=self._toplevel
                ).set_image_type_selection(ImageTypeMenu.IMAGETYPE_RGB)
            with contextlib.suppress(Exception):
                RenderDestinationMenu.get_instance(
                    master=self._toplevel
                ).set_render_destination_selection(
                    RenderDestinationMenu.RENDER_DESTINATION_EXPORT
                )
            model = PDFTreeModel(doc_entry)
            root_obj = doc_entry
            root_label = filename
        elif mode == TreeViewMenu.VIEW_CROSS_REF_TABLE:
            xrefs = XrefEntries(self._document)
            model = PDFTreeModel(xrefs)
            root_obj = xrefs
            root_label = XrefEntries.PATH
        else:
            model = PDFTreeModel(self._document)
            root_obj = model.get_root()
            root_label = "Root"

        self._render_tree(model, root_obj, root_label)

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _render_tree(
        self, model: PDFTreeModel, root_obj: Any, root_label: str
    ) -> None:
        """Insert ``root_obj`` (and one level of children) into the Treeview."""
        # Reset state.
        for iid in self._tree.get_children(""):
            self._tree.delete(iid)
        self._tree._node_for_iid.clear()  # noqa: SLF001

        if root_obj is None:
            return

        root_iid = self._tree.insert("", "end", text=root_label, open=True)
        self._tree.register_node(root_iid, root_obj)
        self._populate_children(model, root_iid, root_obj)

        # Auto-select the first child so a freshly opened doc lands on
        # a useful pane (matches Swing's ``tree.setSelectionPath(...)``).
        children = self._tree.get_children(root_iid)
        if children:
            self._tree.selection_set(children[0])

    def _populate_children(
        self, model: PDFTreeModel, parent_iid: str, parent_node: Any
    ) -> None:
        """Populate one level of children under ``parent_iid``.

        We populate one level eagerly; deeper levels are populated on
        demand via the ``<<TreeviewOpen>>`` event for performance on
        large documents.
        """
        try:
            count = model.get_child_count(parent_node)
        except Exception as ex:  # noqa: BLE001
            _LOG.error("get_child_count failed: %s", ex)
            return
        for i in range(count):
            try:
                child = model.get_child(parent_node, i)
            except Exception as ex:  # noqa: BLE001
                _LOG.error("get_child failed: %s", ex)
                continue
            label = _node_label(child)
            iid = self._tree.insert(parent_iid, "end", text=label)
            self._tree.register_node(iid, child)
            # Insert a sentinel marker so the disclosure triangle shows.
            try:
                if not model.is_leaf(child):
                    self._tree.insert(iid, "end", text="...")
            except Exception:  # noqa: BLE001
                pass
        # On-demand expand handler — replace the sentinel with real
        # children when the user opens a node.
        self._tree.bind("<<TreeviewOpen>>", self._on_tree_open, add="+")

    def _on_tree_open(self, _event: tk.Event[Any]) -> None:
        if self._document is None:
            return
        selection = self._tree.focus()
        if not selection:
            return
        children = self._tree.get_children(selection)
        # If the only child is the sentinel, replace it.
        if (
            len(children) == 1
            and self._tree.item(children[0], "text") == "..."
            and self._tree.get_node(children[0]) is None
        ):
            self._tree.delete(children[0])
            node = self._tree.get_node(selection)
            if node is None:
                return
            model = PDFTreeModel(self._document)
            self._populate_children(model, selection, node)

    # ------------------------------------------------------------------
    # Tree-selection dispatch
    # ------------------------------------------------------------------

    def _on_tree_selection_changed(self, _event: tk.Event[Any]) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        iid = selection[0]
        node = self._tree.get_node(iid)
        if node is None:
            return
        parent_iid = self._tree.parent(iid)
        parent_node = self._tree.get_node(parent_iid) if parent_iid else None
        try:
            self._dispatch_selection(node, parent_node, iid, parent_iid)
        except Exception as ex:  # noqa: BLE001
            _LOG.error("%s", ex)
            self._show_text_details(node)

    def _dispatch_selection(
        self,
        node: Any,
        parent_node: Any,
        iid: str,
        parent_iid: str,
    ) -> None:
        """Pick + mount the appropriate detail pane for ``node``."""
        status_label = self._status_bar.get_status_label()
        if status_label is not None:
            status_label.configure(text="")

        if isinstance(node, XrefEntry):
            self._show_text_details(node)
            return
        if self._is_page(node):
            self._show_page(node)
            return
        if self._is_special_colorspace(node) or self._is_other_colorspace(node):
            self._show_color_pane(node)
            return
        if parent_node is not None and self._is_flag_node(node, parent_node):
            self._show_flag_pane(parent_node, node)
            return
        if self._is_stream(node):
            self._show_stream(node, iid, parent_iid)
            return
        if self._is_font(node):
            self._show_font(node, iid)
            return
        if parent_node is not None and self._is_signature(node, parent_node):
            self._show_signature_pane(node)
            return
        if self._is_string(node):
            self._show_string(node)
            return
        self._show_text_details(node)

    # ------------------------------------------------------------------
    # Type tests (mirrors upstream's is*() helpers)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_underneath_object(node: Any) -> Any:
        if isinstance(node, MapEntry):
            return node.get_value()
        if isinstance(node, ArrayEntry):
            return node.get_value()
        if isinstance(node, PageEntry):
            return node.get_dict()
        if isinstance(node, XrefEntry):
            return node.get_object()
        if isinstance(node, COSObject):
            return node.get_object()
        return node

    @staticmethod
    def _get_node_key(node: Any) -> COSName | None:
        if isinstance(node, MapEntry):
            return node.get_key()
        return None

    @classmethod
    def _is_page(cls, node: Any) -> bool:
        underneath = cls._get_underneath_object(node)
        if isinstance(underneath, COSDictionary):
            type_item = underneath.get_item(COSName.TYPE)
            if isinstance(type_item, COSName) and type_item.get_name() == "Page":
                return True
        return False

    @classmethod
    def _is_stream(cls, node: Any) -> bool:
        return isinstance(cls._get_underneath_object(node), COSStream)

    @classmethod
    def _is_string(cls, node: Any) -> bool:
        return isinstance(cls._get_underneath_object(node), COSString)

    @classmethod
    def _is_font(cls, node: Any) -> bool:
        underneath = cls._get_underneath_object(node)
        if isinstance(underneath, COSDictionary):
            type_name = underneath.get_cos_name(COSName.TYPE)
            if type_name is not None and type_name.get_name() == "Font":
                # Exclude CIDFont* (those are dealt with via Type0 wrapping).
                subtype = underneath.get_cos_name(COSName.SUBTYPE)
                return not (
                    subtype is not None
                    and subtype.get_name() in ("CIDFontType0", "CIDFontType2")
                )
        return False

    @classmethod
    def _is_special_colorspace(cls, node: Any) -> bool:
        return cls._first_array_name(node) in _SPECIAL_COLORSPACES

    @classmethod
    def _is_other_colorspace(cls, node: Any) -> bool:
        return cls._first_array_name(node) in _OTHER_COLORSPACES

    @classmethod
    def _first_array_name(cls, node: Any) -> str | None:
        underneath = cls._get_underneath_object(node)
        if isinstance(underneath, COSArray) and underneath.size() > 0:
            entry = underneath.get(0)
            if isinstance(entry, COSName):
                return entry.get_name()
        return None

    @classmethod
    def _is_flag_node(cls, node: Any, parent_node: Any) -> bool:
        if not isinstance(node, MapEntry):
            return False
        key = node.get_key()
        if key is None:
            return False
        name = key.get_name()
        if name == "Flags" and cls._is_font_descriptor(parent_node):
            return True
        if name == "F" and cls._is_annot(parent_node):
            return True
        if name in ("Ff", "Panose", "SigFlags"):
            return True
        return name == "P" and cls._is_encrypt(parent_node)

    @classmethod
    def _is_encrypt(cls, node: Any) -> bool:
        if isinstance(node, MapEntry):
            key = node.get_key()
            if key is not None and key.get_name() == "Encrypt":
                return isinstance(node.get_value(), COSDictionary)
        return False

    @classmethod
    def _is_font_descriptor(cls, node: Any) -> bool:
        underneath = cls._get_underneath_object(node)
        if isinstance(underneath, COSDictionary):
            type_name = underneath.get_cos_name(COSName.TYPE)
            return type_name is not None and type_name.get_name() == "FontDescriptor"
        return False

    @classmethod
    def _is_annot(cls, node: Any) -> bool:
        underneath = cls._get_underneath_object(node)
        if isinstance(underneath, COSDictionary):
            type_name = underneath.get_cos_name(COSName.TYPE)
            return type_name is not None and type_name.get_name() == "Annot"
        return False

    @classmethod
    def _is_signature(cls, node: Any, parent_node: Any) -> bool:
        if not isinstance(node, MapEntry) or not isinstance(parent_node, MapEntry):
            return False
        key = node.get_key()
        if key is None or key.get_name() != "Contents":
            return False
        parent_value = parent_node.get_value()
        if isinstance(parent_value, COSDictionary):
            type_name = parent_value.get_cos_name(COSName.TYPE)
            if type_name is not None and type_name.get_name() == "Sig":
                return True
        return False

    # ------------------------------------------------------------------
    # Pane mounting
    # ------------------------------------------------------------------

    def _replace_right_component(self, widget: tk.Widget | None) -> None:
        """Swap the right-hand pane to ``widget``."""
        # Tear down the current widget without destroying any of its
        # children (callers retain references for testability).
        for child in self._right_frame.winfo_children():
            child.pack_forget()
        if widget is None:
            self._current_right_widget = None
            return
        widget.pack(in_=self._right_frame, fill="both", expand=True)
        self._current_right_widget = widget

    def _show_page(self, node: Any) -> None:
        underneath = self._get_underneath_object(node)
        if not isinstance(underneath, COSDictionary) or self._document is None:
            return
        pane = PagePane(
            self._right_frame,
            self._document,
            underneath,
            self._status_bar.get_status_label(),
        )
        pane.init()
        self._replace_right_component(pane.get_panel())

    def _show_color_pane(self, node: Any) -> None:
        underneath = self._get_underneath_object(node)
        if not isinstance(underneath, COSArray) or underneath.size() == 0:
            return
        first = underneath.get(0)
        if not isinstance(first, COSName):
            return
        name = first.get_name()
        widget: tk.Widget | None
        if name == "Separation":
            widget = CSSeparation(underneath, self._right_frame).get_panel()
        elif name == "DeviceN":
            widget = CSDeviceN(underneath, self._right_frame).get_panel()
        elif name == "Indexed":
            widget = CSIndexed(underneath, self._right_frame).get_panel()
        elif name in _OTHER_COLORSPACES:
            widget = CSArrayBased(underneath, self._right_frame).get_panel()
        else:
            widget = None
        self._replace_right_component(widget)

    def _show_flag_pane(self, parent_node: Any, node: Any) -> None:
        underneath_parent = self._get_underneath_object(parent_node)
        if not isinstance(underneath_parent, COSDictionary):
            return
        key = self._get_node_key(node)
        if key is None:
            return
        pane = FlagBitsPane(
            self._document, underneath_parent, key, self._right_frame
        )
        view = pane.get_pane()
        if view is None:
            return
        # ``FlagBitsPaneView`` is a ``ttk.Frame``-rooted widget; mount it.
        widget = view if isinstance(view, tk.Widget) else getattr(view, "frame", None)
        if widget is None and hasattr(view, "get_panel"):
            widget = view.get_panel()
        self._replace_right_component(widget)

    def _show_stream(self, node: Any, iid: str, parent_iid: str) -> None:
        stream = self._get_underneath_object(node)
        if not isinstance(stream, COSStream):
            return
        is_content_stream = False
        is_thumb = False
        resources_dict: COSDictionary | None = None
        node_key = self._get_node_key(node)
        parent_node = self._tree.get_node(parent_iid) if parent_iid else None
        parent_key = self._get_node_key(parent_node) if parent_node is not None else None

        if node_key is not None and node_key.get_name() == "Contents":
            page_dict = self._get_underneath_object(parent_node)
            if isinstance(page_dict, COSDictionary):
                resources_dict = page_dict.get_cos_dictionary(COSName.RESOURCES)
            is_content_stream = True
        elif parent_key is not None and parent_key.get_name() in (
            "Contents",
            "CharProcs",
        ):
            grand_iid = self._tree.parent(parent_iid)
            grand_node = self._tree.get_node(grand_iid) if grand_iid else None
            page_dict = self._get_underneath_object(grand_node) if grand_node else None
            if isinstance(page_dict, COSDictionary):
                resources_dict = page_dict.get_cos_dictionary(COSName.RESOURCES)
            is_content_stream = True
        else:
            subtype = stream.get_cos_name(COSName.SUBTYPE)
            type_name = stream.get_cos_name(COSName.TYPE)
            pattern_type = stream.get_int("PatternType", 0)
            if (
                (subtype is not None and subtype.get_name() == "Form")
                or (type_name is not None and type_name.get_name() == "Pattern")
                or pattern_type == 1
            ):
                if stream.contains_key(COSName.RESOURCES):
                    resources_dict = stream.get_cos_dictionary(COSName.RESOURCES)
                is_content_stream = True
            elif node_key is not None and node_key.get_name() == "Thumb":
                is_thumb = True
            elif subtype is not None and subtype.get_name() == "Image":
                # Two levels up should be the /Resources dictionary.
                grand_iid = self._tree.parent(parent_iid)
                grand_node = self._tree.get_node(grand_iid) if grand_iid else None
                if grand_node is not None and not isinstance(grand_node, XrefEntries):
                    underneath = self._get_underneath_object(grand_node)
                    if isinstance(underneath, COSDictionary):
                        resources_dict = underneath

        pane = StreamPane(
            self._right_frame,
            stream,
            is_content_stream,
            is_thumb,
            resources_dict,
        )
        pane.init()
        self._replace_right_component(pane.get_panel())

    def _show_font(self, node: Any, iid: str) -> None:
        font_name = self._get_node_key(node)
        if font_name is None:
            self._show_text_details(node)
            return
        # Resources dictionary is two levels up (Font / Resources / ...).
        parent_iid = self._tree.parent(iid)
        grand_iid = self._tree.parent(parent_iid) if parent_iid else ""
        grand_node = self._tree.get_node(grand_iid) if grand_iid else None
        resources_dict = self._get_underneath_object(grand_node)
        if not isinstance(resources_dict, COSDictionary):
            self._show_text_details(node)
            return
        controller = FontEncodingPaneController(
            font_name, resources_dict, self._right_frame
        )
        widget = controller.get_pane()
        if widget is None:
            self._show_text_details(node)
            return
        self._replace_right_component(widget)

    def _show_signature_pane(self, node: Any) -> None:
        underneath = self._get_underneath_object(node)
        if isinstance(underneath, COSString):
            pane = SignaturePane(self._right_frame, underneath)
            self._replace_right_component(pane.get_pane())

    def _show_string(self, node: Any) -> None:
        underneath = self._get_underneath_object(node)
        if isinstance(underneath, COSString):
            pane = StringPane(self._right_frame, underneath)
            self._replace_right_component(pane.get_pane())

    def _show_text_details(self, node: Any) -> None:
        """Generic fallback: dump the node's stringified value in a ``tk.Text``."""
        # Streams of unknown sort fall through here — mount a HexView when
        # the underneath object is a COSStream that wasn't classified as a
        # content stream.
        underneath = self._get_underneath_object(node)
        if isinstance(underneath, COSStream):
            data = _read_stream_bytes(underneath)
            hex_view = HexView(self._right_frame, data)
            self._replace_right_component(hex_view.get_pane())
            return

        text_widget = tk.Text(self._right_frame, wrap="word")
        rendered = _convert_to_string(node)
        if rendered is None:
            rendered = ""
        with contextlib.suppress(tk.TclError):
            text_widget.insert("1.0", rendered)
            text_widget.configure(state="disabled")
        self._replace_right_component(text_widget)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _open_menu_item_action_performed(self) -> None:
        path = filedialog.askopenfilename(
            parent=self._toplevel,
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if not path:
            return
        try:
            self._read_pdf_file(path, "")
        except OSError as ex:
            ErrorDialog(ex).set_visible(True)

    def _open_url_menu_item_action_performed(self) -> None:
        url = simpledialog.askstring(
            "Open URL", "Enter an URL", parent=self._toplevel
        )
        if not url:
            return
        try:
            self._read_pdf_url(url, "")
        except (OSError, ValueError) as ex:
            ErrorDialog(ex).set_visible(True)

    def _reopen_menu_item_action_performed(self) -> None:
        if self._current_file_path is None:
            return
        try:
            if self._current_file_path.startswith(("http", "file:")):
                self._read_pdf_url(self._current_file_path, "")
            else:
                self._read_pdf_file(self._current_file_path, "")
        except (OSError, ValueError) as ex:
            ErrorDialog(ex).set_visible(True)

    def _save_as_menu_item_action_performed(self) -> None:
        if self._document is None:
            return
        chosen = filedialog.asksaveasfilename(
            parent=self._toplevel,
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
        )
        if not chosen:
            return
        try:
            self._document.set_all_security_to_be_removed(True)
            self._document.save(chosen)
        except OSError as ex:
            ErrorDialog(ex).set_visible(True)

    def _save_decoded_stream(self) -> None:
        """Save the decoded body of the currently selected stream."""
        stream = self._selected_stream()
        if stream is None:
            return
        chosen = filedialog.asksaveasfilename(parent=self._toplevel)
        if not chosen:
            return
        try:
            data = _read_stream_bytes(stream, raw=False)
            Path(chosen).write_bytes(data)
        except OSError as ex:
            ErrorDialog(ex).set_visible(True)

    def _save_raw_stream(self) -> None:
        """Save the encoded (raw) body of the currently selected stream."""
        stream = self._selected_stream()
        if stream is None:
            return
        chosen = filedialog.asksaveasfilename(parent=self._toplevel)
        if not chosen:
            return
        try:
            data = _read_stream_bytes(stream, raw=True)
            Path(chosen).write_bytes(data)
        except OSError as ex:
            ErrorDialog(ex).set_visible(True)

    def _print_menu_item_action_performed(self) -> None:
        # Printing is not ported — see CHANGES.md.
        if self._document is None:
            return
        messagebox.showinfo(
            "Print",
            "Printing is not yet implemented in the pypdfbox debugger port.",
            parent=self._toplevel,
        )

    def _exit_menu_item_action_performed(self) -> None:
        """Close the document, persist prefs, and destroy the window."""
        if self._document is not None:
            with contextlib.suppress(Exception):
                self._document.close()
            self._document = None
        if (
            self._current_file_path is not None
            and not self._current_file_path.startswith("http")
        ):
            self._recent_files.add_file(self._current_file_path)
        self._recent_files.close()
        with contextlib.suppress(Exception):
            self._toplevel.destroy()

    def _find_menu_item_action_performed(self) -> None:
        # Search wiring is delegated to ``Searcher`` — but no concrete
        # search target is available without a focused text pane. The
        # menu item is enabled when a document is loaded; clicking it
        # surfaces a friendly note rather than silently no-op'ing.
        messagebox.showinfo(
            "Find",
            "Use the editor controls within the right-hand pane to search.",
            parent=self._toplevel,
        )

    def _find_next_menu_item_action_performed(self) -> None:
        pass  # Wired by individual SearchPanel instances.

    def _find_previous_menu_item_action_performed(self) -> None:
        pass  # Wired by individual SearchPanel instances.

    def _copy_tree_path(self) -> None:
        """Copy the current tree-path string to the clipboard."""
        selection = self._tree.selection()
        if not selection:
            return
        iid = selection[0]
        path: list[Any] = []
        current = iid
        while current:
            node = self._tree.get_node(current)
            if node is not None:
                path.append(node)
            current = self._tree.parent(current)
        path.reverse()
        if not path or self._document is None:
            return
        cos_doc = self._document.get_document()
        status = TreeStatus(cos_doc.get_trailer())
        string = status.get_string_for_path(tuple(path))
        with contextlib.suppress(tk.TclError):
            self._toplevel.clipboard_clear()
            self._toplevel.clipboard_append(string)

    # ------------------------------------------------------------------
    # macOS hooks
    # ------------------------------------------------------------------

    def _osx_open_file(self, filename: str) -> None:
        with contextlib.suppress(OSError):
            self._read_pdf_file(filename, "")

    def _show_about_dialog(self) -> None:
        messagebox.showinfo(
            "About Apache PDFBox",
            "Apache PDFBox Debugger (pypdfbox port)",
            parent=self._toplevel,
        )

    # ------------------------------------------------------------------
    # Document loading
    # ------------------------------------------------------------------

    def _read_pdf_file(self, file_path: str, password: str | bytes = "") -> None:
        """Open ``file_path`` and rebuild the tree."""
        # Local import to avoid a heavy import at module load time, and
        # to keep tests that exercise non-loading paths trivially light.
        from pypdfbox.pdmodel import PDDocument  # noqa: PLC0415

        if self._document is not None:
            with contextlib.suppress(Exception):
                self._document.close()
            if (
                self._current_file_path is not None
                and not self._current_file_path.startswith("http")
            ):
                self._recent_files.add_file(self._current_file_path)

        self._current_file_path = file_path
        self._recent_files.remove_file(file_path)
        # Pass the password only when provided; ``PDDocument.load`` rejects
        # an empty bytes value on un-encrypted documents in some test
        # corpora.
        self._document = (
            PDDocument.load(file_path, password)
            if password
            else PDDocument.load(file_path)
        )

        self._enable_document_actions()
        self.init_tree()

        new_title = (
            Path(file_path).name
            if _is_mac_os()
            else f"PDF Debugger - {Path(file_path).resolve()}"
        )
        with contextlib.suppress(AttributeError, tk.TclError):
            self._toplevel.title(new_title)  # type: ignore[union-attr]
        self._populate_recent_files_menu()

    def _read_pdf_url(self, url_string: str, password: str | bytes = "") -> None:
        """Open a remote PDF and rebuild the tree."""
        from urllib.parse import urlparse  # noqa: PLC0415
        from urllib.request import urlopen  # noqa: PLC0415

        from pypdfbox.pdmodel import PDDocument  # noqa: PLC0415

        parsed = urlparse(url_string)
        if not parsed.scheme:
            raise ValueError(f"invalid URL: {url_string}")

        if self._document is not None:
            with contextlib.suppress(Exception):
                self._document.close()
            if (
                self._current_file_path is not None
                and not self._current_file_path.startswith("http")
            ):
                self._recent_files.add_file(self._current_file_path)

        self._current_file_path = url_string
        # ``urlopen`` is the stdlib equivalent of upstream's
        # ``RandomAccessReadBuffer.createBufferFromStream(url.openStream())``.
        with urlopen(url_string) as response:  # noqa: S310 - user-supplied URL
            data = response.read()
        self._document = (
            PDDocument.load(data, password) if password else PDDocument.load(data)
        )

        self._enable_document_actions()
        self.init_tree()
        new_title = (
            url_string if _is_mac_os() else f"PDF Debugger - {url_string}"
        )
        with contextlib.suppress(AttributeError, tk.TclError):
            self._toplevel.title(new_title)  # type: ignore[union-attr]
        self._populate_recent_files_menu()

    def _enable_document_actions(self) -> None:
        if self._file_menu is None:
            return
        for idx in (
            self._reopen_menu_index,
            self._save_as_menu_index,
            self._print_menu_index,
        ):
            if idx is not None:
                with contextlib.suppress(tk.TclError):
                    self._file_menu.entryconfigure(idx, state="normal")
        # Save Decoded / Raw stream entries (relative indices: save_as +1, +2)
        if self._save_as_menu_index is not None:
            with contextlib.suppress(tk.TclError):
                self._file_menu.entryconfigure(
                    self._save_as_menu_index + 1, state="normal"
                )
                self._file_menu.entryconfigure(
                    self._save_as_menu_index + 2, state="normal"
                )
        # Find menu (parent cascade index recorded in `_edit_menu_index`).

    def _populate_recent_files_menu(self) -> None:
        if self._recent_files_menu is None or self._file_menu is None:
            return
        # Wipe + repopulate.
        self._recent_files_menu.delete(0, "end")
        files = self._recent_files.get_files()
        for path in reversed(files):
            name = Path(path).name

            def _opener(path=path) -> None:  # noqa: ANN001 - local default arg
                with contextlib.suppress(OSError):
                    self._read_pdf_file(path, "")

            self._recent_files_menu.add_command(label=name, command=_opener)
        state = "normal" if files else "disabled"
        # Locate the Recent menu in the file menu — its index is
        # ``reopen + 1`` per :meth:`_create_file_menu`.
        if self._reopen_menu_index is not None:
            with contextlib.suppress(tk.TclError):
                self._file_menu.entryconfigure(
                    self._reopen_menu_index + 1, state=state
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _selected_stream(self) -> COSStream | None:
        selection = self._tree.selection()
        if not selection:
            return None
        node = self._tree.get_node(selection[0])
        underneath = self._get_underneath_object(node)
        return underneath if isinstance(underneath, COSStream) else None

    # ------------------------------------------------------------------
    # CLI entry point
    # ------------------------------------------------------------------

    @classmethod
    def main(cls, args: list[str] | None = None) -> int:
        """Command-line entry point. Mirrors upstream ``PDFDebugger.main``."""
        import argparse  # noqa: PLC0415

        parser = argparse.ArgumentParser(
            prog="pdfdebugger",
            description=(
                "Analyzes and inspects the internal structure of a PDF document"
            ),
        )
        parser.add_argument(
            "inputfile", nargs="?", help="the PDF file to be loaded"
        )
        parser.add_argument(
            "-password",
            dest="password",
            default=None,
            help="password to decrypt the document",
        )
        parser.add_argument(
            "-viewstructure",
            dest="viewstructure",
            action="store_true",
            help="activate structure mode on startup",
        )
        ns = parser.parse_args(args)

        root = tk.Tk()
        root.title(cls.TITLE)
        view_mode = (
            TreeViewMenu.VIEW_STRUCTURE
            if ns.viewstructure
            else TreeViewMenu.VIEW_PAGES
        )
        debugger = cls(root, initial_view_mode=view_mode)
        if ns.inputfile and Path(ns.inputfile).exists():
            try:
                debugger.open_document(ns.inputfile, ns.password or "")
            except OSError as ex:
                _LOG.error("failed to open %s: %s", ns.inputfile, ex)
        root.mainloop()
        return 0


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------


def _ensure_default_root() -> tk.Tk:
    """Return an existing implicit Tk root, or create one."""
    # ``tk._default_root`` is a private but stable Tkinter API.
    existing = getattr(tk, "_default_root", None)
    if existing is not None:
        return existing
    return tk.Tk()


def _node_label(node: Any) -> str:
    """Render ``node`` as a Treeview row label."""
    if isinstance(node, MapEntry):
        key = node.get_key()
        if key is not None:
            return key.get_name()
        return "(null)"
    if isinstance(node, ArrayEntry):
        return f"[{node.get_index()}]"
    if isinstance(node, PageEntry):
        return str(node)
    if isinstance(node, XrefEntry):
        return str(node)
    return str(node)


def _convert_to_string(node: Any) -> str | None:
    """Render ``node`` as a one-line string for the generic detail panel."""
    if isinstance(node, COSBoolean):
        return "true" if node.get_value() else "false"
    if isinstance(node, COSFloat):
        return str(node.float_value())
    if isinstance(node, COSNull):
        return "null"
    if isinstance(node, COSInteger):
        return str(node.long_value() if hasattr(node, "long_value") else int(node))
    if isinstance(node, COSName):
        return node.get_name()
    if isinstance(node, COSString):
        text = node.get_string()
        for char in text:
            code = ord(char)
            if code <= 0x1F or 0x7F <= code <= 0x9F:
                return "<" + node.to_hex_string() + ">"
        return text
    if isinstance(node, COSStream):
        try:
            return _read_stream_bytes(node).decode("latin-1", errors="replace")
        except OSError:
            return None
    if isinstance(node, COSDictionary):
        return "COSDictionary"
    if isinstance(node, COSArray):
        return "COSArray"
    if isinstance(node, MapEntry):
        return _convert_to_string(node.get_value())
    if isinstance(node, ArrayEntry):
        return _convert_to_string(node.get_value())
    if isinstance(node, XrefEntry):
        return str(node)
    return None


def _read_stream_bytes(stream: COSStream, *, raw: bool = False) -> bytes:
    """Read ``stream`` fully into bytes."""
    creator_name = "create_raw_input_stream" if raw else "create_input_stream"
    creator = getattr(stream, creator_name, None)
    if creator is None:
        return b""
    try:
        with creator() as data:
            if hasattr(data, "read"):
                return data.read()
            return bytes(data)
    except OSError:
        return b""


__all__ = ["PDFDebugger"]
