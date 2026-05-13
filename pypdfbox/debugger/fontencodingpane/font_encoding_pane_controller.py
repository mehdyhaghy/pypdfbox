"""Dispatcher for the font-encoding panes.

Ported from ``org.apache.pdfbox.debugger.fontencodingpane.FontEncodingPaneController``.

Resolves a font by name through a :class:`PDResources` dictionary and
returns the appropriate :class:`SimpleFont`, :class:`Type0Font`, or
:class:`Type3Font` pane.
"""

from __future__ import annotations

import logging
import tkinter as tk
from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary
from pypdfbox.debugger.fontencodingpane.font_pane import FontPane
from pypdfbox.debugger.fontencodingpane.simple_font import SimpleFont
from pypdfbox.debugger.fontencodingpane.type0_font import Type0Font
from pypdfbox.debugger.fontencodingpane.type3_font import Type3Font
from pypdfbox.pdmodel.font import (
    PDFontFactory,
    PDSimpleFont,
    PDType0Font,
    PDType3Font,
)
from pypdfbox.pdmodel.pd_resources import PDResources

if TYPE_CHECKING:
    from pypdfbox.cos import COSName

_LOG = logging.getLogger(__name__)


class FontEncodingPaneController:
    """Resolve a font and produce its encoding pane.

    Mirrors upstream ``FontEncodingPaneController`` (public). The
    constructor performs the lookup eagerly so :meth:`get_pane` is a
    simple accessor.
    """

    def __init__(
        self,
        font_name: COSName,
        dictionary: COSDictionary,
        master: tk.Misc | None = None,
    ) -> None:
        """Build the controller.

        :param font_name: ``COSName`` of the entry in ``dictionary`` to
            inspect.
        :param dictionary: a ``/Resources``-shaped :class:`COSDictionary`
            (the controller wraps it in :class:`PDResources`).
        :param master: parent Tk widget — propagated to the rendered
            pane's view.
        """
        self._font_pane: FontPane | None = None
        resources = PDResources(dictionary)
        try:
            font = resources.get_font(font_name)
        except OSError as exc:
            _LOG.error("Failed to load font %s: %s", font_name, exc)
            return

        # ``PDResources.get_font`` may return a raw ``COSDictionary``
        # when the entry is direct (no indirect-object wrapper). Wrap
        # via :class:`PDFontFactory` so the dispatch below sees a typed
        # font instance.
        if isinstance(font, COSDictionary):
            try:
                font = PDFontFactory.create_font(font)
            except OSError as exc:
                _LOG.error("Failed to wrap direct font %s: %s", font_name, exc)
                return

        if font is None or not hasattr(font, "get_cos_object"):
            return

        try:
            if isinstance(font, PDType3Font):
                self._font_pane = Type3Font(font, resources, master)
            elif isinstance(font, PDSimpleFont):
                self._font_pane = SimpleFont(font, master)
            elif isinstance(font, PDType0Font):
                descendant = font.get_descendant_font()
                if descendant is not None:
                    self._font_pane = Type0Font(descendant, font, master)
        except OSError as exc:
            _LOG.error("Failed to render encoding pane for %s: %s", font_name, exc)

    def get_pane(self) -> tk.Misc | None:
        """Return the rendered pane widget, or ``None`` for unsupported types.

        Mirrors upstream ``JPanel getPane()``.
        """
        if self._font_pane is None:
            return None
        return self._font_pane.get_panel()

    @property
    def font_pane(self) -> FontPane | None:
        """Underlying :class:`FontPane` (testing hook)."""
        return self._font_pane
