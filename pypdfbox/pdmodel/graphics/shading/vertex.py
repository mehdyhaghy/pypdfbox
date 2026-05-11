"""Vertex data class for Type 4 / 5 shadings.

Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.shading.Vertex``.
"""

from __future__ import annotations

from collections.abc import Sequence


class Vertex:
    """A vertex carrying a 2D point and per-component color."""

    __slots__ = ("point", "color")

    def __init__(self, p: tuple[float, float], c: Sequence[float]) -> None:
        # Mirror Java semantics: defensive copy of the color array.
        self.point: tuple[float, float] = (float(p[0]), float(p[1]))
        self.color: list[float] = [float(v) for v in c]

    def to_string(self) -> str:
        """Mirror upstream ``Vertex.toString()``."""
        colors = " ".join(f"{c:3.2f}" for c in self.color)
        return f"Vertex{{ Point2D.Double[{self.point[0]}, {self.point[1]}], colors=[{colors}] }}"

    def __repr__(self) -> str:
        return self.to_string()
