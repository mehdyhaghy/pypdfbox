"""Windows font directory finder.

Mirrors ``org.apache.fontbox.util.autodetect.WindowsFontDirFinder``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pypdfbox.fontbox.util.autodetect.font_dir_finder import FontDirFinder

_LOG = logging.getLogger(__name__)


class WindowsFontDirFinder(FontDirFinder):
    """Locate font directories on Windows hosts."""

    def find(self) -> list[Path]:
        result: list[Path] = []
        windir = os.environ.get("windir")  # noqa: SIM112 — case-sensitive on POSIX
        if windir and len(windir) > 2:
            if windir.endswith("/") or windir.endswith("\\"):
                windir = windir[:-1]
            os_fonts = Path(f"{windir}{os.sep}FONTS")
            if os_fonts.exists() and os_fonts.is_dir():
                result.append(os_fonts)
            ps_fonts = Path(f"{windir[:2]}{os.sep}PSFONTS")
            if ps_fonts.exists() and ps_fonts.is_dir():
                result.append(ps_fonts)
        else:
            # Heuristic fallback across drive letters C..E.
            for drive in ("C", "D", "E"):
                fonts_dir = Path(f"{drive}:{os.sep}WINDOWS{os.sep}FONTS")
                try:
                    if fonts_dir.exists() and fonts_dir.is_dir():
                        result.append(fonts_dir)
                        break
                except OSError as exc:
                    _LOG.debug("probe %s failed: %s", fonts_dir, exc)
            for drive in ("C", "D", "E"):
                ps_dir = Path(f"{drive}:{os.sep}PSFONTS")
                try:
                    if ps_dir.exists() and ps_dir.is_dir():
                        result.append(ps_dir)
                        break
                except OSError as exc:
                    _LOG.debug("probe %s failed: %s", ps_dir, exc)
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            local_font_dir = (
                Path(local_app_data) / "Microsoft" / "Windows" / "Fonts"
            )
            if local_font_dir.exists() and local_font_dir.is_dir():
                result.append(local_font_dir)
        return result


__all__ = ["WindowsFontDirFinder"]
