"""OS/400 font directory finder.

Mirrors ``org.apache.fontbox.util.autodetect.OS400FontDirFinder``.
"""

from __future__ import annotations

import os

from pypdfbox.fontbox.util.autodetect.native_font_dir_finder import NativeFontDirFinder


class OS400FontDirFinder(NativeFontDirFinder):
    def get_searchable_directories(self) -> list[str]:
        home = os.path.expanduser("~")
        return [f"{home}/.fonts", "/QIBM/ProdData/OS400/Fonts"]


__all__ = ["OS400FontDirFinder"]
