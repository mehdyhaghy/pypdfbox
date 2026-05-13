"""Shared fixtures for flagbitspane tests.

Widget tests need a running ``Tk()`` root, which can't be created on
headless systems. The ``tk_root`` fixture attempts to create one and skips
the test on ``tk.TclError`` (e.g. ``no display name and no $DISPLAY``).
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
