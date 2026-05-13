"""Hand-written tests for ``pypdfbox.debugger.ui.WindowPrefs``."""

from pathlib import Path

import pytest

from pypdfbox.debugger.ui import WindowPrefs


@pytest.fixture
def prefs_path(tmp_path: Path) -> Path:
    return tmp_path / "debugger.json"


def test_bounds_round_trip(prefs_path: Path) -> None:
    prefs = WindowPrefs("test.scope", path=prefs_path)
    prefs.set_bounds((10, 20, 800, 600))
    # Re-open from disk to be sure we actually persisted.
    again = WindowPrefs("test.scope", path=prefs_path)
    assert again.get_bounds() == (10, 20, 800, 600)


def test_bounds_defaults_seed_from_screen(prefs_path: Path) -> None:
    prefs = WindowPrefs("test.scope", path=prefs_path)
    bounds = prefs.get_bounds(screen_width=1600, screen_height=900)
    assert bounds == (400, 225, 800, 450)


def test_divider_round_trip(prefs_path: Path) -> None:
    prefs = WindowPrefs("test.scope", path=prefs_path)
    prefs.set_divider_location(123)
    assert prefs.get_divider_location() == 123


def test_divider_default_uses_screen_width(prefs_path: Path) -> None:
    prefs = WindowPrefs("test.scope", path=prefs_path)
    assert prefs.get_divider_location(screen_width=1024) == 128


def test_extended_state_round_trip(prefs_path: Path) -> None:
    prefs = WindowPrefs("test.scope", path=prefs_path)
    assert prefs.get_extended_state() == 0  # NORMAL
    prefs.set_extended_state(6)  # MAXIMIZED_BOTH on Frame
    assert WindowPrefs("test.scope", path=prefs_path).get_extended_state() == 6


def test_two_scopes_share_a_file(prefs_path: Path) -> None:
    a = WindowPrefs("scope.a", path=prefs_path)
    b = WindowPrefs("scope.b", path=prefs_path)
    a.set_bounds((1, 2, 3, 4))
    b.set_bounds((5, 6, 7, 8))
    # Re-load to ensure both buckets persist.
    a2 = WindowPrefs("scope.a", path=prefs_path)
    b2 = WindowPrefs("scope.b", path=prefs_path)
    assert a2.get_bounds() == (1, 2, 3, 4)
    assert b2.get_bounds() == (5, 6, 7, 8)


def test_class_scope_uses_qualified_name(prefs_path: Path) -> None:
    class Marker:
        pass

    prefs = WindowPrefs(Marker, path=prefs_path)
    prefs.set_bounds((9, 9, 9, 9))
    again = WindowPrefs(Marker, path=prefs_path)
    assert again.get_bounds() == (9, 9, 9, 9)


def test_corrupt_file_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ not valid json", encoding="utf-8")
    prefs = WindowPrefs("test", path=path)
    # No crash; returns defaults seeded from the requested screen size.
    assert prefs.get_extended_state() == 0
