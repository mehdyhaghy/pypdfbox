"""Hand-written tests for ``pypdfbox.fontbox.util.autodetect``."""

from __future__ import annotations

import platform
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.util.autodetect import (
    FontFileFinder,
    MacFontDirFinder,
    OS400FontDirFinder,
    UnixFontDirFinder,
)


def test_mac_font_dir_finder_lists_candidates() -> None:
    candidates = MacFontDirFinder().get_searchable_directories()
    assert any("Library/Fonts" in c for c in candidates)


def test_unix_font_dir_finder_lists_candidates() -> None:
    candidates = UnixFontDirFinder().get_searchable_directories()
    assert any("share/fonts" in c for c in candidates)


def test_os400_font_dir_finder_lists_candidates() -> None:
    candidates = OS400FontDirFinder().get_searchable_directories()
    assert any("/QIBM/" in c for c in candidates)


def test_font_file_finder_filters_directory() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "regular.ttf"
        bad = Path(tmp) / "fonts.dir"
        non_font = Path(tmp) / "ignore.txt"
        good.write_bytes(b"\x00\x01")
        bad.write_bytes(b"\x00")
        non_font.write_bytes(b"x")
        result = FontFileFinder().find(tmp)
        assert any(uri.endswith("regular.ttf") for uri in result)
        assert not any(uri.endswith("fonts.dir") for uri in result)
        assert not any(uri.endswith("ignore.txt") for uri in result)


def test_font_file_finder_returns_empty_for_missing_dir() -> None:
    finder = FontFileFinder()
    assert finder.find("/nonexistent/path/should/return/empty") == []


@pytest.mark.skipif(platform.system() == "Windows", reason="Unix-only sanity check")
def test_font_file_finder_dispatches_native_finder() -> None:
    finder = FontFileFinder()
    # Just check the find() method doesn't raise; results depend on host.
    finder.find()
