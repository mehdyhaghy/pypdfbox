"""Tkinter port of ``ViewMenu``.

Mirrors ``org.apache.pdfbox.debugger.ui.ViewMenu`` — the top-level
*View* menu in the debugger's menubar.

**Partial port (wave 1294)**: upstream's *View* cascade aggregates a
larger set of sub-menus (``TreeViewMenu``, ``ImageTypeMenu``,
``TextStripperMenu``, the *Show TextStripper TextPositions* / glyph
bounds / subsampling / extract-text checkbuttons, *Repair AcroForm*…)
which are not yet ported. This module only wires in the three menus
covered by this wave — :class:`ZoomMenu`, :class:`RotationMenu`,
:class:`RenderDestinationMenu` — plus the always-available
*Allow subsampling* checkbox (which has no external dependencies).

Subsequent waves will add the remaining sub-menus and checkbuttons; see
``CHANGES.md`` for the deviation note.
"""

from __future__ import annotations

from typing import Any, ClassVar

from .menu_base import MenuBase
from .render_destination_menu import RenderDestinationMenu
from .rotation_menu import RotationMenu
from .zoom_menu import ZoomMenu

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class ViewMenu(MenuBase):
    """Singleton facade for the debugger's *View* menubar entry."""

    ALLOW_SUBSAMPLING: ClassVar[str] = "Allow subsampling"

    _instance: ClassVar[ViewMenu | None] = None

    def __init__(self, pdf_debugger: Any = None, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)
        self._pdf_debugger = pdf_debugger

        menu = tk.Menu(master, tearoff=0)
        self.set_menu(menu)

        # Sub-menus ported in this wave.
        self._zoom_menu = ZoomMenu.get_instance(master=master)
        self._zoom_menu.set_enable_menu(False)
        menu.add_cascade(label="Zoom", menu=self._zoom_menu.get_menu())

        self._rotation_menu = RotationMenu.get_instance(master=master)
        self._rotation_menu.set_enable_menu(False)
        menu.add_cascade(label="Rotation", menu=self._rotation_menu.get_menu())

        self._render_destination_menu = RenderDestinationMenu.get_instance(master=master)
        self._render_destination_menu.set_enable_menu(False)
        menu.add_cascade(
            label="Render destination", menu=self._render_destination_menu.get_menu()
        )

        # Standalone toggle that doesn't depend on any unported menu.
        menu.add_separator()
        self._allow_subsampling_var = tk.BooleanVar(value=False)
        menu.add_checkbutton(
            label=self.ALLOW_SUBSAMPLING,
            variable=self._allow_subsampling_var,
        )

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
    # Public read-only state mirroring upstream's static accessors
    # ------------------------------------------------------------------

    @staticmethod
    def is_allow_subsampling() -> bool:
        if ViewMenu._instance is None:
            return False
        return bool(ViewMenu._instance._allow_subsampling_var.get())


__all__ = ["ViewMenu"]
