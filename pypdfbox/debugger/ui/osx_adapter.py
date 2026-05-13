"""macOS-specific Tk integration glue.

Ported (in intent) from ``org.apache.pdfbox.debugger.ui.OSXAdapter``.

The Java original used reflection against ``com.apple.eawt.Application`` /
``java.awt.Desktop`` to hook the "Quit", "About", and "Preferences" entries
of the macOS application menu. Tk on macOS exposes equivalent hooks via
``root.createcommand("::tk::mac::Quit", ...)`` and friends. We translate the
upstream API directly:

* :meth:`OSXAdapter.set_quit_handler(callback)`
* :meth:`OSXAdapter.set_about_handler(callback)`
* :meth:`OSXAdapter.set_preferences_handler(callback)`
* :meth:`OSXAdapter.set_file_handler(callback)`
* :meth:`OSXAdapter.register(root, callbacks)` -- bulk registration

On non-macOS platforms (``sys.platform != "darwin"``) the methods are
deliberate no-ops, matching the upstream behaviour of skipping registration
when the Apple EAWT classes are absent.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from typing import Any

#: Type alias for a no-arg user callback.
Handler = Callable[[], Any]
#: Type alias for the open-file callback (receives one path string).
FileHandler = Callable[[str], Any]


def _is_macos() -> bool:
    """Return ``True`` iff we're running on macOS."""
    return sys.platform == "darwin"


class OSXAdapter:
    """Routes macOS application-menu actions to user callbacks.

    Instances are kept per Tk root so that re-registering on the same root
    replaces the previous handlers (matching the upstream singleton-like
    behaviour of ``com.apple.eawt.Application``).
    """

    def __init__(self, root: tk.Misc) -> None:
        self._root = root

    # --- registration helpers ---------------------------------------------

    def set_quit_handler(self, handler: Handler | None) -> bool:
        """Register a Quit-menu handler. Returns ``True`` iff installed."""
        return self._create_command("::tk::mac::Quit", handler)

    def set_about_handler(self, handler: Handler | None) -> bool:
        """Register an About-menu handler. Returns ``True`` iff installed."""
        return self._create_command("tk::mac::standardAboutPanel", handler)

    def set_preferences_handler(self, handler: Handler | None) -> bool:
        """Register a Preferences-menu handler. Returns ``True`` iff installed."""
        return self._create_command("::tk::mac::ShowPreferences", handler)

    def set_file_handler(self, handler: FileHandler | None) -> bool:
        """Register an open-file handler. Returns ``True`` iff installed."""
        if not _is_macos():
            return False
        if handler is None:
            return False

        def _wrapper(*paths: str) -> None:
            # Tk's OpenDocument command receives each path as a separate arg.
            if not paths:
                return
            handler(paths[0])

        return self._create_command("::tk::mac::OpenDocument", _wrapper)

    # --- composite registration -------------------------------------------

    @classmethod
    def register(
        cls,
        root: tk.Misc,
        callbacks: dict[str, Handler | FileHandler] | None,
    ) -> OSXAdapter | None:
        """Register a bundle of handlers in one call.

        ``callbacks`` keys: ``"quit"``, ``"about"``, ``"preferences"``,
        ``"file"``. Unknown keys are ignored. Returns the adapter on macOS,
        or ``None`` on other platforms.
        """
        if not _is_macos():
            return None
        adapter = cls(root)
        if not callbacks:
            return adapter
        quit_cb = callbacks.get("quit")
        about_cb = callbacks.get("about")
        prefs_cb = callbacks.get("preferences")
        file_cb = callbacks.get("file")
        if quit_cb is not None:
            adapter.set_quit_handler(quit_cb)  # type: ignore[arg-type]
        if about_cb is not None:
            adapter.set_about_handler(about_cb)  # type: ignore[arg-type]
        if prefs_cb is not None:
            adapter.set_preferences_handler(prefs_cb)  # type: ignore[arg-type]
        if file_cb is not None:
            adapter.set_file_handler(file_cb)  # type: ignore[arg-type]
        return adapter

    # --- internals --------------------------------------------------------

    def _create_command(
        self,
        name: str,
        handler: Handler | Callable[..., Any] | None,
    ) -> bool:
        if not _is_macos():
            return False
        if handler is None:
            return False
        try:
            self._root.createcommand(name, handler)
        except (tk.TclError, AttributeError):  # pragma: no cover - depends on platform
            return False
        return True
