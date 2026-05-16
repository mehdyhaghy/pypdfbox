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
        self._current_image: Any | None = None

        self.init_ui()

    # ---- public API --------------------------------------------------------

    def init_ui(self) -> None:
        """Build the scrollable canvas widget tree.

        Mirrors upstream ``initUI()`` which assembles a ``JPanel`` +
        ``JLabel`` inside a ``JScrollPane``; here a ``tk.Canvas`` with
        horizontal + vertical ``ttk.Scrollbar`` widgets fills the same
        role. Safe to invoke more than once — subsequent calls rebuild
        the canvas in place.
        """

        with contextlib.suppress(tk.TclError):
            self.configure(width=self.DEFAULT_WIDTH, height=self.DEFAULT_HEIGHT)

        # If a previous canvas exists, drop it so we don't stack widgets
        # on repeated init_ui() calls.
        existing = getattr(self, "_canvas", None)
        if existing is not None:
            with contextlib.suppress(tk.TclError):
                for child in list(self.winfo_children()):
                    child.destroy()

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

    def add_image(self, image: object) -> None:
        """Replace the displayed image with *image* and re-render.

        Mirrors upstream ``addImage(Image)`` — assigns the supplied
        ``PIL.Image.Image`` as the currently shown bitmap, then refreshes
        the canvas at the current zoom and rotation.
        """

        self._image = image
        self._render()

    def zoom_image(
        self,
        scale: float | None = None,
        rotation: int | None = None,
    ) -> Any:
        """Return the source image resampled at *scale* and *rotation*.

        Mirrors upstream ``zoomImage(BufferedImage origin, float scale,
        int rotation)`` which rotates first, then scales. When *scale*
        or *rotation* is ``None`` the corresponding stored value (set
        via the constructor / ``set_zoom`` / ``set_rotation``) is used.

        Side effect: updates the displayed canvas so the rendered image
        matches the returned ``PIL.Image.Image``. Returns the rendered
        image so callers can inspect dimensions (parity with upstream's
        return of ``java.awt.Image``).
        """

        if scale is not None:
            self._zoom_scale = scale
        if rotation is not None:
            self._rotation_degrees = rotation
        self._render()
        return self._current_image

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

    @property
    def current_image(self) -> Any | None:
        """The most recently rendered ``PIL.Image.Image`` (or ``None``)."""
        return self._current_image

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

        self._current_image = rendered

        # Build the PhotoImage and stash it on ``self`` so the GC does
        # not reclaim it after this method returns (Tk holds only a weak
        # reference inside the canvas).
        self._photo = ImageTk.PhotoImage(rendered)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.configure(scrollregion=(0, 0, rendered.width, rendered.height))
