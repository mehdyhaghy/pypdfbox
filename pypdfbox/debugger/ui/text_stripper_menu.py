"""Tk checkbox menu of options forwarded to ``PDFTextStripper``.

Ported from ``org.apache.pdfbox.debugger.ui.TextStripperMenu``. Upstream's
two ``JCheckBoxMenuItem`` entries become ``add_checkbutton`` entries backed
by ``BooleanVar``s. ``is_sorted()``/``is_ignore_spaces()`` read the current
state of those checkboxes, matching the upstream contract.
"""

from __future__ import annotations

from typing import ClassVar

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class TextStripperMenu(MenuBase):
    """Singleton menubar entry with text-extraction toggles."""

    SORT_LABEL: ClassVar[str] = "sort"
    IGNORE_SPACES_LABEL: ClassVar[str] = "ignore spaces"

    _instance: ClassVar[TextStripperMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)
        menu = tk.Menu(master, tearoff=0)
        self.set_menu(menu)
        self._sort_var = tk.BooleanVar(master=master, value=False)
        self._ignore_spaces_var = tk.BooleanVar(master=master, value=False)
        menu.add_checkbutton(label=self.SORT_LABEL, variable=self._sort_var)
        menu.add_checkbutton(label=self.IGNORE_SPACES_LABEL, variable=self._ignore_spaces_var)

    # --- singleton --------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> TextStripperMenu:  # type: ignore[name-defined]
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        cls._instance = None

    # --- state ------------------------------------------------------------

    @classmethod
    def is_sorted(cls) -> bool:
        """Return whether the "sort" checkbox is currently selected."""
        if cls._instance is None:
            return False
        return bool(cls._instance._sort_var.get())

    @classmethod
    def is_ignore_spaces(cls) -> bool:
        """Return whether the "ignore spaces" checkbox is currently selected."""
        if cls._instance is None:
            return False
        return bool(cls._instance._ignore_spaces_var.get())


__all__ = ["TextStripperMenu"]
