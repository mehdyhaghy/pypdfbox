"""Tooltip for the ``k`` / ``K`` (CMYK) color operators.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.KToolTip``.

Upstream loads the bundled ``CGATS001Compat-v2-micro.icc`` profile
through ``java.awt.color.ICC_ColorSpace`` and converts CMYK→RGB through
the JDK's color-management pipeline. pypdfbox's existing
:class:`~pypdfbox.pdmodel.graphics.color.pd_device_cmyk.PDDeviceCMYK`
applies a subtractive ``(1-c)(1-k)`` approximation that matches the
formula used everywhere else in the port (see ``PDDeviceCMYK.to_rgb``
for the rationale). We delegate to that path so the tooltip's swatch
agrees with what the renderer actually paints. See ``CHANGES.md`` for
the ICC-vs-subtractive deviation note.
"""

from __future__ import annotations

import logging

from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK

from .color_tool_tip import ColorToolTip

_LOG = logging.getLogger(__name__)


class KToolTip(ColorToolTip):
    """Produce a swatch tooltip for non-stroking ``k`` and stroking ``K``."""

    def __init__(self, row_text: str) -> None:
        super().__init__()
        self._create_markup(row_text)

    def _create_markup(self, row_text: str) -> None:
        color_values = self.extract_color_values(row_text)
        if color_values is None or len(color_values) < 4:
            return
        try:
            rgb_values = PDDeviceCMYK.INSTANCE.to_rgb(color_values[:4])
        except OSError as exc:  # pragma: no cover - I/O guard
            _LOG.error("%s", exc)
            return
        r, g, b = rgb_values[0], rgb_values[1], rgb_values[2]
        self.set_tool_tip_text(self.get_markup(self.color_hex_value((r, g, b))))
