"""Wave 1495 — behaviour-anchored coverage for ``NativeFontDirFinder.find``'s
remaining branches: a subclass that returns ``None`` from
``get_searchable_directories`` (the ``or []`` guard), and the normal
exists/is-dir filtering that keeps only real directories.

Mirrors ``org.apache.fontbox.util.autodetect.NativeFontDirFinder``.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.util.autodetect.native_font_dir_finder import (
    NativeFontDirFinder,
)


def test_find_returns_empty_when_searchable_directories_is_none() -> None:
    class _NoneFinder(NativeFontDirFinder):
        def get_searchable_directories(self):  # type: ignore[override]
            return None  # ``or []`` guard must absorb this without raising.

    assert _NoneFinder().find() == []


def test_find_keeps_only_existing_directories(tmp_path: Path) -> None:
    real_dir = tmp_path / "fonts"
    real_dir.mkdir()
    a_file = tmp_path / "afile.ttf"
    a_file.write_text("x", encoding="utf-8")
    missing = tmp_path / "nope"

    class _Finder(NativeFontDirFinder):
        def get_searchable_directories(self):  # type: ignore[override]
            return [str(real_dir), str(a_file), str(missing)]

    result = _Finder().find()
    # The plain file and the missing path are filtered out; only the real dir
    # survives the ``exists() and is_dir()`` test.
    assert result == [real_dir]


def test_find_returns_empty_for_empty_candidate_list() -> None:
    class _EmptyFinder(NativeFontDirFinder):
        def get_searchable_directories(self):  # type: ignore[override]
            return []

    assert _EmptyFinder().find() == []
