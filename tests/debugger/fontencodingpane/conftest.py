"""Shared fixtures for fontencodingpane tests.

Widget tests need a running ``Tk()`` root, which isn't available on
headless CI runners. The ``tk_root`` fixture skips when the root can't
be created (``tk.TclError``).
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
