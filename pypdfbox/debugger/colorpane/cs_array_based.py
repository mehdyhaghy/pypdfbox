"""Generic color-space inspector pane.

Ported from ``org.apache.pdfbox.debugger.colorpane.CSArrayBased``.

Shows a title plus a handful of summary labels for color spaces that
have no special UI (everything except DeviceN / Indexed /
Separation). When the color space is :class:`PDICCBased` we surface
its ``ColorSpace`` type integer and ``isSRGB`` flag.

Swing → Tkinter mapping:
* ``JPanel`` + ``BoxLayout.Y_AXIS`` → ``ttk.Frame`` with ``pack``-ed
  children stacked vertically.
* Monospaced bold ``JLabel`` → ``ttk.Label`` with a ``tkfont.Font``
  configured for ``Courier`` bold.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_icc_based import (
    TYPE_CMYK,
    TYPE_GRAY,
    TYPE_RGB,
    PDICCBased,
)
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

# ``java.awt.color.ColorSpace`` constant integers mirrored here so the
# upstream switch maps cleanly. AWT defines the ``CS_*`` set as
# named-color-space identifiers (separate from the ``TYPE_*`` family
# already exported by :mod:`pypdfbox.pdmodel.graphics.color.pd_icc_based`).
CS_XYZ = 1001
CS_LINEAR_RGB = 1004
CS_PYCC = 1002
CS_GRAY = 1003
CS_SRGB = 1000


class CSArrayBased:
    """Inspector for any array-form color space that lacks a custom UI."""

    def __init__(
        self, array: COSArray, master: tk.Misc | None = None
    ) -> None:
        """Build the pane.

        :param array: COSArray for the color space (the ``[/Name …]``
            form that ``PDColorSpace.create`` consumes).
        :param master: parent Tk widget. ``None`` falls back to the
            implicit default root.
        """
        self._panel: ttk.Frame | None = None
        self._color_space: PDColorSpace | None = None
        self._number_of_components: int = 0
        self._errmsg: str = ""

        try:
            self._color_space = PDColorSpace.create(array)
            # PDColorSpace.create can return None when ``array`` doesn't
            # name a recognised CS — upstream's analogous branch would
            # have thrown IOException, which we surface as an empty
            # color-space (the no-CS message path below).
            if self._color_space is not None and not isinstance(
                self._color_space, PDPattern
            ):
                self._number_of_components = (
                    self._color_space.get_number_of_components()
                )
        except OSError as ex:
            # Upstream catches IOException from PDColorSpace.create — in
            # pypdfbox the analogue is OSError (or its parser-specific
            # subclasses) per the project's exception mapping convention.
            self._errmsg = str(ex)

        self.init_ui(master)

    # ---- UI ---------------------------------------------------------------

    def init_ui(self, master: tk.Misc | None) -> None:
        """Build the inspector widgets.

        Mirrors upstream private ``CSArrayBased.initUI()``. Public on the
        Python port so headless callers / parity tooling can rebuild the
        widget tree on demand. The upstream method takes no arguments;
        Tkinter requires the parent widget here.
        """
        panel = ttk.Frame(master)
        # Approximate upstream's ``setPreferredSize(new Dimension(300,
        # 500))``. ``configure(width=, height=)`` may fail in headless
        # test environments — ignore.
        with contextlib.suppress(tk.TclError):
            panel.configure(width=300, height=500)
        self._panel = panel

        if self._color_space is None:
            err_font = tkfont.Font(
                family="Courier", size=15, weight=tkfont.BOLD
            )
            ttk.Label(panel, text=self._errmsg, font=err_font).pack(
                anchor="center", padx=4, pady=4
            )
            return

        header_font = tkfont.Font(family="Courier", size=30, weight=tkfont.BOLD)
        sub_font = tkfont.Font(family="Courier", size=20, weight=tkfont.BOLD)

        ttk.Label(
            panel,
            text=f"{self._color_space.get_name()} colorspace",
            font=header_font,
        ).pack(anchor="center", padx=4, pady=(4, 0))

        if self._number_of_components > 0:
            ttk.Label(
                panel,
                text=f"Component Count: {self._number_of_components}",
                font=sub_font,
            ).pack(anchor="center", padx=4)

        if isinstance(self._color_space, PDICCBased):
            color_space_type = self._color_space.get_color_space_type()
            cs_name = _format_color_space_type(color_space_type)
            ttk.Label(
                panel, text=f"Colorspace type: {cs_name}", font=sub_font
            ).pack(anchor="center", padx=4)
            ttk.Label(
                panel,
                text=f"sRGB: {self._color_space.is_srgb()}",
                font=sub_font,
            ).pack(anchor="center", padx=4)

    # Back-compat private alias.
    _init_ui = init_ui

    # ---- public surface ---------------------------------------------------

    def get_panel(self) -> ttk.Frame | None:
        """Return the main panel that holds all the UI elements.

        Mirrors upstream ``CSArrayBased.getPanel()`` which returns the
        underlying ``Component``.
        """
        return self._panel


def _format_color_space_type(color_space_type: int) -> str:
    """Map an AWT ``ColorSpace`` type integer to upstream's label."""
    # Upstream switch — keep the same labels for parity.
    if color_space_type == CS_LINEAR_RGB:
        return "linear RGB"
    if color_space_type == CS_XYZ:
        return "CIEXYZ"
    if color_space_type == CS_GRAY:
        return "linear gray"
    if color_space_type == CS_SRGB:
        return "sRGB"
    if color_space_type == TYPE_RGB:
        return "RGB"
    if color_space_type == TYPE_GRAY:
        return "gray"
    if color_space_type == TYPE_CMYK:
        return "CMYK"
    return f"type {color_space_type}"
