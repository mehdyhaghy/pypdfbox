"""Shared fixtures for stringpane tests.

See :mod:`tests.debugger.streampane.conftest` for the rationale of the
``tk_root`` fixture.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Iterator

import pytest


@pytest.fixture()
def tk_root() -> Iterator[tk.Tk]:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()
