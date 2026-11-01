"""Shared fixtures for signaturepane tests.

See :mod:`tests.debugger.streampane.conftest` for the rationale of the
``tk_root`` fixture.
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
