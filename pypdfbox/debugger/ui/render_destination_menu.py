"""Tkinter port of ``RenderDestinationMenu``.

Mirrors ``org.apache.pdfbox.debugger.ui.RenderDestinationMenu`` — a
singleton menu that lets the debugger user pick between the
``EXPORT``, ``PRINT`` and ``VIEW`` rendering targets exposed by
:class:`pypdfbox.rendering.render_destination.RenderDestination`.
"""

from __future__ import annotations

from typing import ClassVar

from pypdfbox.rendering.render_destination import RenderDestination

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class RenderDestinationMenu(MenuBase):
    """Singleton menu for the ``RenderDestination`` enum."""

    RENDER_DESTINATION_EXPORT: ClassVar[str] = "Export"
    RENDER_DESTINATION_PRINT: ClassVar[str] = "Print"
    RENDER_DESTINATION_VIEW: ClassVar[str] = "View"

    _instance: ClassVar[RenderDestinationMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)

        self._master = master
        self.set_menu(self.create_menu())

    def create_menu(self) -> tk.Menu:  # type: ignore[name-defined]
        """Build and return the radio-group menu used by this singleton.

        Mirrors upstream ``RenderDestinationMenu.createMenu``. The three
        labels share a single :class:`tk.StringVar` so the menu acts as a
        Tk-equivalent ``ButtonGroup`` with ``EXPORT`` pre-selected.
        """
        menu = tk.Menu(self._master, tearoff=0)
        # Upstream selects EXPORT by default.
        self._destination_var = tk.StringVar(
            master=self._master, value=self.RENDER_DESTINATION_EXPORT
        )
        for label in (
            self.RENDER_DESTINATION_EXPORT,
            self.RENDER_DESTINATION_PRINT,
            self.RENDER_DESTINATION_VIEW,
        ):
            menu.add_radiobutton(label=label, value=label, variable=self._destination_var)
        return menu

    # Back-compat alias for the previously-private builder.
    _create_menu = create_menu

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> RenderDestinationMenu:  # type: ignore[name-defined]
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    # ------------------------------------------------------------------
    # Public API mirrored from upstream
    # ------------------------------------------------------------------

    def set_render_destination_selection(self, selection: str) -> None:
        """Select a render destination by label."""
        if selection not in (
            self.RENDER_DESTINATION_EXPORT,
            self.RENDER_DESTINATION_PRINT,
            self.RENDER_DESTINATION_VIEW,
        ):
            msg = f"Invalid RenderDestination selection: {selection}"
            raise ValueError(msg)
        self._destination_var.set(selection)

    @staticmethod
    def is_render_destination_menu(action_command: str) -> bool:
        return action_command in {
            RenderDestinationMenu.RENDER_DESTINATION_EXPORT,
            RenderDestinationMenu.RENDER_DESTINATION_PRINT,
            RenderDestinationMenu.RENDER_DESTINATION_VIEW,
        }

    @staticmethod
    def get_render_destination() -> RenderDestination:
        """Return the currently selected :class:`RenderDestination`."""
        if RenderDestinationMenu._instance is None:
            return RenderDestination.EXPORT
        current = RenderDestinationMenu._instance._destination_var.get()
        return RenderDestinationMenu.get_render_destination_for(current)

    @staticmethod
    def get_render_destination_for(action_command: str) -> RenderDestination:
        """Parse a label into a :class:`RenderDestination` enum value.

        Equivalent to upstream's overloaded
        ``getRenderDestination(String actionCommand)``; renamed to
        avoid Python's lack of method overloading.
        """
        if action_command == RenderDestinationMenu.RENDER_DESTINATION_EXPORT:
            return RenderDestination.EXPORT
        if action_command == RenderDestinationMenu.RENDER_DESTINATION_PRINT:
            return RenderDestination.PRINT
        if action_command == RenderDestinationMenu.RENDER_DESTINATION_VIEW:
            return RenderDestination.VIEW
        msg = f"Invalid RenderDestination actionCommand: {action_command}"
        raise ValueError(msg)


__all__ = ["RenderDestinationMenu"]
