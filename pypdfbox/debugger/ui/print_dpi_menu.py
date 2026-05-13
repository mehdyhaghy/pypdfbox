"""Tk radio-group menu for selecting print-rastering DPI.

Ported from ``org.apache.pdfbox.debugger.ui.PrintDpiMenu``. Upstream's
``JRadioButtonMenuItem`` set becomes a ``tk.Menu`` of ``add_radiobutton``
entries sharing an ``IntVar``.

The DPI list mirrors upstream exactly:
``0`` (off), ``100``, ``200``, ``300``, ``600``, ``1200``, ``-1`` (printer dpi).
"""

from __future__ import annotations

from typing import ClassVar

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class PrintDpiMenu(MenuBase):
    """Singleton menubar entry for choosing the print rastering DPI."""

    DPIS: ClassVar[tuple[int, ...]] = (0, 100, 200, 300, 600, 1200, -1)

    _instance: ClassVar[PrintDpiMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)
        menu = tk.Menu(master, tearoff=0)
        self.set_menu(menu)
        self._var = tk.IntVar(master=master, value=0)
        for dpi in self.DPIS:
            menu.add_radiobutton(label=self._label_for(dpi), value=dpi, variable=self._var)
        # Match upstream: PrintDpiMenu constructor explicitly seeds the
        # selection to ``0`` ("off") after building the radio set.
        self.change_dpi_selection(0)

    # --- singleton --------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> PrintDpiMenu:  # type: ignore[name-defined]
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls._instance = None

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _label_for(dpi: int) -> str:
        if dpi == 0:
            return "off"
        if dpi == -1:
            return "printer dpi"
        return f"{dpi} dpi"

    # --- selection --------------------------------------------------------

    def change_dpi_selection(self, selection: int) -> None:
        """Mark ``selection`` as the active DPI.

        :raises ValueError: when ``selection`` isn't a known DPI preset.
        """
        if selection not in self.DPIS:
            raise ValueError(f"no dpi menu item found for: {selection}")
        self._var.set(selection)

    @classmethod
    def get_dpi_selection(cls) -> int:
        """Return the currently selected DPI value.

        :raises RuntimeError: when no instance exists yet.
        """
        if cls._instance is None:
            raise RuntimeError("no dpi menu item is selected")
        return int(cls._instance._var.get())


__all__ = ["PrintDpiMenu"]
