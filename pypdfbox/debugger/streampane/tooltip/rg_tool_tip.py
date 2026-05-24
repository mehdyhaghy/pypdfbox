"""Tooltip for the ``rg`` / ``RG`` color operators.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.RGToolTip``.
"""

from __future__ import annotations

from .color_tool_tip import ColorToolTip


class RGToolTip(ColorToolTip):
    """Produce a swatch tooltip for non-stroking ``rg`` and stroking ``RG``."""

    def __init__(self, row_text: str) -> None:
        super().__init__()
        self.create_mark_up(row_text)

    def create_mark_up(self, row_text: str) -> None:
        """Build the tooltip markup for the RGB-tuple row.

        Mirrors upstream private ``createMarkUp(String)`` (PDFBox 3.0
        ``RGToolTip``). Public on the Python port for parity tooling.
        """
        rgb_values = self.extract_color_values(row_text)
        if rgb_values is None or len(rgb_values) < 3:
            return
        r, g, b = rgb_values[0], rgb_values[1], rgb_values[2]
        self.set_tool_tip_text(self.get_markup(self.color_hex_value((r, g, b))))

    # Back-compat private alias.
    _create_markup = create_mark_up
