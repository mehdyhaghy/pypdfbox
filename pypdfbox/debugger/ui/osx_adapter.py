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

import inspect
import logging
import sys
import tkinter as tk
from collections.abc import Callable, Sequence
from typing import Any

_LOG = logging.getLogger(__name__)

#: Type alias for a no-arg user callback.
Handler = Callable[[], Any]
#: Type alias for the open-file callback (receives one path string).
FileHandler = Callable[[str], Any]


def _is_macos() -> bool:
    """Return ``True`` iff we're running on macOS."""
    return sys.platform == "darwin"


def is_min_jdk9() -> bool:
    """Python-platform analogue of upstream ``isMinJdk9()``.

    Upstream parsed ``System.getProperty("java.specification.version")`` to
    decide whether to use the modern ``java.awt.Desktop`` API or fall back to
    the legacy ``com.apple.eawt.Application`` route. The Python port talks to
    Tk on macOS instead, so the equivalent gate is "are we on macOS with a
    modern-enough Python interpreter for ``inspect.signature`` etc.?".
    """
    return sys.platform == "darwin" and sys.version_info >= (3, 8)


def is_correct_method(
    method: Any,
    name: str,
    types: Sequence[type] | None = None,
) -> bool:
    """Return ``True`` iff ``method`` matches ``name`` + parameter ``types``.

    Upstream used ``java.lang.reflect.Method.getName()`` plus an args-array
    length check. The Python equivalent uses :func:`inspect.signature` to
    compare the declared parameter count (and, when annotations are present,
    the annotation types).

    Parameters
    ----------
    method:
        Callable to inspect, or a ``(target, name)`` pair where the name is
        used to look up the bound method on the target.
    name:
        Expected callable name (matched against ``method.__name__``).
    types:
        Expected parameter type sequence; if ``None``, only the name is
        checked. If parameter annotations are missing on ``method``, only the
        parameter *count* is enforced.
    """
    if method is None or not callable(method):
        return False
    declared = getattr(method, "__name__", None)
    if declared != name:
        return False
    if types is None:
        return True
    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        return False
    params = [
        p
        for p in sig.parameters.values()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if len(params) != len(types):
        return False
    for param, expected in zip(params, types, strict=False):
        annot = param.annotation
        if annot is inspect.Parameter.empty:
            # No annotation declared -- count match already accepted above.
            continue
        # ``from __future__ import annotations`` stores annotations as
        # strings; accept a name match in that case.
        expected_name = getattr(expected, "__name__", str(expected))
        if isinstance(annot, str):
            if annot != expected_name:
                return False
            continue
        if annot is not expected:
            return False
    return True


def invoke(target: Any, method_name: str, *args: Any) -> Any:
    """Safe-dispatch wrapper around ``target.method_name(*args)``.

    Upstream relied on ``Method.invoke`` + ``InvocationTargetException``
    unwrapping. The Python equivalent is ``getattr`` + a plain call, with
    ``AttributeError`` / ``TypeError`` swallowed and logged so a stray
    Apple-event callback never tears down the Tk loop.

    Returns the called method's return value, or ``None`` if ``target`` has no
    such attribute / the call signature does not match.
    """
    handler = getattr(target, method_name, None)
    if handler is None or not callable(handler):
        _LOG.debug("OSXAdapter.invoke: %r has no callable %r", target, method_name)
        return None
    try:
        return handler(*args)
    except TypeError as exc:
        _LOG.warning(
            "OSXAdapter.invoke: signature mismatch calling %r.%s%r: %s",
            target,
            method_name,
            args,
            exc,
        )
        return None


def call_target(target: Any, method_name: str, event: Any = None) -> Any:
    """Dispatch a macOS event to ``target.method_name(event)``.

    Mirrors upstream ``callTarget(Object appleEvent)``: forwards the event to
    the user method via :func:`invoke`. When ``event`` is ``None`` the call is
    made with no arguments (matches upstream's no-arg fast path for handlers
    like ``handleAbout`` / ``handleQuit``).
    """
    if event is None:
        return invoke(target, method_name)
    return invoke(target, method_name, event)


def set_application_event_handled(event: Any, handled: bool) -> None:
    """No-op on Tk -- preserved for upstream interface parity.

    Upstream Java set the ``ApplicationEvent.setHandled`` flag so the legacy
    EAWT framework would suppress its default behaviour. Tk's
    ``createcommand`` dispatch has no such flag: registering a callback fully
    overrides the default menu action, so there is nothing to mark "handled".
    Kept as a documented no-op so callers writing port-shaped code can invoke
    it without conditional branches.
    """
    # Intentionally empty. ``event`` and ``handled`` accepted for interface
    # parity; Tk dispatch already consumes the event when our callback runs.
    del event, handled


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

    # --- upstream-shape static helpers ------------------------------------
    #
    # Upstream Java exposes these as ``public static`` members of
    # ``OSXAdapter``. The Python port keeps the implementations as
    # module-level functions (so callers can use them without importing the
    # class), but also re-exposes them as ``@staticmethod``s on the class
    # for parity-tool detection and for callers that prefer the
    # ``OSXAdapter.<name>`` spelling. These are thin delegations — the
    # logic lives in the module-level functions above.

    @staticmethod
    def is_min_jdk9() -> bool:
        """Class-surface alias for :func:`is_min_jdk9` (upstream-shape)."""
        return is_min_jdk9()

    @staticmethod
    def is_correct_method(
        method: Any,
        name: str,
        types: Sequence[type] | None = None,
    ) -> bool:
        """Class-surface alias for :func:`is_correct_method` (upstream-shape)."""
        return is_correct_method(method, name, types)

    @staticmethod
    def invoke(target: Any, method_name: str, *args: Any) -> Any:
        """Class-surface alias for :func:`invoke` (upstream-shape)."""
        return invoke(target, method_name, *args)

    @staticmethod
    def call_target(target: Any, method_name: str, event: Any = None) -> Any:
        """Class-surface alias for :func:`call_target` (upstream-shape)."""
        return call_target(target, method_name, event)

    @staticmethod
    def set_application_event_handled(event: Any, handled: bool) -> None:
        """Class-surface alias for :func:`set_application_event_handled`."""
        return set_application_event_handled(event, handled)

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
