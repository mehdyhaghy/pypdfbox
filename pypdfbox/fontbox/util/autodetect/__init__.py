"""Font autodetection — locate native operating-system font files."""

from __future__ import annotations

from pypdfbox.fontbox.util.autodetect.font_dir_finder import FontDirFinder
from pypdfbox.fontbox.util.autodetect.font_file_finder import FontFileFinder
from pypdfbox.fontbox.util.autodetect.mac_font_dir_finder import MacFontDirFinder
from pypdfbox.fontbox.util.autodetect.native_font_dir_finder import NativeFontDirFinder
from pypdfbox.fontbox.util.autodetect.os400_font_dir_finder import OS400FontDirFinder
from pypdfbox.fontbox.util.autodetect.unix_font_dir_finder import UnixFontDirFinder
from pypdfbox.fontbox.util.autodetect.windows_font_dir_finder import WindowsFontDirFinder

__all__ = [
    "FontDirFinder",
    "FontFileFinder",
    "MacFontDirFinder",
    "NativeFontDirFinder",
    "OS400FontDirFinder",
    "UnixFontDirFinder",
    "WindowsFontDirFinder",
]
