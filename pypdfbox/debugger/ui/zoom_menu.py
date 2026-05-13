"""Tkinter port of ``ZoomMenu``.

Mirrors ``org.apache.pdfbox.debugger.ui.ZoomMenu`` — a singleton menubar
entry exposing the discrete zoom levels used by the debugger's page
preview.

Upstream is a Swing ``JMenu`` of ``JRadioButtonMenuItem`` instances
bound together by a ``ButtonGroup``. The Tk equivalent is a
``tk.Menu(tearoff=0)`` populated with ``add_radiobutton`` entries that
share a single ``tk.StringVar`` — same single-selection invariant
without an explicit group object.

Singleton: PDFBox uses an explicit ``getInstance`` accessor; we keep
that pattern (rather than introducing a second module-level instance)
so call sites translate one-for-one. The instance is created lazily
because building a ``tk.Menu`` requires a Tk root, which may not yet
exist at import time.
"""

from __future__ import annotations

from typing import ClassVar

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class ZoomMenu(MenuBase):
    """Singleton zoom menu for the debugger's *View* cascade."""

    #: Zoom percentages exposed by the menu — matches upstream order.
    ZOOMS: ClassVar[tuple[int, ...]] = (25, 50, 100, 150, 200, 400, 1000, 2000)

    _instance: ClassVar[ZoomMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        self._page_zoom_scale: float = 1.0
        self._image_zoom_scale: float = 1.0

        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)

        menu = tk.Menu(master, tearoff=0)
        self.set_menu(menu)
        self._zoom_var = tk.StringVar(value="100%")
        for zoom in self.ZOOMS:
            label = f"{zoom}%"
            menu.add_radiobutton(label=label, value=label, variable=self._zoom_var)

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> ZoomMenu:  # type: ignore[name-defined]
        """Return the lazily-created singleton instance.

        Mirrors upstream ``ZoomMenu.getInstance()``.
        """
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        """Internal helper used by the tests to clear the singleton."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Public API mirrored from upstream
    # ------------------------------------------------------------------

    def change_zoom_selection(self, zoom_value: float) -> None:
        """Select the radio entry matching ``zoom_value``.

        ``zoom_value`` is a multiplier (``1`` == 100 %), matching the
        upstream contract (``zoomValue * 100`` is the printed label).

        :raises ValueError: when no menu entry corresponds to the given
            value — matches upstream's ``IllegalArgumentException``.
        """
        selection = int(zoom_value * 100)
        if selection not in self.ZOOMS:
            msg = f"no zoom menu item found for: {selection}%"
            raise ValueError(msg)
        self._zoom_var.set(f"{selection}%")

    @staticmethod
    def is_zoom_menu(action_command: str) -> bool:
        """Return ``True`` when ``action_command`` matches a zoom entry."""
        if not action_command.endswith("%"):
            return False
        try:
            zoom = int(action_command[:-1])
        except ValueError:
            return False
        return zoom in ZoomMenu.ZOOMS

    @staticmethod
    def get_zoom_scale() -> float:
        """Return the currently selected zoom as a multiplier.

        :raises RuntimeError: when nothing is selected (matches
            upstream's ``IllegalStateException``).
        """
        if ZoomMenu._instance is None:
            msg = "no zoom menu item is selected"
            raise RuntimeError(msg)
        raw = ZoomMenu._instance._zoom_var.get()
        if not raw or not raw.endswith("%"):
            msg = "no zoom menu item is selected"
            raise RuntimeError(msg)
        return int(raw[:-1]) / 100.0

    # --- page/image zoom (instance state, unchanged from upstream) -----

    def get_page_zoom_scale(self) -> float:
        return self._page_zoom_scale

    def set_page_zoom_scale(self, page_zoom_value: float) -> None:
        self._page_zoom_scale = page_zoom_value

    def get_image_zoom_scale(self) -> float:
        return self._image_zoom_scale

    def set_image_zoom_scale(self, image_zoom_value: float) -> None:
        self._image_zoom_scale = image_zoom_value

    def reset_zoom(self) -> None:
        """Reset both stored zooms and the selection back to 100 %."""
        self.set_page_zoom_scale(1.0)
        self.set_image_zoom_scale(1.0)
        self.change_zoom_selection(1.0)


__all__ = ["ZoomMenu"]
