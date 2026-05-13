"""Plain-data record for one DeviceN colorant.

Ported from ``org.apache.pdfbox.debugger.colorpane.DeviceNColorant``.

Upstream stores ``maximum`` / ``minimum`` as ``java.awt.Color`` instances
created from float RGB values in ``[0, 1]``. We keep the same shape but
store the colors as ``tuple[float, float, float]`` (r, g, b) so the
record stays purely a data class — Tkinter rendering converts the tuple
to ``#RRGGBB`` at draw time.
"""

from __future__ import annotations


class DeviceNColorant:
    """One colorant in a ``/DeviceN`` color space.

    Mirrors upstream's mutable JavaBean — empty no-arg constructor plus
    getter/setter pairs for ``name``, ``maximum``, ``minimum``.
    """

    def __init__(self) -> None:
        # Upstream comment: "// do nothing". Fields default to None and
        # are populated via setters (mirrors the JavaBean idiom).
        self._name: str | None = None
        self._maximum: tuple[float, float, float] | None = None
        self._minimum: tuple[float, float, float] | None = None

    def get_name(self) -> str | None:
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name

    def get_maximum(self) -> tuple[float, float, float] | None:
        return self._maximum

    def set_maximum(self, maximum: tuple[float, float, float]) -> None:
        self._maximum = maximum

    def get_minimum(self) -> tuple[float, float, float] | None:
        return self._minimum

    def set_minimum(self, minimum: tuple[float, float, float]) -> None:
        self._minimum = minimum
