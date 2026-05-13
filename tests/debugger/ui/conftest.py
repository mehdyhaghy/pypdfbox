"""Shared fixtures for debugger/ui widget tests.

The Tk-based menu/widget tests need a running ``Tk()`` root, which
cannot be created on headless systems. A ``tk_root`` fixture attempts
to create one and skips the test on ``tk.TclError`` (e.g.
``no display name and no $DISPLAY``).
"""

from __future__ import annotations

import contextlib
import os
import tkinter as tk
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def _tk_root_session() -> Iterator[tk.Tk | None]:
    """Process-wide singleton Tk root.

    tkinter does not robustly support multiple ``Tk()`` instances within a
    single Python process — ``tk.StringVar`` / widgets bind to the first
    root, and recreating roots between tests breaks widget→var coupling
    in subtle ways. We create one root for the whole session and reuse it.

    Setting ``PYPDFBOX_SKIP_TK=1`` in the environment yields ``None`` here
    (and ``tk_root`` then skips) without ever touching Tk. Useful for
    parallel ``pytest`` runs on macOS where two processes contending for
    the WindowServer have been observed to crash one of them.
    """
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
        yield None
        return
    try:
        root = tk.Tk()
    except tk.TclError:
        yield None
        return
    root.withdraw()
    try:
        yield root
    finally:
        with contextlib.suppress(tk.TclError):
            root.destroy()


@pytest.fixture()
def tk_root(_tk_root_session: tk.Tk | None) -> tk.Tk:
    if _tk_root_session is None:
        pytest.skip("no Tk display available (or PYPDFBOX_SKIP_TK=1)")
    return _tk_root_session
