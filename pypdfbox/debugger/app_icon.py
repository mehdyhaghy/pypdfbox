"""Window icon wiring for the Tkinter debugger.

Upstream PDFBox sets its Swing frame icon from
``org.apache.pdfbox.debugger/pdfbox.png``; this is the Tk equivalent. The
icon is cosmetic, so every failure path here is swallowed — a stripped-down
Tk build without PNG support, a missing resource in an unusual install
layout, or a window manager that ignores icons must never stop the debugger
from opening.
"""

import logging
import sys
import tkinter as tk
from importlib import resources
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)

# Tk holds only a weak reference to a PhotoImage. Without a module-level
# anchor the image is garbage collected as soon as this function returns and
# the icon silently blanks — the classic Tk footgun.
_ICON_REFS: list[tk.PhotoImage] = []

# Sizes handed to ``iconphoto``, LARGEST FIRST -- the order matters.
#
# Tk treats the *first* image as the primary one and lets the window manager
# pick among the rest. Passing these ascending made 16x16 the primary, so the
# macOS dock upscaled a 16px bitmap to dock size (up to 512px on a retina
# display) and the icon looked blurred. Largest-first gives the dock a
# 512px source to downscale from, which is what it wants; the small sizes
# are still offered for the title bar and task switcher, which downscale
# from the nearest match.
_PHOTO_SIZES = (512, 256, 128, 64, 48, 32, 16)


def icon_dir() -> Path:
    """Return the directory holding the packaged icon files.

    Mirrors :func:`pypdfbox.fontbox.liberation_loader`'s lookup so the path
    resolves identically for installed and editable installs.
    """
    return Path(str(resources.files("pypdfbox.resources.icon")))


def apply_window_icon(window: Any) -> bool:
    """Set ``window``'s icon to the pypdfbox mark.

    Returns ``True`` when an icon was applied, ``False`` when it could not be
    (never raises). ``window`` is a ``tk.Tk`` or ``tk.Toplevel``.
    """
    try:
        directory = icon_dir()
    except (ModuleNotFoundError, OSError) as ex:  # pragma: no cover - layout
        _LOG.debug("icon resources unavailable: %s", ex)
        return False

    applied = False

    # Windows: .ico gives a proper title-bar and taskbar icon, and
    # ``default=`` makes it apply to Toplevels opened later too. On other
    # platforms Tk expects an XBM here and raises, so this is Windows-only.
    if sys.platform == "win32":
        ico = directory / "pypdfbox.ico"
        if ico.is_file():
            try:
                window.iconbitmap(default=str(ico))
                applied = True
            except Exception as ex:  # pragma: no cover
                _LOG.debug("iconbitmap failed: %s", ex)

    images: list[tk.PhotoImage] = []
    for size in _PHOTO_SIZES:
        png = directory / f"pypdfbox-{size}.png"
        if not png.is_file():
            continue
        try:
            # Tk 8.6+ reads PNG natively; older builds raise TclError. A
            # non-Tk ``window`` fails with AttributeError/TypeError instead,
            # so catch broadly — this path is cosmetic and must never
            # propagate.
            images.append(tk.PhotoImage(master=window, file=str(png)))
        except Exception as ex:
            _LOG.debug("could not load %s: %s", png.name, ex)

    if images:
        try:
            window.iconphoto(True, *images)
            _ICON_REFS.extend(images)
            applied = True
        except Exception as ex:  # pragma: no cover
            _LOG.debug("iconphoto failed: %s", ex)

    return applied
