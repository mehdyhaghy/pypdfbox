"""Base class for native font directory finders.

Mirrors ``org.apache.fontbox.util.autodetect.NativeFontDirFinder``.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path

from pypdfbox.fontbox.util.autodetect.font_dir_finder import FontDirFinder

_LOG = logging.getLogger(__name__)


class NativeFontDirFinder(FontDirFinder):
    """Generic body shared by Mac, Unix and OS/400 finders."""

    def find(self) -> list[Path]:
        result: list[Path] = []
        for raw in self.get_searchable_directories() or []:
            try:
                p = Path(raw).expanduser()
                if p.exists() and p.is_dir():
                    result.append(p)
            except OSError as exc:
                _LOG.debug("Couldn't probe %s: %s", raw, exc)
        return result

    @abstractmethod
    def get_searchable_directories(self) -> list[str]:
        """Return a list of candidate font directories."""


__all__ = ["NativeFontDirFinder"]
