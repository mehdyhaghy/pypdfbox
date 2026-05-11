"""Locate font files on disk by walking native font directories.

Mirrors ``org.apache.fontbox.util.autodetect.FontFileFinder`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/util/autodetect/FontFileFinder.java``).

Library-first: we use :mod:`platform` to dispatch to the right finder and
:mod:`pathlib` to walk directories. ``fontTools`` provides richer font
metadata, but for *locating* font files the stdlib is sufficient.
"""

from __future__ import annotations

import logging
import platform
from pathlib import Path

from pypdfbox.fontbox.util.autodetect.font_dir_finder import FontDirFinder
from pypdfbox.fontbox.util.autodetect.mac_font_dir_finder import MacFontDirFinder
from pypdfbox.fontbox.util.autodetect.os400_font_dir_finder import OS400FontDirFinder
from pypdfbox.fontbox.util.autodetect.unix_font_dir_finder import UnixFontDirFinder
from pypdfbox.fontbox.util.autodetect.windows_font_dir_finder import WindowsFontDirFinder

_LOG = logging.getLogger(__name__)


class FontFileFinder:
    """Walk OS font directories and return font file URIs."""

    def __init__(self) -> None:
        self._font_dir_finder: FontDirFinder | None = None

    def determine_dir_finder(self) -> FontDirFinder:
        """Mirror of upstream's ``determineDirFinder``.

        Picks the platform-appropriate font directory finder.
        """
        os_name = platform.system()
        if os_name.startswith("Windows"):
            return WindowsFontDirFinder()
        if os_name == "Darwin" or os_name.startswith("Mac"):
            return MacFontDirFinder()
        if os_name.startswith("OS/400"):
            return OS400FontDirFinder()
        return UnixFontDirFinder()

    # Underscore-prefixed alias retained for in-module callers.
    _determine_dir_finder = determine_dir_finder

    def find(self, directory: str | None = None) -> list[str]:
        """Return font file URIs.

        With no argument, walks all detected native font directories.
        With a ``directory`` argument, walks just that directory.
        """
        results: list[str] = []
        if directory is None:
            if self._font_dir_finder is None:
                self._font_dir_finder = self._determine_dir_finder()
            for d in self._font_dir_finder.find():
                self._walk(d, results)
        else:
            d = Path(directory)
            if d.is_dir():
                self._walk(d, results)
        return results

    def walk(self, directory: Path, results: list[str]) -> None:
        """Mirror of upstream's ``walk``.

        Recurses into ``directory``, collecting any font file URIs.
        """
        if not directory.is_dir():
            return
        try:
            entries = list(directory.iterdir())
        except OSError as exc:
            _LOG.debug("Couldn't list %s: %s", directory, exc)
            return
        for entry in entries:
            if entry.is_dir():
                if entry.name.startswith("."):
                    _LOG.debug("skip hidden directory %s", entry)
                    continue
                self.walk(entry, results)
            else:
                _LOG.debug("checkFontfile check %s", entry)
                if self.check_fontfile(entry):
                    _LOG.debug("checkFontfile found %s", entry)
                    results.append(entry.absolute().as_uri())

    # Underscore-prefixed alias.
    _walk = walk

    @staticmethod
    def check_fontfile(file: Path) -> bool:
        """Mirror of upstream's ``checkFontfile``."""
        name = file.name.lower()
        return (
            name.endswith((".ttf", ".otf", ".pfb", ".ttc"))
            and not name.startswith("fonts.")
        )

    # Underscore-prefixed alias.
    _check_fontfile = check_fontfile


__all__ = ["FontFileFinder"]
