"""Modal log-viewer dialog backed by a Tkinter ``Toplevel`` + ``Text``.

Ported from ``org.apache.pdfbox.debugger.ui.LogDialog``.

The Swing original uses a ``JTextPane`` with styled runs to colour each log
level. We map that to a ``tk.Text`` widget with per-level tags. Counts of
each severity are tracked and rendered into a status label, matching the
upstream summary string ("3 exceptions, 1 fatal error, 2 errors, 4 warnings").

The dialog registers itself as the active dialog sink of
:mod:`pypdfbox.debugger.ui.debug_log` so :class:`DebugLog` instances forward
messages here automatically.
"""

from __future__ import annotations

import contextlib
import io
import tkinter as tk
import traceback
from typing import Any

from .debug_log import set_dialog_sink

#: Maps the upstream level keys to (display label, foreground, background).
_LEVEL_STYLES: dict[str, tuple[str, str, str]] = {
    "fatal": ("Fatal", "#FFFFFF", "#000000"),
    "error": ("Error", "#FF291F", "#FFF0F0"),
    "warn": ("Warning", "#614201", "#FFFCE5"),
    "info": ("Info", "#203261", "#E2E8FF"),
    "debug": ("Debug", "#32612E", "#F4FFEC"),
    "trace": ("Trace", "#64438D", "#FEF3FF"),
}

_NAME_COLOR = "#6A6A6A"


class LogDialog:
    """Custom log dialog showing styled log records and a status summary."""

    _instance: LogDialog | None = None

    def __init__(
        self,
        owner: tk.Misc | None,
        log_label: tk.Label | None = None,
    ) -> None:
        self._owner = owner
        self._log_label = log_label
        self._toplevel: tk.Toplevel | None = None
        self._text: tk.Text | None = None
        self._scrollbar: tk.Scrollbar | None = None
        self._text_font_height: float | None = None
        self._fatal_count = 0
        self._error_count = 0
        self._warn_count = 0
        self._other_count = 0
        self._exception_count = 0
        # Buffered records, replayed once the toplevel is built. Each entry
        # is ``(name, level, message, throwable)``.
        self._pending: list[tuple[str, str, Any, BaseException | None]] = []

    # --- singleton lifecycle ----------------------------------------------

    @classmethod
    def init(
        cls,
        owner: tk.Misc | None,
        log_label: tk.Label | None = None,
    ) -> None:
        """Instantiate the singleton and register the sink."""
        cls._instance = cls(owner, log_label)
        set_dialog_sink(cls._instance.log)

    @classmethod
    def instance(cls) -> LogDialog | None:
        return cls._instance

    # --- public API -------------------------------------------------------

    def set_text_font_height(self, height: float) -> None:
        """Apply an explicit font height (in points)."""
        self._text_font_height = float(height)
        if self._text is not None:
            self._text.configure(
                font=("TkDefaultFont", int(self._text_font_height)),
            )

    def set_visible(self, visible: bool = True) -> None:
        """Show or hide the dialog (Swing parity)."""
        if visible:
            self.show()
        elif self._toplevel is not None:
            self._toplevel.withdraw()

    def show(self) -> tk.Toplevel:
        """Create the toplevel (if needed) and bring it forward."""
        if self._toplevel is None:
            self._build()
        assert self._toplevel is not None
        self._toplevel.deiconify()
        self._toplevel.lift()
        return self._toplevel

    def pack(self) -> None:
        """Auto-size the toplevel (Swing parity)."""
        if self._toplevel is not None:
            self._toplevel.update_idletasks()

    def get_content_pane(self) -> tk.Toplevel | None:
        return self._toplevel

    def log(
        self,
        name: str,
        level: str,
        message: Any,
        throwable: BaseException | None = None,
    ) -> None:
        """Append a styled log record.

        If the toplevel hasn't been built yet, the record is buffered and
        replayed when :meth:`show` is called.
        """
        # Bump counters regardless of whether the widget exists. Tests can
        # assert on the counters without forcing a Tk root.
        self._bump_counters(level, throwable)
        if self._text is None:
            self._pending.append((name, level, message, throwable))
            self.update_status_bar()
            return
        self._render_record(name, level, message, throwable)
        self.update_status_bar()

    def clear(self) -> None:
        """Reset all counters and clear the dialog and status label."""
        self._fatal_count = 0
        self._error_count = 0
        self._warn_count = 0
        self._other_count = 0
        self._exception_count = 0
        self._pending = []
        if self._text is not None:
            self._text.configure(state="normal")
            self._text.delete("1.0", "end")
            self._text.configure(state="disabled")
        if self._log_label is not None:
            self._log_label.configure(text="")

    # --- counters (exposed for testing) -----------------------------------

    def get_fatal_count(self) -> int:
        return self._fatal_count

    def get_error_count(self) -> int:
        return self._error_count

    def get_warn_count(self) -> int:
        return self._warn_count

    def get_other_count(self) -> int:
        return self._other_count

    def get_exception_count(self) -> int:
        return self._exception_count

    def get_status_text(self) -> str:
        """Return the summary text exposed by the bottom-panel label."""
        return self._build_status_text()

    # --- internals --------------------------------------------------------

    def _bump_counters(
        self,
        level: str,
        throwable: BaseException | None,
    ) -> None:
        if level == "fatal":
            self._fatal_count += 1
        elif level == "error":
            self._error_count += 1
        elif level == "warn":
            self._warn_count += 1
        elif level in ("info", "debug", "trace"):
            self._other_count += 1
        else:
            raise ValueError(level)
        if throwable is not None:
            self._exception_count += 1

    def _build(self) -> None:
        parent = self._owner
        toplevel = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
        toplevel.title("Log")
        if parent is not None:
            with contextlib.suppress(tk.TclError):  # pragma: no cover - platform
                toplevel.transient(parent)
        text = tk.Text(toplevel, wrap="word", state="disabled")
        scroll = tk.Scrollbar(toplevel, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        self._toplevel = toplevel
        self._text = text
        self._scrollbar = scroll
        # Configure per-level tags.
        for level, (_label, fg, bg) in _LEVEL_STYLES.items():
            text.tag_configure(
                f"level-{level}",
                foreground=fg,
                background=bg,
            )
        text.tag_configure("name", foreground=_NAME_COLOR)
        if self._text_font_height is not None:
            text.configure(font=("TkDefaultFont", int(self._text_font_height)))
        # Replay any buffered records.
        for name, level, message, throwable in self._pending:
            self._render_record(name, level, message, throwable)
        self._pending = []

    def _render_record(
        self,
        name: str,
        level: str,
        message: Any,
        throwable: BaseException | None,
    ) -> None:
        text = self._text
        assert text is not None
        style = _LEVEL_STYLES.get(level)
        if style is None:
            raise ValueError(level)
        label, _fg, _bg = style
        short_name = name.rsplit(".", 1)[-1]
        rendered = "(null)" if message is None else str(message)
        if throwable is not None:
            buf = io.StringIO()
            traceback.print_exception(
                type(throwable),
                throwable,
                throwable.__traceback__,
                file=buf,
            )
            rendered += "\n    " + buf.getvalue()
        text.configure(state="normal")
        text.insert("end", f" {label} ", (f"level-{level}",))
        text.insert("end", f" [{short_name}]", ("name",))
        text.insert("end", f" {rendered}\n")
        text.see("end")
        text.configure(state="disabled")

    def _build_status_text(self) -> str:
        infos: list[str] = []
        if self._exception_count > 0:
            infos.append(
                f"{self._exception_count} exception"
                + ("s" if self._exception_count > 1 else "")
            )
        if self._fatal_count > 0:
            infos.append(
                f"{self._fatal_count} fatal error"
                + ("s" if self._fatal_count > 1 else "")
            )
        if self._error_count > 0:
            infos.append(
                f"{self._error_count} error"
                + ("s" if self._error_count > 1 else "")
            )
        if self._warn_count > 0:
            infos.append(
                f"{self._warn_count} warning"
                + ("s" if self._warn_count > 1 else "")
            )
        if self._other_count > 0:
            infos.append(
                f"{self._other_count} message"
                + ("s" if self._other_count > 1 else "")
            )
        return ", ".join(infos)

    def update_status_bar(self) -> None:
        """Refresh the status-bar label with the current counter summary.

        Mirrors the upstream private helper. Public so callers — and tests —
        can resync the label after manipulating counters directly.
        """
        info = self._build_status_text()
        if self._log_label is not None:
            self._log_label.configure(text=info)

    # Backwards-compatible private alias.
    _update_status_bar = update_status_bar
