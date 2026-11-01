"""One reusable, withdrawn ``Tk`` root per debugger test package.

Creating a ``tk.Tk()`` costs ~10 ms (Tcl interpreter + Tk init), and the
pane packages used to build a fresh root for every test. The pane
``conftest.py`` files now hold one :class:`SharedTkRoot` in a
package-scoped fixture and hand the same root to each test, resetting it
in between:

* every child widget the test created is destroyed;
* pending ``after`` callbacks are cancelled, so they cannot fire into the
  next test;
* the root is withdrawn again in case the test showed it.

If a test destroys the root itself, the next test gets a fresh one. The
root is destroyed when the package finishes, so it never becomes the
default root for tests outside the package.
"""

import contextlib
import os
import tkinter as tk

import pytest


class SharedTkRoot:
    def __init__(self) -> None:
        self._root: tk.Tk | None = None

    @staticmethod
    def _alive(root: tk.Tk) -> bool:
        try:
            return bool(root.winfo_exists())
        except tk.TclError:
            return False

    def acquire(self) -> tk.Tk:
        if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":
            pytest.skip("PYPDFBOX_SKIP_TK=1 -- Tk tests opted out")
        if self._root is None or not self._alive(self._root):
            try:
                root = tk.Tk()
            except tk.TclError as exc:
                pytest.skip(f"no Tk display available: {exc}")
            root.withdraw()
            self._root = root
        return self._root

    def reset(self) -> None:
        root = self._root
        if root is None:
            return
        if not self._alive(root):
            self._root = None
            return
        try:
            for child in list(root.winfo_children()):
                with contextlib.suppress(tk.TclError):
                    child.destroy()
            for after_id in root.tk.splitlist(root.tk.call("after", "info")):
                with contextlib.suppress(tk.TclError):
                    root.after_cancel(after_id)
            root.withdraw()
            root.update_idletasks()
        except tk.TclError:
            # Root is in an unusable state; drop it so the next test
            # starts from a fresh one.
            self.close()

    def close(self) -> None:
        root, self._root = self._root, None
        if root is not None:
            with contextlib.suppress(tk.TclError):
                root.destroy()
