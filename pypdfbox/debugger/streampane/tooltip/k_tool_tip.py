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
from typing import Any

from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK

from .color_tool_tip import ColorToolTip

_LOG = logging.getLogger(__name__)


class KToolTip(ColorToolTip):
    """Produce a swatch tooltip for non-stroking ``k`` and stroking ``K``."""

    def __init__(self, row_text: str) -> None:
        super().__init__()
        self.create_mark_up(row_text)

    def create_mark_up(self, row_text: str) -> None:
        """Compute the CMYK→RGB swatch markup for ``row_text``.

        Mirrors upstream ``KToolTip.createMarkUp``. Renamed from the
        previous private ``_create_markup``; the alias is preserved
        below for back-compat.
        """
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

    # Back-compat alias for the previous private spelling.
    _create_markup = create_mark_up

    def get_icc_profile(self) -> Any | None:
        """Return the CMYK ICC profile used for tooltip swatches.

        Mirrors upstream ``KToolTip.getICCProfile`` which streams
        ``CGATS001Compat-v2-micro.icc`` from classpath resources.
        pypdfbox does not bundle that profile (Pillow's built-in CMYK
        transform handles rendering, and :meth:`create_mark_up` uses
        the subtractive approximation), so we delegate to
        :meth:`PDDeviceCMYK.get_icc_profile`, which returns ``None``
        until a profile is installed.
        """
        return PDDeviceCMYK.INSTANCE.get_icc_profile()

    def get_icc_color_space(self) -> Any | None:
        """Return an ICC-backed color-space object for CMYK.

        Mirrors upstream ``KToolTip.getICCColorSpace``. Upstream wraps
        the profile in ``java.awt.color.ICC_ColorSpace`` and raises
        ``IOException`` when the profile is missing. pypdfbox returns
        the same value as :meth:`get_icc_profile` because there is no
        Python equivalent of ``ICC_ColorSpace``; callers needing a
        runtime CMYK→RGB conversion should use
        :meth:`PDDeviceCMYK.to_rgb` directly (as
        :meth:`create_mark_up` does).
        """
        profile = self.get_icc_profile()
        if profile is None:
            # Match upstream's contract: surface the absence as an OSError
            # so callers can distinguish "no profile" from "no operands".
            raise OSError("Default CMYK color profile could not be loaded")
        return profile
