"""Abstract base for native font directory finders.

Mirrors ``org.apache.fontbox.util.autodetect.FontDirFinder`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/util/autodetect/FontDirFinder.java``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class FontDirFinder(ABC):
    """Implementers return a list of directories to search for fonts."""

    @abstractmethod
    def find(self) -> list[Path]:
        """Return a list of native font directories."""


__all__ = ["FontDirFinder"]
