from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDFont


class AppearanceStyle:
    """Define styling attributes used for text formatting. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.AppearanceStyle``
    (upstream lines 25–101).

    Holds the font, font size, and leading used when generating field
    appearances. Setting the font size updates ``leading`` to
    ``font_size * 1.2`` (Acrobat default) to match upstream.
    """

    _DEFAULT_FONT_SIZE: float = 12.0
    _DEFAULT_LEADING: float = 14.4  # 1.2 * 12.0

    def __init__(self) -> None:
        self._font: PDFont | None = None
        self._font_size: float = self._DEFAULT_FONT_SIZE
        self._leading: float = self._DEFAULT_LEADING

    # ---------- font ----------

    def get_font(self) -> PDFont | None:
        """Return the font used for text formatting, or ``None``."""
        return self._font

    def set_font(self, font: PDFont | None) -> None:
        """Set the font to be used for text formatting."""
        self._font = font

    # ---------- font size ----------

    def get_font_size(self) -> float:
        """Return the font size used for text formatting."""
        return self._font_size

    def set_font_size(self, font_size: float) -> None:
        """Set the font size and recompute leading as ``font_size * 1.2``
        — mirrors upstream's coupled setter."""
        self._font_size = font_size
        self._leading = font_size * 1.2

    # ---------- leading ----------

    def get_leading(self) -> float:
        """Return the leading (line distance) used for text formatting."""
        return self._leading

    def set_leading(self, leading: float) -> None:
        """Set the leading used for text formatting."""
        self._leading = leading


__all__ = ["AppearanceStyle"]
