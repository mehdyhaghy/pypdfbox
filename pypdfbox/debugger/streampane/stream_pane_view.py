"""Tkinter port of ``org.apache.pdfbox.debugger.streampane.StreamPaneView``.

Holds the container frame whose body is swapped between a
:class:`StreamTextView` and a :class:`StreamImageView` depending on
which filter view the user picks.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Iterable, Sequence
from tkinter import ttk
from typing import Any

from pypdfbox.debugger.streampane.stream_image_view import StreamImageView
from pypdfbox.debugger.streampane.stream_text_view import StreamTextView


class StreamPaneView:
    """Container hosting one of the StreamText / StreamImage child views."""

    def __init__(self, master: tk.Misc | None) -> None:
        """Build an empty container frame.

        Upstream's parameterless constructor instantiates a ``JPanel``
        with a ``BorderLayout``; here we own a ``ttk.Frame`` that the
        caller embeds in a notebook / tabbed pane as required.
        """
        self._content_panel = ttk.Frame(master)
        self._content_panel.rowconfigure(0, weight=1)
        self._content_panel.columnconfigure(0, weight=1)
        self._current_child: tk.Widget | None = None

    def show_stream_text(
        self,
        segments: Sequence[tuple[str, str | None]],
        styles: Iterable[tuple[str, dict[str, Any]]] | None = None,
        tool_tip_controller: object | None = None,
    ) -> StreamTextView:
        """Replace the body with a freshly built :class:`StreamTextView`.

        Mirrors upstream's ``showStreamText(StyledDocument, ToolTipController)``.
        Returns the child widget so callers can inspect it in tests.
        """
        self._clear_children()
        view = StreamTextView(
            self._content_panel, segments, styles, tool_tip_controller
        )
        view.grid(row=0, column=0, sticky="nsew")
        self._current_child = view
        return view

    def show_stream_image(
        self,
        image: object,
        zoom_scale: float = 1.0,
        rotation_degrees: int = 0,
    ) -> StreamImageView:
        """Replace the body with a freshly built :class:`StreamImageView`.

        Mirrors upstream's ``showStreamImage(BufferedImage)``.
        """
        self._clear_children()
        view = StreamImageView(
            self._content_panel, image, zoom_scale, rotation_degrees
        )
        view.grid(row=0, column=0, sticky="nsew")
        self._current_child = view
        return view

    def get_stream_panel(self) -> ttk.Frame:
        """Return the container frame — upstream returns the ``JPanel``."""
        return self._content_panel

    @property
    def current_child(self) -> tk.Widget | None:
        """The widget most recently installed via ``show_stream_*``."""
        return self._current_child

    # ---- internals ---------------------------------------------------------

    def _clear_children(self) -> None:
        for child in self._content_panel.winfo_children():
            with contextlib.suppress(tk.TclError):
                child.destroy()
        self._current_child = None
