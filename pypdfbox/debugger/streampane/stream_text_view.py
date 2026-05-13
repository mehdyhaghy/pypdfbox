"""Tkinter port of ``org.apache.pdfbox.debugger.streampane.StreamTextView``.

The upstream class wraps a Swing ``JTextPane`` with a ``StyledDocument``
and a tooltip listener. Tkinter has no ``JTextPane`` — we use a
``tk.Text`` widget configured read-only, with one tag per syntax style.
Text is supplied as a list of ``(text, tag_name_or_None)`` segments;
the caller — :class:`pypdfbox.debugger.streampane.stream_pane.StreamPane`
— assembles these from the content-stream parser output.

Tooltip support is reduced to a no-op shim: the original ``ToolTip`` /
``ToolTipController`` Swing surface is replaced by Tkinter ``bind`` on
``<Motion>``; the actual tooltip text is delegated to the controller
object, which mirrors the upstream interface but returns a plain string.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Iterable, Sequence
from tkinter import ttk
from typing import Any


class StreamTextView(ttk.Frame):
    """Read-only ``tk.Text`` showing a content-stream with operator highlights."""

    def __init__(
        self,
        master: tk.Misc | None,
        segments: Sequence[tuple[str, str | None]],
        styles: Iterable[tuple[str, dict[str, Any]]] | None = None,
        tool_tip_controller: object | None = None,
    ) -> None:
        """Build the view.

        :param master: parent Tkinter widget.
        :param segments: list of ``(text, tag_name_or_None)`` runs to insert.
            Tag names are matched against ``styles``; entries with a tag
            name that is not in ``styles`` are inserted without styling.
        :param styles: optional iterable of ``(tag_name, tag_configure_kwargs)``
            pairs. Each tag is registered on the underlying ``tk.Text``
            via ``tag_configure``. Callers typically pass entries built
            from :class:`OperatorMarker` plus their own number / string /
            name / escape styles.
        :param tool_tip_controller: optional object exposing
            ``get_tool_tip(offset: int, text_widget: tk.Text) -> str``;
            the returned text is shown on motion as a Tk-native tooltip
            (a transient ``Toplevel``). ``None`` disables tooltips.
        """
        super().__init__(master)
        self._tool_tip_controller = tool_tip_controller
        self._tool_tip_window: tk.Toplevel | None = None

        text = tk.Text(
            self,
            wrap="none",
            font=("TkFixedFont", 13),
            state="normal",
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        # Register every requested tag before inserting content so the
        # tag references inside ``insert`` resolve immediately.
        for tag_name, kwargs in styles or ():
            text.tag_configure(tag_name, **kwargs)

        for chunk, tag in segments:
            if tag:
                text.insert("end", chunk, tag)
            else:
                text.insert("end", chunk)

        # Lock the widget against accidental edits — upstream uses
        # ``setEditable(false)`` for the same effect.
        text.configure(state="disabled")

        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._text = text
        if tool_tip_controller is not None:
            text.bind("<Motion>", self._on_motion)
            text.bind("<Leave>", self._hide_tooltip)

    # ---- public accessors --------------------------------------------------

    def get_view(self) -> StreamTextView:
        """Return ``self`` — upstream returns the containing ``JComponent``."""
        return self

    @property
    def text(self) -> tk.Text:
        """The underlying ``tk.Text`` widget (exposed for tests)."""
        return self._text

    # ---- tooltip handling --------------------------------------------------

    def _on_motion(self, event: tk.Event[Any]) -> None:
        if self._tool_tip_controller is None:
            return
        # Convert pixel position to a character index for the controller.
        index = self._text.index(f"@{event.x},{event.y}")
        offset = _text_index_to_offset(self._text, index)
        try:
            tip = self._tool_tip_controller.get_tool_tip(offset, self._text)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — controller errors must not break motion
            tip = None
        if tip:
            self._show_tooltip(event.x_root, event.y_root, tip)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, x_root: int, y_root: int, text: str) -> None:
        self._hide_tooltip()
        window = tk.Toplevel(self._text)
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x_root + 12}+{y_root + 12}")
        label = ttk.Label(window, text=text, relief="solid", borderwidth=1,
                          background="#ffffe1", padding=(4, 2))
        label.pack()
        self._tool_tip_window = window

    def _hide_tooltip(self, _event: tk.Event[Any] | None = None) -> None:
        if self._tool_tip_window is not None:
            with contextlib.suppress(tk.TclError):
                self._tool_tip_window.destroy()
            self._tool_tip_window = None


def _text_index_to_offset(widget: tk.Text, index: str) -> int:
    """Translate a Tk ``Text`` index (``"line.col"``) to an absolute offset."""
    # Tk doesn't have a built-in "index → integer offset" call; we use the
    # difference between ``1.0`` and the supplied index expressed in chars.
    line, col = (int(part) for part in index.split("."))
    offset = 0
    for current_line in range(1, line):
        line_text = widget.get(f"{current_line}.0", f"{current_line}.end")
        offset += len(line_text) + 1  # +1 for the trailing newline
    return offset + col
