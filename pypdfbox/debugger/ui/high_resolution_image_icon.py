"""High-DPI image icon wrapper for Tkinter.

Ported from ``org.apache.pdfbox.debugger.ui.HighResolutionImageIcon``.

Java's ``javax.swing.Icon`` draws into a host ``Graphics`` instance at a base
size while the underlying ``Image`` is a higher-resolution bitmap. Tkinter
has no equivalent abstraction: widgets simply consume ``PhotoImage``
instances. We therefore expose:

* the original ``PIL.Image`` (full resolution), and
* a :meth:`get_photo_image` accessor that lazily resizes to the declared
  base size and returns a ``ImageTk.PhotoImage`` suitable for Tk widgets.
"""

from __future__ import annotations

from typing import Any


class HighResolutionImageIcon:
    """Tkinter-flavoured analogue of Swing's ``HighResolutionImageIcon``."""

    def __init__(self, image: Any, base_width: int, base_height: int) -> None:
        self._image = image
        self._base_width = base_width
        self._base_height = base_height
        self._photo: Any | None = None

    # --- accessors --------------------------------------------------------

    def get_icon_width(self) -> int:
        """Return the declared base width in pixels."""
        return self._base_width

    def get_icon_height(self) -> int:
        """Return the declared base height in pixels."""
        return self._base_height

    def get_image(self) -> Any:
        """Return the underlying high-resolution PIL image."""
        return self._image

    def get_photo_image(self) -> Any:
        """Return (and cache) a ``PhotoImage`` resized to the base dimensions."""
        if self._photo is None:
            self._photo = _build_photo_image(
                self._image, self._base_width, self._base_height
            )
        return self._photo

    # --- Swing-parity paint hook -----------------------------------------

    def paint_icon(self, canvas: Any, x: int, y: int) -> Any:
        """Draw the icon onto a Tk canvas at ``(x, y)``.

        Mirrors Swing's ``paintIcon(Component, Graphics, x, y)``.

        :returns: the canvas item id, matching the upstream ``Graphics.drawImage``
            return-via-callback contract well enough for tests to assert.
        """
        photo = self.get_photo_image()
        return canvas.create_image(x, y, anchor="nw", image=photo)


def _build_photo_image(image: Any, width: int, height: int) -> Any:
    """Resize ``image`` to ``(width, height)`` and wrap it as a ``PhotoImage``.

    Imported lazily so unit tests that only exercise the headless accessors
    don't pull Tk/PIL into the module-load path.
    """
    try:
        from PIL import Image, ImageTk
    except ImportError as exc:  # pragma: no cover - dependency declared in pyproject
        raise RuntimeError(
            "Pillow (PIL) is required for HighResolutionImageIcon.get_photo_image()"
        ) from exc

    resized = image.resize((width, height), Image.LANCZOS)
    return ImageTk.PhotoImage(resized)
