"""An abstract class for tooltips of color operators.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.ColorToolTip``.
"""

from __future__ import annotations

from .tool_tip import ToolTip, ToolTipSegment, ToolTipText


class ColorToolTip(ToolTip):
    """Base for ``rg``/``RG``, ``k``/``K``, ``g``/``G``, ``scn``/``SCN``.

    Mirrors the upstream ``ColorToolTip``: subclasses extract the
    operator's operands from the row text and call
    :meth:`set_tool_tip_text` with the rendered payload (via
    :meth:`get_markup`).
    """

    def __init__(self) -> None:
        self._tool_tip_text: ToolTipText | None = None

    # ---- color helpers ----------------------------------------------------

    @staticmethod
    def color_hex_value(rgb: tuple[float, float, float]) -> str:
        """Return the six-digit lowercase hex value for ``(r, g, b)``.

        Mirrors upstream ``ColorToolTip.colorHexValue(Color)``. Each
        channel is expected in ``[0.0, 1.0]`` and clamped before
        formatting so out-of-gamut values from CMYK/ICC conversion
        never blow up the hex render.
        """
        r, g, b = rgb

        def _clamp(c: float) -> int:
            return max(0, min(255, round(c * 255.0)))

        return f"{_clamp(r):02x}{_clamp(g):02x}{_clamp(b):02x}"

    @staticmethod
    def extract_color_values(row_text: str) -> list[float] | None:
        """Extract the leading numeric operands from ``row_text``.

        The trailing operator token (e.g. ``rg``) is stripped, mirroring
        upstream ``ColorToolTip.extractColorValues``. Returns ``None``
        if any operand fails to parse — exactly matching the upstream
        ``NumberFormatException`` fallback.
        """
        from .tool_tip_controller import ToolTipController

        words = ToolTipController.get_words(row_text)
        if not words:
            return None
        # Drop the trailing operator token, like upstream
        # `words.remove(words.size() - 1)`.
        words = words[:-1]
        try:
            return [float(word) for word in words]
        except ValueError:
            return None

    # ---- markup -----------------------------------------------------------

    def get_markup(self, hex_value: str) -> ToolTipText:
        """Return a swatch-only tooltip payload.

        Upstream returns an HTML ``<div>`` with a 50x20 colored
        rectangle; we instead emit a single
        :class:`~pypdfbox.debugger.streampane.tooltip.tool_tip.ToolTipText`
        whose lone segment carries the hex value. The Tkinter consumer
        is responsible for the visual swatch geometry — see the module
        docstring for the HTML-to-structured-segment migration note.
        """
        return ToolTipText(
            plain=f"#{hex_value}",
            segments=(ToolTipSegment(text="", color_hex=hex_value),),
        )

    def set_tool_tip_text(self, tool_tip: ToolTipText | None) -> None:
        """Store the tooltip payload for :meth:`get_tool_tip_text`."""
        self._tool_tip_text = tool_tip

    def get_tool_tip_text(self) -> ToolTipText | None:
        return self._tool_tip_text
