"""Wave 1403 — branch round-out for :meth:`FontMappers.instance`.

Closes the partial arc ``[63,68]`` — the ``_default is None`` False
branch: when ``_instance`` is unset but a cached ``_default`` already
exists, :meth:`instance` skips rebuilding the default and re-uses the
cached mapper.

The public :meth:`set`/:meth:`reset` API clears ``_instance`` and
``_default`` together, so this specific intermediate state (no instance,
cached default) can only be reproduced by seeding the module globals
directly — done here under a save/restore guard so no singleton state
leaks into other tests.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox import font_mappers as fm_module
from pypdfbox.fontbox.font_mappers import FontMappers


def test_instance_reuses_cached_default_without_rebuilding() -> None:
    """With ``_instance is None`` but ``_default`` already populated, the
    ``_default is None`` guard takes its False arc ([63,68]) and the
    cached default is promoted to the active instance."""
    saved_instance = fm_module._instance
    saved_default = fm_module._default
    try:
        cached: Any = FontMappers.instance()  # build a real default mapper
        # Reproduce the intermediate state: no active instance, but the
        # default is still cached.
        fm_module._instance = None
        fm_module._default = cached

        result = FontMappers.instance()
        # The cached default was reused (not rebuilt) and promoted.
        assert result is cached
        assert fm_module._instance is cached
    finally:
        fm_module._instance = saved_instance
        fm_module._default = saved_default
