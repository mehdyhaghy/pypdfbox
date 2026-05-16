"""Tkinter port of ``ViewMenu``.

Mirrors ``org.apache.pdfbox.debugger.ui.ViewMenu`` — the top-level
*View* menu in the debugger's menubar. Aggregates the tree-view,
zoom, rotation, image-type, render-destination and text-stripper
sub-menus and exposes the global rendering / extraction toggles.

The wiring follows upstream order:

1. ``TreeViewMenu`` cascade
2. ``ZoomMenu`` cascade
3. ``RotationMenu`` cascade
4. ``ImageTypeMenu`` cascade
5. ``RenderDestinationMenu`` cascade
6. separator
7. *Show TextStripper TextPositions* checkbutton
8. *Show TextStripper Beads* checkbutton
9. *Show Approximate Text Bounds* checkbutton
10. *Show Glyph Bounds* checkbutton
11. separator
12. *Allow subsampling* checkbutton
13. separator
14. *Extract Text* command
15. ``TextStripperMenu`` cascade
16. separator
17. *Repair AcroForm* checkbutton

The *Extract Text* command is wired to an optional consumer-supplied
callback registered via :py:meth:`set_extract_text_callback`. This is
the Python analogue of upstream's ``ActionListener``/``getActionCommand``
dispatch — the debugger shell installs a listener that performs the
actual text extraction.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from .image_type_menu import ImageTypeMenu
from .menu_base import MenuBase
from .render_destination_menu import RenderDestinationMenu
from .rotation_menu import RotationMenu
from .text_stripper_menu import TextStripperMenu
from .tree_view_menu import TreeViewMenu
from .zoom_menu import ZoomMenu

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class ViewMenu(MenuBase):
    """Singleton facade for the debugger's *View* menubar entry."""

    SHOW_TEXT_STRIPPER: ClassVar[str] = "Show TextStripper TextPositions"
    SHOW_TEXT_STRIPPER_BEADS: ClassVar[str] = "Show TextStripper Beads"
    SHOW_FONT_BBOX: ClassVar[str] = "Show Approximate Text Bounds"
    SHOW_GLYPH_BOUNDS: ClassVar[str] = "Show Glyph Bounds"
    ALLOW_SUBSAMPLING: ClassVar[str] = "Allow subsampling"
    EXTRACT_TEXT: ClassVar[str] = "Extract Text"
    REPAIR_ACROFORM: ClassVar[str] = "Repair AcroForm"

    _instance: ClassVar[ViewMenu | None] = None

    def __init__(self, pdf_debugger: Any = None, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)
        self._pdf_debugger = pdf_debugger
        self._master = master
        self._extract_text_callback: Callable[[], None] | None = None

        # Upstream's constructor body is one line: ``setMenu(createViewMenu())``.
        # Mirror that exactly so the upstream method exists on the Python class.
        self.set_menu(self.create_view_menu())

    def create_view_menu(self) -> tk.Menu:  # type: ignore[name-defined]
        """Build the *View* ``tk.Menu`` and return it.

        Direct port of upstream's private ``createViewMenu`` (promoted to
        ``public`` here so the menu wiring is observable by consumers that
        want to rebuild the cascade — e.g. tests that exercise singleton
        recycling). The returned menu is *also* bound via :py:meth:`set_menu`
        by the constructor, matching upstream's
        ``setMenu(createViewMenu())`` one-liner.
        """
        master = self._master
        menu = tk.Menu(master, tearoff=0)

        # 1. TreeViewMenu cascade.
        self._tree_view_menu = TreeViewMenu.get_instance(master=master)
        menu.add_cascade(label="Tree view", menu=self._tree_view_menu.get_menu())

        # 2. ZoomMenu cascade (disabled until a document loads).
        self._zoom_menu = ZoomMenu.get_instance(master=master)
        self._zoom_menu.set_enable_menu(False)
        menu.add_cascade(label="Zoom", menu=self._zoom_menu.get_menu())

        # 3. RotationMenu cascade.
        self._rotation_menu = RotationMenu.get_instance(master=master)
        self._rotation_menu.set_enable_menu(False)
        menu.add_cascade(label="Rotation", menu=self._rotation_menu.get_menu())

        # 4. ImageTypeMenu cascade.
        self._image_type_menu = ImageTypeMenu.get_instance(master=master)
        self._image_type_menu.set_enable_menu(False)
        menu.add_cascade(label="Image type", menu=self._image_type_menu.get_menu())

        # 5. RenderDestinationMenu cascade.
        self._render_destination_menu = RenderDestinationMenu.get_instance(master=master)
        self._render_destination_menu.set_enable_menu(False)
        menu.add_cascade(
            label="Render destination", menu=self._render_destination_menu.get_menu()
        )

        # 6. separator.
        menu.add_separator()

        # 7-10. Per-render-pass debug overlays. Disabled until a doc loads,
        # mirroring upstream's ``setEnabled(false)`` on the four ``JCheckBoxMenuItem``s.
        self._show_text_positions_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(
            label=self.SHOW_TEXT_STRIPPER,
            variable=self._show_text_positions_var,
            state="disabled",
        )
        self._show_text_strip_beads_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(
            label=self.SHOW_TEXT_STRIPPER_BEADS,
            variable=self._show_text_strip_beads_var,
            state="disabled",
        )
        self._show_approximate_text_bounds_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(
            label=self.SHOW_FONT_BBOX,
            variable=self._show_approximate_text_bounds_var,
            state="disabled",
        )
        self._show_glyph_bounds_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(
            label=self.SHOW_GLYPH_BOUNDS,
            variable=self._show_glyph_bounds_var,
            state="disabled",
        )

        # 11. separator.
        menu.add_separator()

        # 12. Standalone toggle — always available.
        self._allow_subsampling_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(
            label=self.ALLOW_SUBSAMPLING,
            variable=self._allow_subsampling_var,
        )

        # 13. separator.
        menu.add_separator()

        # 14. Extract Text command. Disabled until a doc loads upstream;
        # we keep the entry enabled here so consumers can drive it
        # programmatically in tests, and let the debugger shell flip
        # ``state`` after constructing the menu (mirrors upstream's
        # post-construction ``setEnabled`` calls).
        menu.add_command(
            label=self.EXTRACT_TEXT,
            command=self._invoke_extract_text,
            state="disabled",
        )

        # 15. TextStripperMenu cascade.
        self._text_stripper_menu = TextStripperMenu.get_instance(master=master)
        self._text_stripper_menu.set_enable_menu(False)
        menu.add_cascade(
            label="Text stripper", menu=self._text_stripper_menu.get_menu()
        )

        # 16. separator.
        menu.add_separator()

        # 17. Repair AcroForm checkbutton.
        self._repair_acro_form_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(
            label=self.REPAIR_ACROFORM,
            variable=self._repair_acro_form_var,
            state="disabled",
        )
        return menu

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(
        cls,
        pdf_debugger: Any = None,
        master: tk.Misc | None = None,  # type: ignore[name-defined]
    ) -> ViewMenu:
        if cls._instance is None:
            cls._instance = cls(pdf_debugger=pdf_debugger, master=master)
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    # ------------------------------------------------------------------
    # Extract Text dispatch
    # ------------------------------------------------------------------

    def set_extract_text_callback(self, callback: Callable[[], None] | None) -> None:
        """Register the consumer that performs the actual text extraction.

        Consumers (typically the ``PDFDebugger`` shell) call this once at
        construction time. Invocations are dispatched synchronously from
        the menu's ``command`` handler.
        """
        self._extract_text_callback = callback

    def _invoke_extract_text(self) -> None:
        if self._extract_text_callback is not None:
            self._extract_text_callback()

    # ------------------------------------------------------------------
    # Public read-only state mirroring upstream's static accessors
    # ------------------------------------------------------------------

    @staticmethod
    def is_allow_subsampling() -> bool:
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._allow_subsampling_var.get())

    @staticmethod
    def is_show_text_positions() -> bool:
        """Return whether the *Show TextStripper TextPositions* toggle is on."""
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._show_text_positions_var.get())

    @staticmethod
    def is_show_text_strip_beads() -> bool:
        """Return whether the *Show TextStripper Beads* toggle is on."""
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._show_text_strip_beads_var.get())

    @staticmethod
    def is_show_approximate_text_bounds() -> bool:
        """Return whether the *Show Approximate Text Bounds* toggle is on."""
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._show_approximate_text_bounds_var.get())

    @staticmethod
    def is_show_glyph_bounds() -> bool:
        """Return whether the *Show Glyph Bounds* toggle is on."""
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._show_glyph_bounds_var.get())

    @staticmethod
    def is_repair_acro_form() -> bool:
        """Return whether the *Repair AcroForm* toggle is on."""
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._repair_acro_form_var.get())

    @staticmethod
    def is_rendering_option(action_command: str) -> bool:
        """Return ``True`` for any of the per-render-pass overlay labels.

        Mirrors upstream's ``isRenderingOption(String)`` — used by the
        debugger to decide whether a menu event should trigger a re-render
        of the currently-displayed page.
        """
        return action_command in {
            ViewMenu.SHOW_TEXT_STRIPPER,
            ViewMenu.SHOW_TEXT_STRIPPER_BEADS,
            ViewMenu.SHOW_FONT_BBOX,
            ViewMenu.SHOW_GLYPH_BOUNDS,
            ViewMenu.ALLOW_SUBSAMPLING,
        }

    # ------------------------------------------------------------------
    # Event predicates (upstream-named static helpers)
    # ------------------------------------------------------------------

    @staticmethod
    def _action_command_of(action_event: Any) -> str:
        """Extract the action-command label from a Tk-or-Swing-shaped event.

        Tk listeners installed by :py:class:`MenuBase.add_menu_listeners`
        already pass the entry label (a ``str``). Some debugger call sites
        still wrap that label in a lightweight event-like object that
        exposes ``action_command`` or ``label`` (mirroring Swing's
        ``ActionEvent.getActionCommand``); accept either shape so the
        predicate behaves the same regardless of dispatch style.
        """
        if isinstance(action_event, str):
            return action_event
        for attr in ("action_command", "label"):
            value = getattr(action_event, attr, None)
            if isinstance(value, str):
                return value
        return ""

    @staticmethod
    def is_extract_text_event(action_event: Any) -> bool:
        """Return ``True`` when ``action_event`` was dispatched by *Extract Text*.

        Mirrors upstream ``isExtractTextEvent(ActionEvent)``.
        """
        return ViewMenu._action_command_of(action_event) == ViewMenu.EXTRACT_TEXT

    @staticmethod
    def is_repair_acroform_event(action_event: Any) -> bool:
        """Return ``True`` when ``action_event`` was dispatched by *Repair AcroForm*.

        Mirrors upstream ``isRepairAcroformEvent(ActionEvent)``.
        """
        return ViewMenu._action_command_of(action_event) == ViewMenu.REPAIR_ACROFORM

    @staticmethod
    def is_repair_acroform_selected() -> bool:
        """Return the current checkbox state of the *Repair AcroForm* entry.

        Upstream-named alias for :py:meth:`is_repair_acro_form` — kept
        because upstream exposes ``isRepairAcroformSelected()`` as the
        public accessor used by the debugger shell.
        """
        return ViewMenu.is_repair_acro_form()

    @staticmethod
    def is_show_font_b_box() -> bool:
        """Return the current checkbox state of the *Show Font BBox* entry.

        Upstream-named alias for :py:meth:`is_show_approximate_text_bounds`
        — upstream's symbol is ``isShowFontBBox`` (the constant label is
        ``"Show Approximate Text Bounds"`` even though the field is named
        ``showFontBBox``). The snake_case translation is
        ``is_show_font_b_box`` (two adjacent capitals ``BB`` → ``_b_b``).
        """
        return ViewMenu.is_show_approximate_text_bounds()


__all__ = ["ViewMenu"]
