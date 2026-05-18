"""Wave 1351 coverage-boost tests for :class:`RecentFiles`.

Targets the ``except OSError`` branch on the second ``write_text`` call
inside :meth:`RecentFiles.write_history_to_pref` (lines 145-146).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.debugger.ui.recent_files import RecentFiles


def test_write_history_swallows_write_text_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``Path.write_text`` raises ``OSError`` (e.g. disk full,
    permission denied), ``write_history_to_pref`` returns quietly
    instead of propagating."""
    store = tmp_path / "recent.json"
    recent = RecentFiles("scope.a", 5, path=store)

    original_write_text = Path.write_text

    def _fail_write(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == store:
            raise OSError("disk full")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _fail_write)

    # No exception expected — caller must not see the OSError.
    recent.write_history_to_pref(["/tmp/whatever.pdf"])
    # Confirmation: nothing was written to disk.
    assert not store.exists()
