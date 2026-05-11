"""macOS font directory finder.

Mirrors ``org.apache.fontbox.util.autodetect.MacFontDirFinder``.
"""

from __future__ import annotations

import os

from pypdfbox.fontbox.util.autodetect.native_font_dir_finder import NativeFontDirFinder


class MacFontDirFinder(NativeFontDirFinder):
    def get_searchable_directories(self) -> list[str]:
        home = os.path.expanduser("~")
        return [
            f"{home}/Library/Fonts/",
            "/Library/Fonts/",
            "/System/Library/Fonts/",
            "/Network/Library/Fonts/",
        ]


__all__ = ["MacFontDirFinder"]
