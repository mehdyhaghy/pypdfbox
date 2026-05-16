"""Separation color-space inspector.

Ported from ``org.apache.pdfbox.debugger.colorpane.CSSeparation``.

Renders a header label, a colorant-name label, a slider + text-field
pair for the tint value and a colored canvas (the "color bar") that
reflects the current tint.

Swing → Tkinter mapping:
* ``JPanel`` + ``GridBagLayout`` → ``ttk.Frame`` with ``grid`` placement.
* ``JSlider`` → ``ttk.Scale`` (0..100).
* ``JTextField`` → ``ttk.Entry`` bound to a ``tk.StringVar``.
* ``JLabel`` with opaque background → ``tk.Canvas``.

Upstream implements ``ChangeListener`` (slider) + ``ActionListener``
(text-field Enter key); the Tkinter port wires ``command=`` on the
``ttk.Scale`` and ``<Return>``/``<FocusOut>`` on the entry to two
private methods with matching semantics.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from pypdfbox.cos import COSArray
from pypdfbox.debugger.colorpane.color_bar_cell_renderer import (
    ColorBarCellRenderer,
)
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation


class CSSeparation:
    """Tkinter inspector for a ``/Separation`` color space."""

    def __init__(
        self, array: COSArray, master: tk.Misc | None = None
    ) -> None:
        """Build the pane.

        :param array: COSArray for the Separation color space.
        :param master: parent Tk widget. ``None`` falls back to the
            implicit default root.

        :raises OSError: when ``PDSeparation`` cannot be created.
        """
        self._separation = PDSeparation(array)
        self._tint_value: float = 1.0
        self._panel: ttk.Frame | None = None
        self._slider: ttk.Scale | None = None
        self._tint_field: ttk.Entry | None = None
        self._tint_var: tk.StringVar | None = None
        self._color_bar: tk.Canvas | None = None
        self._renderer = ColorBarCellRenderer()
        # ``_syncing`` guards re-entrant updates: when the slider sets
        # the entry's text or vice versa, we don't want the resulting
        # variable-change event to bounce back and re-run the partner
        # update. Upstream side-steps this because ``JSlider.setValue``
        # is a no-op when the value is unchanged, but Tk's ``StringVar``
        # always fires.
        self._syncing: bool = False
        self.init_ui(master)
        self.init_values()

    # ---- UI ---------------------------------------------------------------

    def init_ui(self, master: tk.Misc | None) -> None:
        """Initialise all UI elements and arrange them.

        Mirrors upstream ``CSSeparation.initUI()``. Public so headless
        callers / tests can rebuild the widget tree on demand. Note the
        signature deviates from upstream which took no arguments —
        Tkinter requires the parent widget here.
        """
        bold_font = tkfont.Font(family="Courier", size=20, weight=tkfont.BOLD)
        header_font = tkfont.Font(family="Courier", size=30, weight=tkfont.BOLD)
        small_font = tkfont.Font(family="Courier", size=10, weight=tkfont.BOLD)

        panel = ttk.Frame(master)
        with contextlib.suppress(tk.TclError):
            panel.configure(width=300, height=500)
        self._panel = panel

        ttk.Label(
            panel, text="Separation colorspace", font=header_font
        ).pack(anchor="center", padx=4, pady=(4, 0))

        main_panel = ttk.Frame(panel)
        main_panel.pack(fill="both", expand=True, padx=4, pady=4)

        colorant_name = self._separation.get_colorant_name() or ""
        ttk.Label(
            main_panel,
            text=f"Colorant: {colorant_name}",
            font=bold_font,
        ).grid(row=0, column=0, sticky="w", padx=2, pady=2)

        content_panel = ttk.Frame(main_panel)
        content_panel.grid(
            row=1, column=0, sticky="nsew", padx=2, pady=2
        )

        input_panel = ttk.Frame(content_panel)
        input_panel.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Slider 0..100 with label markers — Tkinter's ``ttk.Scale``
        # has no built-in tick-label support so we approximate with a
        # row of ``ttk.Label`` widgets beneath the scale.
        slider = ttk.Scale(input_panel, from_=0, to=100, command=self.state_changed)
        slider.grid(row=0, column=0, columnspan=3, sticky="ew", padx=2, pady=2)

        ttk.Label(input_panel, text="lightest", font=small_font).grid(
            row=1, column=0, sticky="w", padx=2
        )
        ttk.Label(input_panel, text="0.5", font=small_font).grid(
            row=1, column=1, sticky="n", padx=2
        )
        ttk.Label(input_panel, text="darkest", font=small_font).grid(
            row=1, column=2, sticky="e", padx=2
        )

        ttk.Label(input_panel, text="Tint Value:", font=bold_font).grid(
            row=2, column=0, sticky="w", padx=2, pady=2
        )

        self._tint_var = tk.StringVar()
        tint_field = ttk.Entry(input_panel, textvariable=self._tint_var)
        tint_field.grid(row=2, column=1, columnspan=2, sticky="ew", padx=2, pady=2)
        tint_field.bind("<Return>", self._on_tint_entry)
        tint_field.bind("<FocusOut>", self._on_tint_entry)

        input_panel.columnconfigure(1, weight=1)
        input_panel.columnconfigure(2, weight=1)

        color_bar = tk.Canvas(content_panel, width=120, height=80)
        color_bar.grid(row=0, column=1, sticky="nsew", padx=4, pady=2)
        content_panel.columnconfigure(0, weight=3)
        content_panel.columnconfigure(1, weight=7)

        main_panel.columnconfigure(0, weight=1)
        main_panel.rowconfigure(1, weight=1)

        self._slider = slider
        self._tint_field = tint_field
        self._color_bar = color_bar
        # Border depends on PDSeparation.to_rgb succeeding — if the
        # alternate or tint transform is missing, swallow the error
        # and skip border styling (matches upstream's IOException
        # tolerance in initUI).
        with contextlib.suppress(OSError, tk.TclError):
            self.set_color_bar_border()

    # Back-compat private alias.
    _init_ui = init_ui

    def init_values(self) -> None:
        """Sync slider/text-field/color-bar with the current tint value.

        Mirrors upstream ``CSSeparation.initValues()``. Used at
        construction time and any time callers want to re-display the
        current ``tint_value`` (e.g. after programmatic mutation).
        """
        assert self._slider is not None
        assert self._tint_var is not None
        self._syncing = True
        try:
            self._slider.set(self.get_int_representation(self._tint_value))
            self._tint_var.set(str(self._tint_value))
        finally:
            self._syncing = False
        with contextlib.suppress(OSError):
            self.update_color_bar()

    # Back-compat private alias.
    _init_values = init_values

    # ---- listeners --------------------------------------------------------

    def state_changed(self, raw_value: str | None = None) -> None:
        """Slider moved — update tint, entry and color bar.

        Mirrors upstream ``stateChanged(ChangeEvent)``. The Tk port
        receives the slider's current value as a string (Tk's
        ``command=`` callback signature); the optional ``None`` default
        lets callers re-trigger a sync from the live slider value.
        """
        if self._syncing:
            return
        if raw_value is None and self._slider is not None:
            raw_value = str(self._slider.get())
        try:
            value = int(float(raw_value))
        except (TypeError, ValueError):
            return
        self._tint_value = self.get_float_representation(value)
        self._syncing = True
        try:
            assert self._tint_var is not None
            self._tint_var.set(str(self._tint_value))
        finally:
            self._syncing = False
        try:
            self.update_color_bar()
        except OSError as ex:
            assert self._tint_var is not None
            self._tint_var.set(str(ex))

    # Back-compat private alias for the slider callback wiring.
    _on_slider = state_changed

    def _on_tint_entry(self, _event: tk.Event | None = None) -> None:
        """User pressed Enter (or left the field) — parse tint and refresh.

        Mirrors upstream ``actionPerformed(ActionEvent)``.
        """
        if self._syncing:
            return
        assert self._tint_var is not None
        assert self._slider is not None
        text = self._tint_var.get()
        try:
            self._tint_value = float(text)
        except ValueError:
            self._syncing = True
            try:
                self._tint_var.set(str(self._tint_value))
            finally:
                self._syncing = False
            return
        self._syncing = True
        try:
            self._slider.set(self.get_int_representation(self._tint_value))
        finally:
            self._syncing = False
        try:
            self.update_color_bar()
        except OSError as ex:
            self._tint_var.set(str(ex))

    # ---- color-bar helpers ------------------------------------------------

    def update_color_bar(self) -> None:
        """Recolor the color-bar canvas from the current tint value.

        Mirrors upstream ``CSSeparation.updateColorBar()`` (private). The
        underscore-prefixed alias is retained for callers that depended
        on the original name.
        """
        assert self._color_bar is not None
        rgb_values = self._separation.to_rgb([self._tint_value])
        # PDSeparation.to_rgb returns ``None`` when the alternate /
        # tint-transform is missing — upstream would NPE here; we
        # degrade to opaque black instead.
        color: tuple[float, float, float] = (
            (rgb_values[0], rgb_values[1], rgb_values[2])
            if rgb_values is not None
            else (0.0, 0.0, 0.0)
        )
        hex_color = self._renderer.to_hex(color)
        with contextlib.suppress(tk.TclError):
            self._color_bar.configure(background=hex_color)

    # Back-compat private alias.
    _update_color_bar = update_color_bar

    def set_color_bar_border(self, border: object | None = None) -> None:
        """Set a border around the colour bar.

        Mirrors upstream ``CSSeparation.setColorBarBorder()``. The
        upstream method takes no arguments and uses the darkest colour
        of the colorant as the border colour via a ``BevelBorder``.
        Tkinter has no direct ``BevelBorder`` analogue, so we use
        ``relief="sunken"`` with ``highlightbackground`` set to the
        darkest colour. The optional ``border`` argument is accepted for
        API-symmetry with potential overrides — when provided it is
        passed through to ``Canvas.configure(relief=border)``.
        """
        assert self._color_bar is not None
        rgb_values = self._separation.to_rgb([1.0])
        color: tuple[float, float, float] = (
            (rgb_values[0], rgb_values[1], rgb_values[2])
            if rgb_values is not None
            else (0.0, 0.0, 0.0)
        )
        darkest_hex = self._renderer.to_hex(color)
        relief = border if isinstance(border, str) else "sunken"
        # ``BevelBorder.LOWERED`` has no direct Tkinter equivalent;
        # ``relief="sunken"`` is the closest analogue. The darkest
        # color drives the border color via ``highlightbackground``.
        with contextlib.suppress(tk.TclError):
            self._color_bar.configure(
                relief=relief,
                highlightthickness=2,
                highlightbackground=darkest_hex,
            )

    # Back-compat private alias.
    _set_color_bar_border = set_color_bar_border

    # ---- value conversion helpers ----------------------------------------

    @staticmethod
    def get_float_representation(value: int) -> float:
        """Convert slider int (0..100) to tint float (0.0..1.0).

        Mirrors upstream ``CSSeparation.getFloatRepresentation(int)``.
        """
        return value / 100

    @staticmethod
    def get_int_representation(value: float) -> int:
        """Convert tint float (0.0..1.0) to slider int (0..100).

        Mirrors upstream ``CSSeparation.getIntRepresentation(float)``.
        Upstream uses Java's ``(int) (value*100)`` cast which truncates
        toward zero; we match that with Python's ``int()``.
        """
        return int(value * 100)

    # Back-compat private aliases.
    _get_float_representation = get_float_representation
    _get_int_representation = get_int_representation

    # ---- public surface ---------------------------------------------------

    def get_panel(self) -> ttk.Frame | None:
        """Return the main panel. Mirrors upstream ``CSSeparation.getPanel()``."""
        return self._panel

    @property
    def tint_value(self) -> float:
        """Current tint value as a float in ``[0, 1]``."""
        return self._tint_value
