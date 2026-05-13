"""Persistent recent-files history for the debugger.

Ported from ``org.apache.pdfbox.debugger.ui.RecentFiles``. Upstream uses
``java.util.prefs.Preferences`` (which on Linux ends up under
``~/.java/.userPrefs/``). Python has no direct equivalent in the standard
library, so we store the history in a small JSON file alongside the
window-prefs JSON used by :mod:`pypdfbox.debugger.ui.window_prefs`.

Default location:

* POSIX: ``$XDG_CONFIG_HOME/pypdfbox/recent-files.json`` (falls back to
  ``~/.config/pypdfbox/recent-files.json``).
* Windows: ``%APPDATA%/pypdfbox/recent-files.json`` (falls back to
  ``~/AppData/Roaming/pypdfbox/recent-files.json``).

Callers that want isolation (tests, embedded usage) can pass an explicit
``path=...`` keyword. The history is keyed by a slug derived from the
``className`` argument so multiple consumers can share one file without
clobbering each other.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections import deque
from collections.abc import Iterable
from pathlib import Path


def _default_recent_files_path() -> Path:
    """Return the platform-specific default recent-files JSON path."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "pypdfbox" / "recent-files.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "pypdfbox" / "recent-files.json"


class RecentFiles:
    """Maintains an LRU-style history of recently-opened file paths."""

    def __init__(
        self,
        class_name: str | type,
        maximum_file: int,
        *,
        path: Path | None = None,
    ) -> None:
        if isinstance(class_name, type):
            slug = f"{class_name.__module__}.{class_name.__qualname__}"
        else:
            slug = str(class_name)
        self._slug = slug
        self._maximum = int(maximum_file)
        self._path = path if path is not None else _default_recent_files_path()
        self._file_paths: deque[str] = deque(self._read_history_from_pref())

    # --- I/O --------------------------------------------------------------

    def _load_payload(self) -> dict[str, object]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return payload

    def _read_history_from_pref(self) -> list[str]:
        payload = self._load_payload()
        node = payload.get(self._slug)
        if not isinstance(node, list):
            return []
        # Filter out any non-string detritus to be safe.
        return [item for item in node if isinstance(item, str)]

    def _write_history_to_pref(self, file_paths: Iterable[str]) -> None:
        entries = list(file_paths)
        if not entries:
            # Upstream returns early on an empty queue; mirror that behavior so
            # close() on a never-populated history doesn't blow away other
            # slugs already stored in the same JSON file.
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        payload = self._load_payload()
        payload[self._slug] = entries
        try:
            self._path.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            return

    # --- public API -------------------------------------------------------

    def remove_all(self) -> None:
        """Clear the in-memory history. Disk state is unaffected until ``close()``."""
        self._file_paths.clear()

    def is_empty(self) -> bool:
        """Return ``True`` iff the in-memory history is empty."""
        return not self._file_paths

    def add_file(self, path: str | None) -> None:
        """Append ``path`` to the history, evicting the oldest if at capacity."""
        if path is None:
            return
        # Upstream's threshold is ``maximum + 1``; mirror that exactly.
        if len(self._file_paths) >= self._maximum + 1:
            self._file_paths.popleft()
        self._file_paths.append(path)

    def remove_file(self, path: str) -> None:
        """Remove the first occurrence of ``path`` from the history, if present."""
        with contextlib.suppress(ValueError):
            self._file_paths.remove(path)

    def get_files(self) -> list[str]:
        """Return existing-on-disk file paths in insertion order.

        Mirrors upstream's ``getFiles()``: drops paths that no longer exist
        and caps the returned list at ``maximum`` by discarding the oldest
        survivor when the surviving count exceeds the cap.
        """
        files = [path for path in self._file_paths if Path(path).exists()]
        if len(files) > self._maximum:
            files.pop(0)
        return files

    def close(self) -> None:
        """Persist the in-memory history to the JSON file."""
        self._write_history_to_pref(self._file_paths)


__all__ = ["RecentFiles"]
