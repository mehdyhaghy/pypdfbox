"""Shared fixtures for streampane tests.

Widget tests need a running ``Tk()`` root, which can't be created on
headless systems. The ``tk_root`` fixture attempts to create one and
skips the test on ``tk.TclError`` (e.g. ``no display name and no
$DISPLAY``).

Setting ``PYPDFBOX_SKIP_TK=1`` in the environment skips every Tk-based
test in this subpackage -- useful for running multiple ``pytest``
invocations concurrently on macOS without WindowServer contention
(see ``tests/conftest.py``).
"""

from collections.abc import Iterator

import pytest

from tests.debugger._shared_tk_root import SharedTkRoot


@pytest.fixture(scope="package")
def _shared_tk_root() -> Iterator[SharedTkRoot]:
    """One withdrawn Tk root for the whole package (see ``_shared_tk_root``)."""
    shared = SharedTkRoot()
    try:
        yield shared
    finally:
        shared.close()


@pytest.fixture()
def tk_root(_shared_tk_root: SharedTkRoot):
    root = _shared_tk_root.acquire()
    try:
        yield root
    finally:
        _shared_tk_root.reset()
