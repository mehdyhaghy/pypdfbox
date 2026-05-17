"""Coverage tests for :class:`WindowsFontDirFinder`.

The Windows font directory finder reads from ``%windir%`` /
``%LOCALAPPDATA%`` and probes the filesystem for ``FONTS`` / ``PSFONTS``
directories. None of these calls are platform-gated to Windows in the
implementation — they are env-driven — so we can drive every branch
from any host by monkey-patching the environment and
:meth:`pathlib.Path.exists` / :meth:`pathlib.Path.is_dir`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.util.autodetect.windows_font_dir_finder import (
    WindowsFontDirFinder,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _existing_dir(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _set_env(monkeypatch: pytest.MonkeyPatch, *, windir=None, localappdata=None) -> None:
    if windir is None:
        monkeypatch.delenv("windir", raising=False)
    else:
        monkeypatch.setenv("windir", str(windir))
    if localappdata is None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.setenv("LOCALAPPDATA", str(localappdata))


# ---------------------------------------------------------------------------
# windir-driven branch
# ---------------------------------------------------------------------------


def test_windir_path_returns_fonts_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``%windir%`` exists and ``%windir%/FONTS`` is a real directory,
    that directory shows up in the result list."""
    windir = _existing_dir(tmp_path, "Windows")
    _existing_dir(tmp_path, "Windows/FONTS")
    _set_env(monkeypatch, windir=windir)
    result = WindowsFontDirFinder().find()
    assert any(p.name.upper() == "FONTS" for p in result)


def test_windir_with_trailing_slash_is_stripped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trailing ``/`` on ``%windir%`` is trimmed before the join — verify
    by enabling a real FONTS dir under the trimmed path."""
    windir = _existing_dir(tmp_path, "Windows")
    _existing_dir(tmp_path, "Windows/FONTS")
    # Pass the windir with a trailing separator on the end.
    _set_env(monkeypatch, windir=f"{windir}/")
    result = WindowsFontDirFinder().find()
    assert any("FONTS" in str(p).upper() for p in result)


def test_windir_with_trailing_backslash_is_stripped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    windir = _existing_dir(tmp_path, "Windows")
    _existing_dir(tmp_path, "Windows/FONTS")
    _set_env(monkeypatch, windir=f"{windir}\\")
    result = WindowsFontDirFinder().find()
    assert any("FONTS" in str(p).upper() for p in result)


def test_windir_path_collects_psfonts_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``%windir%[:2]/PSFONTS`` exists, the finder appends it.

    ``windir[:2]`` produces a 2-char prefix (e.g. ``C:`` on Windows).
    On POSIX the resulting path is rooted relatively, so we drive the
    branch via patched :meth:`Path.exists` / :meth:`Path.is_dir`.
    """
    monkeypatch.setenv("windir", "C:\\Windows")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    def _exists(self: Path) -> bool:
        s = str(self).upper().replace("\\", "/")
        return s.endswith("PSFONTS")

    def _is_dir(self: Path) -> bool:
        s = str(self).upper().replace("\\", "/")
        return s.endswith("PSFONTS")

    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.setattr(Path, "is_dir", _is_dir)
    result = WindowsFontDirFinder().find()
    assert any("PSFONTS" in str(p).upper() for p in result)


def test_windir_without_fonts_dir_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``%windir%`` set, but no FONTS subdir exists -> empty result."""
    windir = _existing_dir(tmp_path, "Windows-noFONTS")
    _set_env(monkeypatch, windir=windir)
    result = WindowsFontDirFinder().find()
    assert result == []


def test_windir_too_short_falls_back_to_drive_letter_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``len(windir) <= 2`` -> drive-letter heuristic. We patch
    :meth:`Path.exists` / :meth:`Path.is_dir` to return ``False`` so no
    candidate is found but the branch executes."""
    _set_env(monkeypatch, windir="C")  # length 1 -> drive-letter probe

    def _never_exists(_self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", _never_exists)
    monkeypatch.setattr(Path, "is_dir", _never_exists)
    result = WindowsFontDirFinder().find()
    assert result == []


def test_no_windir_drive_letter_probe_finds_fonts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``%windir%`` set -> walk C/D/E drive letters until a match.
    Use a sentinel Path string so the heuristic finds *something*."""
    _set_env(monkeypatch)  # neither env var set

    real_exists = Path.exists
    real_is_dir = Path.is_dir

    # The candidate paths the finder probes have the form
    # ``C:<sep>WINDOWS<sep>FONTS`` / ``C:<sep>PSFONTS`` — match by suffix.
    def _exists(self: Path) -> bool:
        s = str(self).upper().replace("\\", "/")
        if s.endswith("C:/WINDOWS/FONTS") or s.endswith("C:/PSFONTS"):
            return True
        return real_exists(self)

    def _is_dir(self: Path) -> bool:
        s = str(self).upper().replace("\\", "/")
        if s.endswith("C:/WINDOWS/FONTS") or s.endswith("C:/PSFONTS"):
            return True
        return real_is_dir(self)

    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.setattr(Path, "is_dir", _is_dir)
    result = WindowsFontDirFinder().find()
    # Two drive-letter loops ran — each adds at most one entry.
    assert len(result) >= 1
    assert any("FONTS" in str(p).upper() for p in result)


def test_drive_letter_probe_swallows_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``Path.exists`` raises ``OSError`` the probe swallows it
    and continues — logs at DEBUG level."""
    _set_env(monkeypatch)

    def _boom(_self: Path) -> bool:
        raise OSError("simulated permission denied")

    monkeypatch.setattr(Path, "exists", _boom)
    monkeypatch.setattr(Path, "is_dir", _boom)
    result = WindowsFontDirFinder().find()
    assert result == []


# ---------------------------------------------------------------------------
# %LOCALAPPDATA% branch
# ---------------------------------------------------------------------------


def test_localappdata_with_fonts_dir_is_appended(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``%LOCALAPPDATA%/Microsoft/Windows/Fonts`` is appended when it
    exists."""
    _set_env(monkeypatch)  # no windir
    appdata = _existing_dir(tmp_path, "AppData")
    _existing_dir(tmp_path, "AppData/Microsoft/Windows/Fonts")
    # Re-set after the previous helper cleared things.
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))

    # Avoid drive-letter probing from polluting the result.
    def _false(_self: Path) -> bool:
        return False

    real_exists = Path.exists
    real_is_dir = Path.is_dir

    def _exists(self: Path) -> bool:
        s = str(self)
        if "AppData" in s:
            return real_exists(self)
        return False

    def _is_dir(self: Path) -> bool:
        s = str(self)
        if "AppData" in s:
            return real_is_dir(self)
        return False

    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.setattr(Path, "is_dir", _is_dir)
    result = WindowsFontDirFinder().find()
    assert any(
        "AppData" in str(p) and "Fonts" in str(p) for p in result
    )


def test_localappdata_set_but_fonts_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``%LOCALAPPDATA%`` defined but the Fonts subdir doesn't exist —
    branch executes the ``if .exists()`` check and skips."""
    _set_env(monkeypatch, localappdata=tmp_path / "EmptyAppData")

    def _false(_self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", _false)
    monkeypatch.setattr(Path, "is_dir", _false)
    result = WindowsFontDirFinder().find()
    assert result == []


def test_localappdata_unset_skips_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``%LOCALAPPDATA%`` the user-profile branch is skipped."""
    _set_env(monkeypatch)

    def _false(_self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", _false)
    monkeypatch.setattr(Path, "is_dir", _false)
    result = WindowsFontDirFinder().find()
    assert result == []
