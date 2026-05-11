"""Unix/Linux font directory finder.

Mirrors ``org.apache.fontbox.util.autodetect.UnixFontDirFinder``.
"""

from __future__ import annotations

import os

from pypdfbox.fontbox.util.autodetect.native_font_dir_finder import NativeFontDirFinder


class UnixFontDirFinder(NativeFontDirFinder):
    def get_searchable_directories(self) -> list[str]:
        home = os.path.expanduser("~")
        return [
            f"{home}/.fonts",
            "/usr/local/fonts",
            "/usr/local/share/fonts",
            "/usr/share/fonts",
            "/usr/X11R6/lib/X11/fonts",
            "/usr/share/X11/fonts",
        ]


__all__ = ["UnixFontDirFinder"]
