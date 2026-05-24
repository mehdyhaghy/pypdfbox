"""Tooltip for the ``scn`` / ``SCN`` (special color space) operators.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.SCNToolTip``.
"""

from __future__ import annotations

import logging

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.pd_resources import PDResources

from .color_tool_tip import ColorToolTip
from .tool_tip import ToolTipText

_LOG = logging.getLogger(__name__)


class SCNToolTip(ColorToolTip):
    """Produce a swatch tooltip for the special-color ``scn`` / ``SCN`` ops."""

    def __init__(
        self,
        resources: PDResources | None,
        color_space_name: str,
        row_text: str,
    ) -> None:
        super().__init__()
        # Upstream strips the leading ``/`` from the resource-key token,
        # then trims trailing whitespace.
        if color_space_name.startswith("/"):
            normalized = color_space_name[1:].strip()
        else:
            normalized = color_space_name.strip()
        self.create_mark_up(resources, normalized, row_text)

    def create_mark_up(
        self,
        resources: PDResources | None,
        color_space_name: str,
        row_text: str,
    ) -> None:
        """Build the tooltip markup for the special-color row.

        Mirrors upstream private ``createMarkUp(PDResources, String,
        String)`` (PDFBox 3.0 ``SCNToolTip``). Public on the Python
        port for parity tooling.
        """
        color_space = None
        if resources is not None:
            try:
                color_space = resources.get_color_space(COSName.get_pdf_name(color_space_name))
            except OSError as exc:  # pragma: no cover - I/O guard
                _LOG.error("%s", exc)

        if isinstance(color_space, PDPattern):
            # Patterns have no single sRGB swatch — upstream returns the
            # literal HTML string ``<html>Pattern</html>``. The plain
            # caption ``Pattern`` carries the same intent without HTML.
            self.set_tool_tip_text(ToolTipText(plain="Pattern", segments=()))
            return

        if color_space is None:
            return

        values = self.extract_color_values(row_text)
        if values is None:
            return
        try:
            rgb_values = color_space.to_rgb(values)
        except OSError as exc:  # pragma: no cover - I/O guard
            _LOG.error("%s", exc)
            return
        if rgb_values is None or len(rgb_values) < 3:
            return
        r, g, b = rgb_values[0], rgb_values[1], rgb_values[2]
        self.set_tool_tip_text(self.get_markup(self.color_hex_value((r, g, b))))

    # Back-compat private alias.
    _create_markup = create_mark_up
