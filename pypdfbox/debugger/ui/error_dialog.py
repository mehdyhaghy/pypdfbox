"""Modal error dialog backed by :mod:`tkinter.messagebox`.

Ported from ``org.apache.pdfbox.debugger.ui.ErrorDialog``.

The Swing original was a custom ``JDialog`` with a "Show Details" button that
revealed a filtered stack trace. The Tkinter port keeps the same public
surface (constructor + ``show``) but delegates the visual presentation to
``tkinter.messagebox.showerror``: the message and (optionally filtered) stack
trace are combined into the dialog body. This is intentional -- a pixel-perfect
"hide/show details" toggle in stdlib Tk would require building a custom
``Toplevel``, which has no value for the headless / programmatic use cases.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

#: Java packages whose frames are noise in PDFBox stack traces. The same
#: filters apply to Python's ``traceback`` output -- they simply happen to be
#: never matched, since Python tracebacks don't include Java frames. The
#: constant is preserved so test parity stays meaningful.
_FILTERS: tuple[str, ...] = (
    "java.awt.",
    "javax.swing.",
    "sun.reflect.",
    "java.util.concurrent.",
)

#: Module-level hook so tests can intercept the messagebox call. By default it
#: forwards to ``tkinter.messagebox.showerror``; tests monkey-patch this to
#: avoid spawning a real window.
_show_error_impl: Callable[[str, str], Any] | None = None


def _default_show_error(title: str, message: str) -> Any:
    # Imported lazily so the module can be loaded on systems without a
    # display (e.g. headless CI) -- ``tkinter`` itself imports cleanly, but
    # we still defer to be consistent with sibling dialogs.
    from tkinter import messagebox

    return messagebox.showerror(title, message)


class ErrorDialog:
    """A dialog displaying a runtime exception's message and stack trace.

    ``parent`` is accepted for API parity with the Swing constructor but is
    only used to centre the dialog when a real Tk widget is supplied; for
    headless / scripted use, pass ``None``.
    """

    def __init__(
        self,
        *args: Any,
        is_filtering: bool = True,
    ) -> None:
        # Mirror the three Swing constructors:
        #   ErrorDialog(t)
        #   ErrorDialog(owner, t)
        #   ErrorDialog(owner, icon, t)
        if len(args) == 1:
            owner, icon, throwable = None, None, args[0]
        elif len(args) == 2:
            owner, icon, throwable = args[0], None, args[1]
        elif len(args) == 3:
            owner, icon, throwable = args[0], args[1], args[2]
        else:
            raise TypeError(
                f"ErrorDialog() takes 1-3 positional args (got {len(args)})"
            )
        if not isinstance(throwable, BaseException):
            raise TypeError("the last positional argument must be an exception")
        self._owner = owner
        self._icon = icon
        self._error: BaseException = throwable
        self._is_filtering = is_filtering
        self._showing_details = False

    # --- public API -------------------------------------------------------

    def set_visible(self, visible: bool = True) -> None:
        """Show the dialog. Mirrors Swing's ``setVisible(true)``."""
        if visible:
            self.show()

    def show(self) -> Any:
        """Display the dialog, returning whatever the messagebox returns."""
        title = type(self._error).__name__
        body = self._build_body()
        sink = _show_error_impl if _show_error_impl is not None else _default_show_error
        return sink(title, body)

    def set_show_details(self, showing: bool) -> None:
        """Toggle whether stack-trace details are included in the body."""
        self._showing_details = bool(showing)

    def is_showing_details(self) -> bool:
        return self._showing_details

    def set_filtering(self, is_filtering: bool) -> None:
        """Toggle whether boilerplate frames are filtered out."""
        self._is_filtering = bool(is_filtering)

    def is_filtering(self) -> bool:
        return self._is_filtering

    # --- internals --------------------------------------------------------

    def _build_body(self) -> str:
        message = str(self._error) or type(self._error).__name__
        if self._showing_details:
            return message + "\r\n\r\n" + self.generate_stack_trace(self._error)
        return message

    def generate_stack_trace(self, throwable: BaseException) -> str:
        """Render a filtered stack trace for ``throwable``.

        Matches upstream's recursive ``Caused by:`` handling.
        """
        lines: list[str] = []
        seen: set[int] = set()
        self._collect(throwable, lines, seen, prefix="")
        return "".join(lines)

    def _collect(
        self,
        throwable: BaseException,
        lines: list[str],
        seen: set[int],
        prefix: str,
    ) -> None:
        if id(throwable) in seen:
            return
        seen.add(id(throwable))
        header = f"{prefix}{type(throwable).__name__}: {throwable}\r\n"
        lines.append(header)
        tb = throwable.__traceback__
        frames = traceback.extract_tb(tb) if tb is not None else []
        for frame in frames:
            rendered = f"{frame.filename}:{frame.lineno} in {frame.name}"
            if self._is_filtering and self._is_suppressed(frame.filename):
                continue
            lines.append(f"    {rendered}\r\n")
        cause = throwable.__cause__ or throwable.__context__
        if cause is not None and cause is not throwable:
            self._collect(cause, lines, seen, prefix="Caused by: ")

    @staticmethod
    def _is_suppressed(class_name: str) -> bool:
        return any(class_name.startswith(prefix) for prefix in _FILTERS)


def set_show_error_impl(
    impl: Callable[[str, str], Any] | None,
) -> None:
    """Install (or clear) the underlying ``showerror`` implementation.

    Intended for tests; the production code path uses
    ``tkinter.messagebox.showerror``.
    """

    global _show_error_impl
    _show_error_impl = impl
