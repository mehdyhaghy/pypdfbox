"""Logger that forwards to the debugger's ``LogDialog``.

Ported from ``org.apache.pdfbox.debugger.ui.DebugLog``. The Java original
implements ``org.apache.commons.logging.Log``; we forward to Python's stdlib
``logging`` module instead, while also exposing the API surface (``debug``,
``info``, ``warn``, ``error``, ``fatal``, ``trace``, and their ``is_*_enabled``
companions) that callers expect.

A pluggable "dialog" hook (``set_dialog_sink``) lets the Tkinter
``LogDialog`` register itself once it is built; until then, messages are
forwarded only to ``logging``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

# Mirrors the upstream constants. They are module-level so test code can flip
# them without monkey-patching every instance.
_INFO = True
_TRACE = False
_DEBUG = False

# A sink function with signature ``(name, level, msg, exc) -> None``.
# Set by the Tkinter ``LogDialog`` once it is constructed; until then we only
# forward to ``logging``.
_dialog_sink: Callable[[str, str, Any, BaseException | None], None] | None = None


def set_dialog_sink(
    sink: Callable[[str, str, Any, BaseException | None], None] | None,
) -> None:
    """Install (or clear) the dialog-side log sink."""
    global _dialog_sink
    _dialog_sink = sink


class DebugLog:
    """Forward log calls to ``logging`` and (optionally) the debugger UI."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._logger = logging.getLogger(name)

    # --- forwarding --------------------------------------------------------

    def _emit(
        self,
        level: str,
        py_level: int,
        message: Any,
        throwable: BaseException | None,
    ) -> None:
        self._logger.log(py_level, "%s", message, exc_info=throwable)
        if _dialog_sink is not None:
            _dialog_sink(self.name, level, message, throwable)

    # --- debug -------------------------------------------------------------

    def debug(self, message: Any, throwable: BaseException | None = None) -> None:
        if _DEBUG:
            self._emit("debug", logging.DEBUG, message, throwable)

    # --- error -------------------------------------------------------------

    def error(self, message: Any, throwable: BaseException | None = None) -> None:
        self._emit("error", logging.ERROR, message, throwable)

    # --- fatal -------------------------------------------------------------

    def fatal(self, message: Any, throwable: BaseException | None = None) -> None:
        # ``CRITICAL`` is Python's nearest equivalent to ``FATAL``.
        self._emit("fatal", logging.CRITICAL, message, throwable)

    # --- info --------------------------------------------------------------

    def info(self, message: Any, throwable: BaseException | None = None) -> None:
        if _INFO:
            self._emit("info", logging.INFO, message, throwable)

    # --- trace -------------------------------------------------------------

    def trace(self, message: Any, throwable: BaseException | None = None) -> None:
        if _TRACE:
            # ``logging`` has no TRACE level; map to DEBUG with a marker name.
            self._emit("trace", logging.DEBUG, message, throwable)

    # --- warn --------------------------------------------------------------

    def warn(self, message: Any, throwable: BaseException | None = None) -> None:
        self._emit("warn", logging.WARNING, message, throwable)

    # --- enablement flags --------------------------------------------------

    def is_debug_enabled(self) -> bool:
        return _DEBUG

    def is_error_enabled(self) -> bool:
        return True

    def is_fatal_enabled(self) -> bool:
        return True

    def is_info_enabled(self) -> bool:
        return _INFO

    def is_trace_enabled(self) -> bool:
        return _TRACE

    def is_warn_enabled(self) -> bool:
        return True
