"""Plain-data record for one Indexed-color-space entry.

Ported from ``org.apache.pdfbox.debugger.colorpane.IndexedColorant``.

Upstream stores raw float RGB values and re-constructs a
``java.awt.Color`` on demand via ``getColor``. We keep the same shape:
``rgb_values`` is a list of floats in ``[0, 1]`` (typically length 3 —
upstream's ``Color(float, float, float)`` ctor requires exactly that),
and :meth:`get_color` returns a ``tuple[float, float, float]`` instead
of an AWT ``Color`` so the data record stays UI-toolkit-agnostic.
"""

from __future__ import annotations


class IndexedColorant:
    """One palette entry of a ``/Indexed`` color space.

    Mirrors upstream's mutable JavaBean — empty no-arg constructor plus
    getter/setter pairs for ``index`` and ``rgb_values``, and the
    derived ``get_color`` / ``get_rgb_values_string`` accessors.
    """

    def __init__(self) -> None:
        # Upstream comment: "// do nothing". Fields populated via setters.
        self._index: int = 0
        self._rgb_values: list[float] | None = None

    def get_index(self) -> int:
        return self._index

    def set_index(self, index: int) -> None:
        self._index = index

    def set_rgb_values(self, rgb_values: list[float]) -> None:
        self._rgb_values = list(rgb_values)

    def get_color(self) -> tuple[float, float, float]:
        """Return the float-RGB tuple matching upstream ``getColor()``.

        Upstream returns ``new Color(rgbValues[0], rgbValues[1],
        rgbValues[2])`` — a ``java.awt.Color`` built from floats in
        ``[0, 1]``. We return the same three floats so callers don't
        need an AWT dependency.
        """
        if self._rgb_values is None or len(self._rgb_values) < 3:
            raise ValueError(
                "rgb_values must be set with at least 3 components before "
                "calling get_color()"
            )
        return (
            self._rgb_values[0],
            self._rgb_values[1],
            self._rgb_values[2],
        )

    def get_rgb_values_string(self) -> str:
        """Return ``"<r>, <g>, <b>"`` with each channel scaled to 0..255.

        Mirrors upstream's ``getRGBValuesString()`` which iterates the
        ``rgbValues`` array, casts each ``float`` to ``int`` after a
        ``*255`` scale, joins them with ``", "`` and trims the trailing
        comma.
        """
        if self._rgb_values is None:
            return ""
        parts = [str(int(value * 255)) for value in self._rgb_values]
        return ", ".join(parts)
