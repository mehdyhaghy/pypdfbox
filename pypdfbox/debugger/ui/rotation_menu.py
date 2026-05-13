"""Tkinter port of ``RotationMenu``.

Mirrors ``org.apache.pdfbox.debugger.ui.RotationMenu`` — a singleton
menu offering the four cardinal page rotations.

Behavior preserved verbatim from upstream:

* Initial selection: ``0°``.
* :py:meth:`set_rotation_selection` raises on unrecognised labels.
* :py:meth:`is_rotation_menu` checks whether an action command label is
  one of the rotation entries.
* :py:meth:`get_rotation_degrees` returns the integer degree currently
  selected; the overload accepting an action command is exposed as
  :py:meth:`get_rotation_degrees_for` because Python lacks method
  overloads.
"""

from __future__ import annotations

from typing import ClassVar

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class RotationMenu(MenuBase):
    """Singleton menu for page rotations (0/90/180/270 degrees)."""

    ROTATE_0_DEGREES: ClassVar[str] = "0°"
    ROTATE_90_DEGREES: ClassVar[str] = "90°"
    ROTATE_180_DEGREES: ClassVar[str] = "180°"
    ROTATE_270_DEGREES: ClassVar[str] = "270°"

    _instance: ClassVar[RotationMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)

        menu = tk.Menu(master, tearoff=0)
        self.set_menu(menu)
        self._rotation_var = tk.StringVar(value=self.ROTATE_0_DEGREES)
        for label in (
            self.ROTATE_0_DEGREES,
            self.ROTATE_90_DEGREES,
            self.ROTATE_180_DEGREES,
            self.ROTATE_270_DEGREES,
        ):
            menu.add_radiobutton(label=label, value=label, variable=self._rotation_var)

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> RotationMenu:  # type: ignore[name-defined]
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_instance(cls) -> None:
        cls._instance = None

    # ------------------------------------------------------------------
    # Public API mirrored from upstream
    # ------------------------------------------------------------------

    def set_rotation_selection(self, selection: str) -> None:
        """Select a rotation entry by label.

        :raises ValueError: when ``selection`` is not a known label
            (mirrors upstream's ``IllegalArgumentException``).
        """
        if selection not in (
            self.ROTATE_0_DEGREES,
            self.ROTATE_90_DEGREES,
            self.ROTATE_180_DEGREES,
            self.ROTATE_270_DEGREES,
        ):
            msg = f"Invalid rotation selection: {selection}"
            raise ValueError(msg)
        self._rotation_var.set(selection)

    @staticmethod
    def is_rotation_menu(action_command: str) -> bool:
        return action_command in {
            RotationMenu.ROTATE_0_DEGREES,
            RotationMenu.ROTATE_90_DEGREES,
            RotationMenu.ROTATE_180_DEGREES,
            RotationMenu.ROTATE_270_DEGREES,
        }

    @staticmethod
    def get_rotation_degrees() -> int:
        """Return the currently selected rotation as an integer (0/90/180/270)."""
        if RotationMenu._instance is None:
            return 0
        value = RotationMenu._instance._rotation_var.get()
        return RotationMenu.get_rotation_degrees_for(value) if value else 0

    @staticmethod
    def get_rotation_degrees_for(action_command: str) -> int:
        """Parse a rotation label to its degree value.

        Equivalent to the upstream overload
        ``getRotationDegrees(String actionCommand)``; renamed to avoid
        a name clash with the zero-arg version above.
        """
        if action_command == RotationMenu.ROTATE_0_DEGREES:
            return 0
        if action_command == RotationMenu.ROTATE_90_DEGREES:
            return 90
        if action_command == RotationMenu.ROTATE_180_DEGREES:
            return 180
        if action_command == RotationMenu.ROTATE_270_DEGREES:
            return 270
        msg = f"Invalid RotationDegrees actionCommand {action_command}"
        raise ValueError(msg)


__all__ = ["RotationMenu"]
