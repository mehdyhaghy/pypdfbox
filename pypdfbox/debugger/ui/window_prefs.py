"""Persistent window geometry preferences for the debugger.

Ported from ``org.apache.pdfbox.debugger.ui.WindowPrefs``.

Java upstream uses ``java.util.prefs.Preferences``; we use a small JSON file
stored under the platform's per-user config directory. The path resolution
deliberately uses only the standard library to avoid pulling in
``platformdirs`` as a runtime dependency.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_KEY = "window_prefs_"
# Defaults match the upstream behaviour, which used the screen size to seed
# the initial bounds. We do not query a Tk root here -- the Tkinter front-end
# can pass real screen sizes via ``get_bounds(screen_width=..., screen_height=..)``.
_DEFAULT_SCREEN_W = 1280
_DEFAULT_SCREEN_H = 800
_FRAME_NORMAL = 0  # Mirrors ``java.awt.Frame.NORMAL``.


class WindowPrefs:
    """Saves window position and size in a JSON-backed preference file."""

    def __init__(
        self,
        class_name: str | type,
        *,
        path: Path | None = None,
    ) -> None:
        # Java's ``Preferences.userNodeForPackage(class)`` namespaces by the
        # *package* of the supplied class. We mirror that by deriving a slug
        # from the qualified class name.
        if isinstance(class_name, type):
            slug = f"{class_name.__module__}.{class_name.__qualname__}"
        else:
            slug = str(class_name)
        self._slug = slug
        self._path = path if path is not None else _default_prefs_path()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    # --- I/O --------------------------------------------------------------

    def _load(self) -> None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._data = {}
            return
        except OSError:
            self._data = {}
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._data = {}
            return
        if not isinstance(payload, dict):
            self._data = {}
            return
        node = payload.get(self._slug)
        if isinstance(node, dict):
            self._data = {k: v for k, v in node.items() if isinstance(v, dict)}
        else:
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        # Preserve other slugs already on disk.
        payload: dict[str, Any] = {}
        if self._path.exists():
            try:
                existing = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload = existing
            except (OSError, json.JSONDecodeError):
                payload = {}
        payload[self._slug] = self._data
        try:
            self._path.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            return

    # --- helpers ----------------------------------------------------------

    def _node(self) -> dict[str, Any]:
        node = self._data.get(_KEY)
        if not isinstance(node, dict):
            node = {}
            self._data[_KEY] = node
        return node

    def _node_get_int(self, key: str, default: int) -> int:
        value = self._node().get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _node_put_int(self, key: str, value: int) -> None:
        self._node()[key] = int(value)
        self._save()

    # --- public API -------------------------------------------------------

    def set_bounds(self, rect: tuple[int, int, int, int]) -> None:
        """Persist the (x, y, w, h) window rectangle."""
        x, y, w, h = rect
        node = self._node()
        node["X"] = int(x)
        node["Y"] = int(y)
        node["W"] = int(w)
        node["H"] = int(h)
        self._save()

    def get_bounds(
        self,
        *,
        screen_width: int = _DEFAULT_SCREEN_W,
        screen_height: int = _DEFAULT_SCREEN_H,
    ) -> tuple[int, int, int, int]:
        """Read the persisted (x, y, w, h) rectangle, falling back to a sane default."""
        node = self._node()
        x = self._coerce_int(node.get("X"), screen_width // 4)
        y = self._coerce_int(node.get("Y"), screen_height // 4)
        w = self._coerce_int(node.get("W"), screen_width // 2)
        h = self._coerce_int(node.get("H"), screen_height // 2)
        return x, y, w, h

    def set_divider_location(self, divider: int) -> None:
        """Persist the split-pane divider location."""
        self._node_put_int("DIV", divider)

    def get_divider_location(
        self,
        *,
        screen_width: int = _DEFAULT_SCREEN_W,
    ) -> int:
        """Return the persisted divider location, defaulting to ``screen_width // 8``."""
        return self._node_get_int("DIV", screen_width // 8)

    def set_extended_state(self, extended_state: int) -> None:
        """Persist the window's extended-state flag (maximized/iconified bitmask)."""
        self._node_put_int("EXTSTATE", extended_state)

    def get_extended_state(self) -> int:
        """Return the persisted extended-state flag (defaults to ``NORMAL``)."""
        return self._node_get_int("EXTSTATE", _FRAME_NORMAL)

    # --- internal --------------------------------------------------------

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def _default_prefs_path() -> Path:
    """Return the platform-specific default prefs file location."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "pypdfbox" / "debugger.json"
    # macOS + Linux both honour XDG_CONFIG_HOME, falling back to ``~/.config``.
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "pypdfbox" / "debugger.json"
