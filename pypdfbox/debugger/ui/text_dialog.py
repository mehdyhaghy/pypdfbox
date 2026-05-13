"""Modal text-display dialog backed by a Tkinter ``Toplevel`` + ``Text``.

Ported from ``org.apache.pdfbox.debugger.ui.TextDialog``. Used by the
"Extract Text" path of the debugger to show the result of text extraction.

The upstream class is a singleton: a static ``instance()`` returns the same
dialog across calls so the caller can reuse it. We preserve that, including
the ``init(owner)`` two-step construction pattern -- the dialog is built
lazily so importers can register the class without requiring a Tk root.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from typing import Any

#: Default font scale factor matching upstream's ``size * 1.5``.
_FONT_SCALE = 1.5


class TextDialog:
    """Window for text extraction results."""

    _instance: TextDialog | None = None

    def __init__(self, owner: tk.Misc | None) -> None:
        self._owner = owner
        # The toplevel is built on first ``show`` so headless tests can
        # construct a ``TextDialog`` without raising ``TclError``.
        self._toplevel: tk.Toplevel | None = None
        self._text: tk.Text | None = None
        self._scrollbar: tk.Scrollbar | None = None
        self._text_font_height: float | None = None
        self._pending_text: str = ""

    # --- singleton lifecycle -----------------------------------------------

    @classmethod
    def init(cls, owner: tk.Misc | None) -> None:
        """Instantiate the singleton."""
        cls._instance = cls(owner)

    @classmethod
    def instance(cls) -> TextDialog | None:
        """Return the singleton (or ``None`` if :meth:`init` wasn't called)."""
        return cls._instance

    # --- public API --------------------------------------------------------

    def clear(self) -> None:
        """Reset the dialog's text content to empty."""
        self._pending_text = ""
        if self._text is not None:
            self._text.configure(state="normal")
            self._text.delete("1.0", "end")
            self._text.configure(state="disabled")

    def set_text(self, text: str) -> None:
        """Replace the dialog's text content."""
        self._pending_text = text
        if self._text is not None:
            self._text.configure(state="normal")
            self._text.delete("1.0", "end")
            self._text.insert("1.0", text)
            self._text.configure(state="disabled")

    def set_text_font_height(self, height: float) -> None:
        """Apply an explicit font height (in points)."""
        self._text_font_height = float(height)
        if self._text is not None:
            self._apply_font()

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
        """Auto-size the toplevel to fit its contents (Swing parity)."""
        if self._toplevel is not None:
            self._toplevel.update_idletasks()

    def get_content_pane(self) -> tk.Toplevel | None:
        """Return the underlying toplevel."""
        return self._toplevel

    # --- internal ---------------------------------------------------------

    def _build(self) -> None:
        parent = self._owner
        toplevel = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
        toplevel.title("Text")
        if parent is not None:
            # ``transient`` is a no-op on some window managers.
            with contextlib.suppress(tk.TclError):  # pragma: no cover - platform
                toplevel.transient(parent)
        text = tk.Text(toplevel, wrap="none")
        scroll = tk.Scrollbar(toplevel, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        self._toplevel = toplevel
        self._text = text
        self._scrollbar = scroll
        self._apply_font()
        if self._pending_text:
            self.set_text(self._pending_text)

    def _apply_font(self) -> None:
        text = self._text
        if text is None:
            return
        if self._text_font_height is not None:
            # Use a tuple so Tk picks a sensible family fallback.
            text.configure(font=("TkDefaultFont", int(self._text_font_height)))
            return
        # Mirror upstream: derive a font scaled by 1.5 from the default.
        try:
            current = text.cget("font")
            # ``current`` may be a named font or a tuple/string; fall back
            # gracefully if we can't parse the size.
            base_size = _extract_font_size(current)
        except (tk.TclError, ValueError):
            base_size = 10
        text.configure(
            font=("TkDefaultFont", max(1, int(round(base_size * _FONT_SCALE))))
        )


def _extract_font_size(spec: Any) -> int:
    """Best-effort extraction of a font size from a Tk font spec."""
    if isinstance(spec, tuple) and len(spec) >= 2:
        return int(spec[1])
    if isinstance(spec, str):
        parts = spec.split()
        for part in parts:
            try:
                return int(part)
            except ValueError:
                continue
    return 10
