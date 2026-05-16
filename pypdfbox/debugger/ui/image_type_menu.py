"""Tk radio-group menu for selecting the renderer's output image type.

Ported from ``org.apache.pdfbox.debugger.ui.ImageTypeMenu``. Upstream is a
Swing singleton wrapping a ``JMenu`` populated with ``JRadioButtonMenuItem``
entries (RGB / ARGB / Gray / Bitonal). We port to ``tkinter.Menu`` populated
with ``add_radiobutton`` entries sharing a single ``StringVar``.

The selection is exposed via ``get_image_type()``/``set_image_type_selection``
in lock-step with the upstream API.
"""

from __future__ import annotations

from typing import ClassVar

from pypdfbox.rendering.image_type import ImageType

from .menu_base import MenuBase

try:  # pragma: no cover - tkinter is stdlib but might be missing in slim images.
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None  # type: ignore[assignment]


class ImageTypeMenu(MenuBase):
    """Singleton menubar entry for choosing the renderer's image type."""

    IMAGETYPE_RGB: ClassVar[str] = "RGB"
    IMAGETYPE_ARGB: ClassVar[str] = "ARGB"
    IMAGETYPE_GRAY: ClassVar[str] = "Gray"
    IMAGETYPE_BITONAL: ClassVar[str] = "Bitonal"

    _LABELS: ClassVar[tuple[str, ...]] = (
        IMAGETYPE_RGB,
        IMAGETYPE_ARGB,
        IMAGETYPE_GRAY,
        IMAGETYPE_BITONAL,
    )
    _IMAGE_TYPE_BY_LABEL: ClassVar[dict[str, ImageType]] = {
        IMAGETYPE_RGB: ImageType.RGB,
        IMAGETYPE_ARGB: ImageType.ARGB,
        IMAGETYPE_GRAY: ImageType.GRAY,
        IMAGETYPE_BITONAL: ImageType.BINARY,
    }

    _instance: ClassVar[ImageTypeMenu | None] = None

    def __init__(self, master: tk.Misc | None = None) -> None:  # type: ignore[name-defined]
        super().__init__()
        if tk is None:  # pragma: no cover - defensive
            msg = "tkinter is not available"
            raise RuntimeError(msg)
        self._master = master
        self.set_menu(self.create_menu())

    def create_menu(self) -> tk.Menu:  # type: ignore[name-defined]
        """Build and return the radio-group ``tk.Menu`` used by this menubar entry.

        Mirrors upstream ``ImageTypeMenu.createMenu``. The four labels share
        a single :class:`tk.StringVar` so selecting one entry deselects the
        others (the Tk analogue of Swing's ``ButtonGroup``).
        """
        menu = tk.Menu(self._master, tearoff=0)
        self._var = tk.StringVar(master=self._master, value=self.IMAGETYPE_RGB)
        for label in self._LABELS:
            menu.add_radiobutton(label=label, value=label, variable=self._var)
        return menu

    # Back-compat alias for the previously-private builder.
    _create_menu = create_menu

    # --- singleton --------------------------------------------------------

    @classmethod
    def get_instance(cls, master: tk.Misc | None = None) -> ImageTypeMenu:  # type: ignore[name-defined]
        """Return the lazily-created singleton."""
        if cls._instance is None:
            cls._instance = cls(master=master)
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Clear the singleton. Tests only."""
        cls._instance = None

    # --- selection --------------------------------------------------------

    def set_image_type_selection(self, selection: str) -> None:
        """Mark ``selection`` as the active radio entry.

        :raises ValueError: when ``selection`` is not a known image type label.
        """
        if selection not in self._IMAGE_TYPE_BY_LABEL:
            raise ValueError(f"Invalid ImageType selection: {selection}")
        self._var.set(selection)

    @staticmethod
    def is_image_type_menu(action_command: str) -> bool:
        """Return ``True`` if ``action_command`` is one of our labels."""
        return action_command in ImageTypeMenu._IMAGE_TYPE_BY_LABEL

    @classmethod
    def get_image_type(cls, action_command: str | None = None) -> ImageType:
        """Return the ImageType for ``action_command``, or the current selection.

        :raises ValueError: when ``action_command`` is supplied but unknown.
        :raises RuntimeError: when called with no argument and the singleton
            has not been instantiated yet.
        """
        if action_command is not None:
            try:
                return cls._IMAGE_TYPE_BY_LABEL[action_command]
            except KeyError as exc:
                raise ValueError(
                    f"Invalid ImageType actionCommand: {action_command}",
                ) from exc
        if cls._instance is None:
            raise RuntimeError("ImageTypeMenu has not been instantiated")
        return cls._IMAGE_TYPE_BY_LABEL.get(cls._instance._var.get(), ImageType.RGB)


__all__ = ["ImageTypeMenu"]
