"""Wave 1403 branch round-out for the module-level JPXFilter registration.

Closes 80->-1 — the ``if not FilterFactory.is_registered("JPXFilter")``
False arm: at first import the filter is registered (True arm). Re-importing
the module via :func:`importlib.reload` re-runs the guard while ``JPXFilter``
is *already* registered, so the registration is skipped and the block exits.
"""

from __future__ import annotations

import importlib

import pypdfbox.filter.jpx_filter as jpx_filter
from pypdfbox.filter.filter_factory import FilterFactory


def test_reload_skips_registration_when_already_registered() -> None:
    """Closes 80->-1: reloading the module with ``JPXFilter`` already in the
    registry takes the skip-registration arm."""
    assert FilterFactory.is_registered("JPXFilter")
    # Reload re-executes the module body; the guard now sees the filter as
    # already registered and skips the register() call.
    reloaded = importlib.reload(jpx_filter)
    assert FilterFactory.is_registered("JPXFilter")
    assert reloaded.JPXFilter is not None
