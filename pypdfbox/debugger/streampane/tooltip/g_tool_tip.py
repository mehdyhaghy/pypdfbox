"""Tooltip for the ``g`` / ``G`` (gray) color operators.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.GToolTip``.
"""

from __future__ import annotations

from .color_tool_tip import ColorToolTip


class GToolTip(ColorToolTip):
    """Produce a swatch tooltip for non-stroking ``g`` and stroking ``G``."""

    def __init__(self, row_text: str) -> None:
        super().__init__()
        self.create_mark_up(row_text)

    def create_mark_up(self, row_text: str) -> None:
        """Build the tooltip markup for the gray-value row.

        Mirrors upstream private ``createMarkUp(String)`` (PDFBox 3.0
        ``GToolTip``). Public on the Python port for parity tooling.
        """
        color_values = self.extract_color_values(row_text)
        if color_values is None or len(color_values) < 1:
            return
        gray = color_values[0]
        self.set_tool_tip_text(self.get_markup(self.color_hex_value((gray, gray, gray))))

    # Back-compat private alias kept for callers that pre-date the
    # public rename.
    _create_markup = create_mark_up
