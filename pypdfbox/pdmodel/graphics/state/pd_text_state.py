"""Current text-state parameters during content-stream execution.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.state.PDTextState``.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from .rendering_mode import RenderingMode

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_font import PDFont


class PDTextState:
    """Mutable bag of PDF text-state values (character spacing, font, etc.)."""

    def __init__(self) -> None:
        self._character_spacing: float = 0.0
        self._word_spacing: float = 0.0
        self._horizontal_scaling: float = 100.0
        self._leading: float = 0.0
        self._font: PDFont | None = None
        self._font_size: float = 0.0
        self._rendering_mode: RenderingMode = RenderingMode.FILL
        self._rise: float = 0.0
        self._knockout: bool = True

    def get_character_spacing(self) -> float:
        """Return character spacing (Tc)."""
        return self._character_spacing

    def set_character_spacing(self, value: float) -> None:
        """Set character spacing (Tc)."""
        self._character_spacing = float(value)

    def get_word_spacing(self) -> float:
        """Return word spacing (Tw)."""
        return self._word_spacing

    def set_word_spacing(self, value: float) -> None:
        """Set word spacing (Tw)."""
        self._word_spacing = float(value)

    def get_horizontal_scaling(self) -> float:
        """Return horizontal scaling (Th); percentage 0..100."""
        return self._horizontal_scaling

    def set_horizontal_scaling(self, value: float) -> None:
        """Set horizontal scaling (Th)."""
        self._horizontal_scaling = float(value)

    def get_leading(self) -> float:
        """Return text leading (Tl)."""
        return self._leading

    def set_leading(self, value: float) -> None:
        """Set text leading (Tl)."""
        self._leading = float(value)

    def get_font(self) -> PDFont | None:
        """Return the current font."""
        return self._font

    def set_font(self, value: PDFont | None) -> None:
        """Set the current font."""
        self._font = value

    def get_font_size(self) -> float:
        """Return font size (Tfs)."""
        return self._font_size

    def set_font_size(self, value: float) -> None:
        """Set font size (Tfs)."""
        self._font_size = float(value)

    def get_rendering_mode(self) -> RenderingMode:
        """Return rendering mode (Tr)."""
        return self._rendering_mode

    def set_rendering_mode(self, rendering_mode: RenderingMode) -> None:
        """Set rendering mode (Tr)."""
        self._rendering_mode = rendering_mode

    def get_rise(self) -> float:
        """Return text rise (Ts)."""
        return self._rise

    def set_rise(self, value: float) -> None:
        """Set text rise (Ts)."""
        self._rise = float(value)

    def get_knockout_flag(self) -> bool:
        """Return the knockout flag."""
        return self._knockout

    def set_knockout_flag(self, value: bool) -> None:
        """Set the knockout flag."""
        self._knockout = bool(value)

    def clone(self) -> PDTextState:
        """Return a shallow copy of the text state."""
        return copy.copy(self)


__all__ = ["PDTextState"]
