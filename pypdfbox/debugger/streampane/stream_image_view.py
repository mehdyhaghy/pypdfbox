"""Tkinter port of ``org.apache.pdfbox.debugger.streampane.StreamImageView``.

Renders a decoded image stream onto a scrollable Tk frame. The upstream
Swing class wraps a ``BufferedImage`` in a ``JLabel`` inside a
``JScrollPane``; here we use a ``tk.Canvas`` with a ``Scrollbar`` so the
image can be panned at native resolution. The viewer honours an optional
zoom + rotation pair — upstream wires these to global ``ZoomMenu`` /
``RotationMenu`` singletons; this port exposes them as plain
constructor kwargs (the menu wiring is the host frame's concern).
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk
from typing import Any

from pypdfbox.debugger.ui.image_util import ImageUtil


class StreamImageView(ttk.Frame):
    """Scrollable image viewer for decoded stream images."""

    DEFAULT_WIDTH: int = 300
    DEFAULT_HEIGHT: int = 400

    def __init__(
        self,
        master: tk.Misc | None,
        image: object,
        zoom_scale: float = 1.0,
        rotation_degrees: int = 0,
    ) -> None:
        """Build the view.

        :param master: parent Tkinter widget.
        :param image: a ``PIL.Image.Image`` to display.
        :param zoom_scale: multiplier applied to the image dimensions
            (upstream's ``ZoomMenu`` value, defaults to 1.0).
        :param rotation_degrees: clockwise rotation in degrees, one of
            ``0 / 90 / 180 / 270`` (upstream's ``RotationMenu`` value).
        """
        super().__init__(master)
        self._image = image
        self._zoom_scale = zoom_scale
        self._rotation_degrees = rotation_degrees
        self._photo: Any | None = None

        with contextlib.suppress(tk.TclError):
            self.configure(width=self.DEFAULT_WIDTH, height=self.DEFAULT_HEIGHT)

        canvas = tk.Canvas(self, background="white")
        h_scroll = ttk.Scrollbar(self, orient="horizontal", command=canvas.xview)
        v_scroll = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
        )

        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._canvas = canvas
        self._render()

    # ---- public accessors --------------------------------------------------

    def get_view(self) -> StreamImageView:
        """Return ``self`` — upstream returns the containing ``JComponent``."""
        return self

    def set_zoom(self, scale: float) -> None:
        """Re-render at a new zoom level (matches upstream menu hook)."""
        self._zoom_scale = scale
        self._render()

    def set_rotation(self, degrees: int) -> None:
        """Re-render at a new rotation (matches upstream menu hook)."""
        self._rotation_degrees = degrees
        self._render()

    @property
    def canvas(self) -> tk.Canvas:
        """The underlying ``tk.Canvas`` (exposed for tests)."""
        return self._canvas

    # ---- internals ---------------------------------------------------------

    def _render(self) -> None:
        try:
            from PIL import Image as _Image
            from PIL import ImageTk
        except ImportError:  # pragma: no cover — Pillow is a hard dep
            return

        # Apply rotation first, then zoom — matches upstream order
        # (``ImageUtil.getRotatedImage`` followed by ``getScaledInstance``).
        rotated = ImageUtil.get_rotated_image(self._image, self._rotation_degrees)
        if self._zoom_scale != 1.0:
            new_width = max(1, int(rotated.width * self._zoom_scale))
            new_height = max(1, int(rotated.height * self._zoom_scale))
            rendered = rotated.resize((new_width, new_height), _Image.LANCZOS)
        else:
            rendered = rotated

        # Build the PhotoImage and stash it on ``self`` so the GC does
        # not reclaim it after this method returns (Tk holds only a weak
        # reference inside the canvas).
        self._photo = ImageTk.PhotoImage(rendered)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.configure(scrollregion=(0, 0, rendered.width, rendered.height))
