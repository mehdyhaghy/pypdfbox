"""Tooltip for the ``Tf`` (set font and size) operator.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.FontToolTip``.
"""

from __future__ import annotations

import logging

from pypdfbox.pdmodel.pd_resources import PDResources

from .tool_tip import ToolTip, ToolTipSegment, ToolTipText

_LOG = logging.getLogger(__name__)


class FontToolTip(ToolTip):
    """Show the resolved font name for a ``/Fxx <size> Tf`` row.

    Mirrors upstream ``FontToolTip`` — does not inherit ``ColorToolTip``
    because no color swatch is rendered.
    """

    def __init__(self, resources: PDResources | None, row_text: str) -> None:
        self._markup: ToolTipText | None = None
        self.init_ui(self.extract_font_reference(row_text), resources)

    def init_ui(
        self, font_reference_name: str, resources: PDResources | None
    ) -> None:
        """Populate ``self._markup`` from the resource dictionary.

        Mirrors upstream ``FontToolTip.initUI``. Renamed from the
        previous private ``_init_ui``; the alias is preserved below.
        """
        if resources is None or not font_reference_name:
            return
        font = None
        for name in resources.get_font_names():
            if name.get_name() == font_reference_name:
                try:
                    font = resources.get_font(name)
                except OSError as exc:  # pragma: no cover - I/O guard
                    _LOG.error("%s", exc)
        if font is not None:
            font_name = getattr(font, "get_name", lambda: None)()
            if font_name:
                self._markup = ToolTipText(
                    plain=font_name,
                    segments=(ToolTipSegment(text=font_name, color_hex=None),),
                )

    # Back-compat alias for the previous private spelling.
    _init_ui = init_ui

    @staticmethod
    def extract_font_reference(row_text: str) -> str:
        """Return the font reference name from a ``/Fxx <size> Tf`` row.

        Upstream: ``rowText.trim().split(" ")[0].substring(1)`` — i.e.
        drop the first character (the leading ``/``) from the first
        token. We replicate that exactly, including the malformed-input
        behavior where a missing slash yields a truncated key that
        won't match any resource entry.
        """
        tokens = row_text.strip().split(" ")
        if not tokens or not tokens[0]:
            return ""
        return tokens[0][1:]

    # Back-compat alias for the previous private spelling.
    _extract_font_reference = extract_font_reference

    def get_tool_tip_text(self) -> ToolTipText | None:
        return self._markup
