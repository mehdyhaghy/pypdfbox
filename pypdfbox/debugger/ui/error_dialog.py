"""Modal error dialog backed by :mod:`tkinter.messagebox`.

Ported from ``org.apache.pdfbox.debugger.ui.ErrorDialog``.

The Swing original was a custom ``JDialog`` with a "Show Details" button that
revealed a filtered stack trace. The Tkinter port keeps the same public
surface (constructor + ``show``) but delegates the visual presentation to
``tkinter.messagebox.showerror``: the message and (optionally filtered) stack
trace are combined into the dialog body. This is intentional -- a pixel-perfect
"hide/show details" toggle in stdlib Tk would require building a custom
``Toplevel``, which has no value for the headless / programmatic use cases.

The widget-construction helpers (``create_content``, ``create_error_message``,
``create_detailed_message``) and the parent-centring helper (``position``) are
also exposed for callers that *do* want to embed the dialog as a real
``Toplevel``; they return Tk widgets when a Tk root is available and are
inert otherwise.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
import traceback
from collections.abc import Callable
from tkinter import scrolledtext
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

#: Session-level set of exception *types* the user has chosen to suppress.
#: Upstream's ``isSuppressed(String className)`` operates on stack-frame class
#: names; we additionally expose ``is_suppressed(throwable)`` so the debugger
#: can implement a "don't show me again" check at the dialog level. The set
#: is process-wide and cleared explicitly via :func:`clear_suppressed_types`.
_SUPPRESSED_TYPES: set[type[BaseException]] = set()


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

    # --- widget construction (Tk parity for Swing JComponent factories) ---

    def create_content(
        self,
        message: str | None = None,
        throwable: BaseException | None = None,
        parent: tk.Misc | None = None,
    ) -> tk.Widget | None:
        """Build the dialog body (summary label + collapsible detail pane).

        Returns ``None`` on a headless system where no Tk root is available.
        Otherwise returns a ``ttk.Frame`` containing the message widget on
        top and (if ``throwable`` has a traceback) an expandable
        ``ScrolledText`` showing the formatted stack trace below.

        ``message`` defaults to ``str(throwable)`` and ``throwable`` defaults
        to the dialog's bound error -- matching upstream's no-arg
        ``createContent()`` overload.
        """
        if throwable is None:
            throwable = self._error
        if message is None:
            message = str(throwable) or type(throwable).__name__
        try:
            container = tk.Frame(parent) if parent is not None else tk.Frame()
        except tk.TclError:
            return None
        summary = self.create_error_message(message, parent=container)
        if summary is not None:
            summary.pack(side="top", fill="x", padx=20, pady=(20, 10))
        detail = self.create_detailed_message(throwable, parent=container)
        if detail is not None:
            detail.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 20))
        return container

    def create_error_message(
        self,
        message: str | BaseException,
        parent: tk.Misc | None = None,
    ) -> tk.Widget | None:
        """Build the short, non-editable error-summary widget.

        Upstream uses a read-only ``JEditorPane``; the Tk analogue is a
        ``tk.Label`` (single-line, non-editable by construction). Accepts
        either a pre-rendered string or a ``BaseException`` whose ``str``
        will be used, matching upstream's ``createErrorMessage(Throwable)``.
        """
        if isinstance(message, BaseException):
            message = str(message) or type(message).__name__
        try:
            label = (
                tk.Label(parent, text=message, anchor="w", justify="left")
                if parent is not None
                else tk.Label(text=message, anchor="w", justify="left")
            )
        except tk.TclError:
            return None
        return label

    def create_detailed_message(
        self,
        throwable: BaseException | None = None,
        parent: tk.Misc | None = None,
    ) -> tk.Widget | None:
        """Build the expandable widget showing the formatted stack trace.

        Upstream returns a ``JScrollPane`` wrapping a ``JTextPane``; the Tk
        analogue is a ``ScrolledText`` (a ``Text`` widget pre-wired to a
        vertical scrollbar). When called outside a Tk-capable environment
        the method still returns the formatted trace via :meth:`detailed_text`
        so callers in headless tests get something useful.

        Always populates the widget with the rendered trace before returning.
        """
        if throwable is None:
            throwable = self._error
        text = self.detailed_text(throwable)
        try:
            widget = (
                scrolledtext.ScrolledText(parent, wrap="none", height=15)
                if parent is not None
                else scrolledtext.ScrolledText(wrap="none", height=15)
            )
        except tk.TclError:
            return None
        widget.insert("1.0", text)
        widget.configure(state="disabled")
        return widget

    @staticmethod
    def detailed_text(throwable: BaseException) -> str:
        """Render the formatted exception text (no Tk needed).

        Uses :func:`traceback.format_exception` so the output matches
        Python's ``sys.excepthook`` rendering. Exposed separately so
        headless callers (and tests) can obtain the string without
        constructing a widget.
        """
        return "".join(
            traceback.format_exception(
                type(throwable), throwable, throwable.__traceback__
            )
        )

    # --- session-level suppression ----------------------------------------

    def is_suppressed(self, throwable: BaseException | None = None) -> bool:
        """Return ``True`` if errors of this type have been suppressed.

        This mirrors a "don't show me again" checkbox: once
        :meth:`mark_suppressed` is called for an exception type, subsequent
        ``is_suppressed`` calls for the same type return ``True``. When
        ``throwable`` is omitted, the dialog's bound exception is used.
        """
        if throwable is None:
            throwable = self._error
        return type(throwable) in _SUPPRESSED_TYPES

    def mark_suppressed(self, throwable: BaseException | None = None) -> None:
        """Add an exception type to the session-level suppress list."""
        if throwable is None:
            throwable = self._error
        _SUPPRESSED_TYPES.add(type(throwable))

    # --- positioning ------------------------------------------------------

    def position(
        self,
        component: tk.Misc | None = None,
        parent: tk.Misc | None = None,
    ) -> None:
        """Centre ``component`` over ``parent`` (Swing ``setLocationRelativeTo``).

        Mirrors upstream's static ``position(Component c, Component parent)``.
        Both arguments default to the dialog's own widgets: ``component``
        falls back to the dialog's top-level (if any) and ``parent`` to the
        owner passed at construction time. When ``parent`` is ``None`` the
        component is centred on the primary display instead.

        All Tk operations are guarded by ``tk.TclError`` -- if Tk isn't
        available, the call is a silent no-op.
        """
        if component is None:
            component = getattr(self, "_toplevel", None)
        if component is None:
            return
        if parent is None:
            parent = self._owner
        try:
            component.update_idletasks()  # type: ignore[union-attr]
            cw = int(component.winfo_reqwidth())  # type: ignore[union-attr]
            ch = int(component.winfo_reqheight())  # type: ignore[union-attr]
            if parent is None:
                sw = int(component.winfo_screenwidth())  # type: ignore[union-attr]
                sh = int(component.winfo_screenheight())  # type: ignore[union-attr]
                x = sw // 2 - cw // 2
                y = sh // 2 - ch // 2
            else:
                px = int(parent.winfo_rootx())
                py = int(parent.winfo_rooty())
                pw = int(parent.winfo_width())
                ph = int(parent.winfo_height())
                x = px + pw // 2 - cw // 2
                y = py + ph // 2 - ch // 2
            with contextlib.suppress(tk.TclError):
                component.wm_geometry(f"+{x}+{y}")  # type: ignore[union-attr]
        except tk.TclError:
            return

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


def clear_suppressed_types() -> None:
    """Reset the session-level "don't show me again" list.

    Tests rely on this to avoid cross-test pollution; production code
    typically never calls it.
    """
    _SUPPRESSED_TYPES.clear()
