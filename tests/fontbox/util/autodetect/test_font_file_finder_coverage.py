"""Coverage-boost tests for ``pypdfbox.fontbox.util.autodetect.font_file_finder``.

Targets the branches not exercised by the wave-1281 hand-written tests:

* Platform dispatch — Windows, Darwin/Mac, OS/400 branches.
* ``walk`` — missing-directory short circuit, ``OSError`` during
  ``iterdir``, and hidden-directory skip.
* ``check_fontfile`` — every accepted extension and the ``fonts.``
  rejection prefix.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from pypdfbox.fontbox.util.autodetect.font_file_finder import FontFileFinder
from pypdfbox.fontbox.util.autodetect.mac_font_dir_finder import MacFontDirFinder
from pypdfbox.fontbox.util.autodetect.os400_font_dir_finder import OS400FontDirFinder
from pypdfbox.fontbox.util.autodetect.unix_font_dir_finder import UnixFontDirFinder
from pypdfbox.fontbox.util.autodetect.windows_font_dir_finder import (
    WindowsFontDirFinder,
)

# ---------- determine_dir_finder() platform dispatch --------------------


def test_determine_dir_finder_picks_windows() -> None:
    finder = FontFileFinder()
    with mock.patch(
        "pypdfbox.fontbox.util.autodetect.font_file_finder.platform.system",
        return_value="Windows",
    ):
        dir_finder = finder.determine_dir_finder()
    assert isinstance(dir_finder, WindowsFontDirFinder)


def test_determine_dir_finder_picks_mac_for_darwin() -> None:
    finder = FontFileFinder()
    with mock.patch(
        "pypdfbox.fontbox.util.autodetect.font_file_finder.platform.system",
        return_value="Darwin",
    ):
        dir_finder = finder.determine_dir_finder()
    assert isinstance(dir_finder, MacFontDirFinder)


def test_determine_dir_finder_picks_mac_for_mac_prefix() -> None:
    finder = FontFileFinder()
    with mock.patch(
        "pypdfbox.fontbox.util.autodetect.font_file_finder.platform.system",
        return_value="Mac OS X Server",
    ):
        dir_finder = finder.determine_dir_finder()
    assert isinstance(dir_finder, MacFontDirFinder)


def test_determine_dir_finder_picks_os400() -> None:
    finder = FontFileFinder()
    with mock.patch(
        "pypdfbox.fontbox.util.autodetect.font_file_finder.platform.system",
        return_value="OS/400",
    ):
        dir_finder = finder.determine_dir_finder()
    assert isinstance(dir_finder, OS400FontDirFinder)


def test_determine_dir_finder_default_to_unix() -> None:
    finder = FontFileFinder()
    with mock.patch(
        "pypdfbox.fontbox.util.autodetect.font_file_finder.platform.system",
        return_value="Linux",
    ):
        dir_finder = finder.determine_dir_finder()
    assert isinstance(dir_finder, UnixFontDirFinder)


def test_underscore_alias_matches_public_method() -> None:
    # Both names refer to the same underlying function on the class.
    assert FontFileFinder._determine_dir_finder is FontFileFinder.determine_dir_finder


# ---------- walk() error branches ---------------------------------------


def test_walk_returns_early_for_missing_directory() -> None:
    finder = FontFileFinder()
    results: list[str] = []
    # Path that is neither a directory nor existent.
    finder.walk(Path("/nonexistent/should/not/exist"), results)
    assert results == []


def test_walk_handles_oserror_during_iterdir() -> None:
    """If ``iterdir`` raises ``OSError`` the walk logs and short-circuits
    without raising."""
    finder = FontFileFinder()
    results: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with mock.patch.object(
            Path, "iterdir", side_effect=OSError("permission denied")
        ):
            finder.walk(tmp_path, results)
    assert results == []


def test_walk_skips_hidden_directories() -> None:
    """Hidden (dotfile) subdirectories are skipped without recursion."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        hidden_dir = root / ".hidden"
        hidden_dir.mkdir()
        # A font file inside a hidden dir must NOT be discovered.
        (hidden_dir / "secret.ttf").write_bytes(b"\x00\x01")
        # A normal sibling file IS discovered.
        (root / "visible.ttf").write_bytes(b"\x00\x01")

        finder = FontFileFinder()
        results: list[str] = []
        finder.walk(root, results)

        names = [Path(uri.removeprefix("file://")).name for uri in results]
        assert "visible.ttf" in names
        assert "secret.ttf" not in names


def test_walk_recurses_into_non_hidden_directories() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        nested = root / "subdir"
        nested.mkdir()
        (nested / "nested.otf").write_bytes(b"\x00\x01")

        finder = FontFileFinder()
        results: list[str] = []
        finder.walk(root, results)

        names = [Path(uri.removeprefix("file://")).name for uri in results]
        assert "nested.otf" in names


# ---------- check_fontfile() extension matrix ---------------------------


def test_check_fontfile_accepts_each_extension() -> None:
    for ext in (".ttf", ".otf", ".pfb", ".ttc"):
        assert FontFileFinder.check_fontfile(Path(f"sample{ext}")) is True
        # And the uppercase form.
        assert FontFileFinder.check_fontfile(Path(f"SAMPLE{ext.upper()}")) is True


def test_check_fontfile_rejects_non_font_extension() -> None:
    assert FontFileFinder.check_fontfile(Path("image.png")) is False
    assert FontFileFinder.check_fontfile(Path("notes.txt")) is False
    assert FontFileFinder.check_fontfile(Path("font_without_extension")) is False


def test_check_fontfile_rejects_fonts_dot_prefix() -> None:
    """``fonts.dir``, ``fonts.scale`` etc. are X11 metadata files that
    share the ``.ttf`` family of extensions in some installs and must be
    excluded."""
    assert FontFileFinder.check_fontfile(Path("fonts.ttf")) is False
    assert FontFileFinder.check_fontfile(Path("fonts.otf")) is False


def test_check_fontfile_underscore_alias_matches_public_method() -> None:
    assert FontFileFinder._check_fontfile is FontFileFinder.check_fontfile


# ---------- find() no-directory branch ----------------------------------


def test_find_uses_cached_dir_finder_on_repeat_calls() -> None:
    """When ``find()`` is called without a directory, it lazy-creates the
    platform dir finder and caches it for re-use.
    """
    finder = FontFileFinder()
    # Pre-seed with a stub that returns an empty list of directories.
    stub = mock.MagicMock()
    stub.find.return_value = []
    finder._font_dir_finder = stub

    finder.find()
    finder.find()
    # Stub was used both times — no re-instantiation of the OS-specific
    # finder.
    assert stub.find.call_count == 2


def test_find_with_directory_walks_when_directory_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.ttf").write_bytes(b"\x00\x01")
        result = FontFileFinder().find(tmp)
        assert any(uri.endswith("a.ttf") for uri in result)


def test_find_with_directory_returns_empty_when_not_a_dir() -> None:
    """When ``directory`` is a file, not a directory, the walk is
    skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        non_dir = Path(tmp) / "notadir.txt"
        non_dir.write_bytes(b"x")
        assert FontFileFinder().find(str(non_dir)) == []
