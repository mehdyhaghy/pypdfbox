"""File open/save chooser backed by :mod:`tkinter.filedialog`.

Ported from ``org.apache.pdfbox.debugger.ui.FileOpenSaveDialog``.

The Swing original wrapped a single static ``JFileChooser`` with an
``approveSelection`` override that prompted on overwrite. We port the same
public contract:

* ``open_file()`` -> path to user-selected file (or ``None``)
* ``save_file(bytes, extension)`` -> ``True`` on save, ``False`` on cancel
* ``save_document(document, extension)`` -> ``True`` on save, ``False`` on cancel

``tkinter.filedialog.asksaveasfilename`` already shows the platform's native
overwrite-confirmation dialog, so the upstream JFileChooser override has no
Python counterpart.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

#: Test hook -- replaced via :func:`set_open_impl` to avoid blocking dialogs.
_open_impl: Callable[..., str] | None = None
#: Test hook -- replaced via :func:`set_save_impl` to avoid blocking dialogs.
_save_impl: Callable[..., str] | None = None


def _default_open(**kwargs: Any) -> str:
    from tkinter import filedialog

    return filedialog.askopenfilename(**kwargs)


def _default_save(**kwargs: Any) -> str:
    from tkinter import filedialog

    return filedialog.asksaveasfilename(**kwargs)


#: Tk-style filter spec: ``[("PDF files", "*.pdf"), ("All files", "*.*")]``.
FileFilter = Sequence[tuple[str, str]]


class FileOpenSaveDialog:
    """A small helper class for picking files to open or save."""

    def __init__(
        self,
        parent_ui: Any,
        file_filter: FileFilter | None = None,
    ) -> None:
        """Construct the dialog.

        :param parent_ui: the parent widget; passed to ``filedialog`` via
            ``parent=``. May be ``None`` for headless / scripted contexts.
        :param file_filter: optional list of ``(label, pattern)`` tuples.
        """
        self._parent = parent_ui
        # Defensive copy so callers can mutate their own lists freely.
        self._file_filter: list[tuple[str, str]] | None = (
            list(file_filter) if file_filter else None
        )

    # --- open ------------------------------------------------------------

    def open_file(self) -> str | None:
        """Prompt the user and return the chosen file path, or ``None``."""
        kwargs: dict[str, Any] = {}
        if self._parent is not None:
            kwargs["parent"] = self._parent
        if self._file_filter is not None:
            kwargs["filetypes"] = list(self._file_filter)
        impl = _open_impl if _open_impl is not None else _default_open
        result = impl(**kwargs)
        # ``askopenfilename`` returns "" on cancel; mirror Java's ``null``.
        return result or None

    # --- save bytes ------------------------------------------------------

    def save_file(self, data: bytes, extension: str | None) -> bool:
        """Save ``data`` to a user-selected file. Returns ``True`` on save."""
        chosen = self._ask_save_path()
        if not chosen:
            return False
        if extension is not None and not chosen.endswith(extension):
            chosen = chosen + "." + extension
        Path(chosen).write_bytes(data)
        return True

    # --- save document ---------------------------------------------------

    def save_document(self, document: Any, extension: str) -> bool:
        """Save ``document`` to a user-selected ``.pdf`` (or other) file.

        Mirrors the upstream call sequence:
        ``setAllSecurityToBeRemoved(true)`` followed by ``save(filename)``.
        """
        chosen = self._ask_save_path()
        if not chosen:
            return False
        if not chosen.endswith(extension):
            chosen = chosen + "." + extension
        document.set_all_security_to_be_removed(True)
        document.save(chosen)
        return True

    # --- internals -------------------------------------------------------

    def _ask_save_path(self) -> str | None:
        kwargs: dict[str, Any] = {}
        if self._parent is not None:
            kwargs["parent"] = self._parent
        if self._file_filter is not None:
            kwargs["filetypes"] = list(self._file_filter)
        impl = _save_impl if _save_impl is not None else _default_save
        result = impl(**kwargs)
        return result or None


def set_open_impl(impl: Callable[..., str] | None) -> None:
    """Install (or clear) the ``askopenfilename`` implementation."""
    global _open_impl
    _open_impl = impl


def set_save_impl(impl: Callable[..., str] | None) -> None:
    """Install (or clear) the ``asksaveasfilename`` implementation."""
    global _save_impl
    _save_impl = impl
