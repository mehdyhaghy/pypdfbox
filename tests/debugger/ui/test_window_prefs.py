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


def test_non_dict_payload_returns_defaults(tmp_path: Path) -> None:
    """A JSON file that doesn't decode to a dict at the top level is ignored."""
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    prefs = WindowPrefs("test", path=path)
    assert prefs.get_extended_state() == 0
    # Persisting from defaults should still work.
    prefs.set_extended_state(2)
    assert WindowPrefs("test", path=path).get_extended_state() == 2


def test_payload_with_non_dict_slug_falls_back(tmp_path: Path) -> None:
    """When the slug key resolves to something other than a dict, the
    pref store quietly resets that slug's bucket without nuking siblings."""
    import json

    path = tmp_path / "mixed.json"
    path.write_text(
        json.dumps({"test": "not-a-dict", "other": {"k": {"V": 1}}}),
        encoding="utf-8",
    )
    prefs = WindowPrefs("test", path=path)
    # ``_data`` reset to empty for this slug.
    assert prefs.get_extended_state() == 0


def test_payload_filters_non_dict_inner_values(tmp_path: Path) -> None:
    """The inner dictionary keeps only dict-valued entries."""
    import json

    path = tmp_path / "mixed-inner.json"
    path.write_text(
        json.dumps({"test": {"window_prefs_": {"X": 1, "Y": 2}, "junk": 7}}),
        encoding="utf-8",
    )
    prefs = WindowPrefs("test", path=path)
    # Junk key skipped; valid window_prefs_ dict preserved.
    assert prefs.get_bounds()[0:2] == (1, 2)


def test_corrupt_existing_payload_is_replaced_on_save(tmp_path: Path) -> None:
    """``_save`` should not nuke existing well-formed siblings of the
    new slug even if it sees garbage on first read."""
    path = tmp_path / "weird.json"
    path.write_text("not-json", encoding="utf-8")
    prefs = WindowPrefs("test", path=path)
    prefs.set_bounds((1, 2, 3, 4))
    # File now contains our valid payload.
    again = WindowPrefs("test", path=path)
    assert again.get_bounds() == (1, 2, 3, 4)


def test_coerce_int_on_non_numeric_data(tmp_path: Path) -> None:
    """A non-numeric stored value falls back to the requested default."""
    import json

    path = tmp_path / "nonnumeric.json"
    path.write_text(
        json.dumps({"test": {"window_prefs_": {"X": "garbage"}}}),
        encoding="utf-8",
    )
    prefs = WindowPrefs("test", path=path)
    # ``_coerce_int`` returns default when the stored value can't parse.
    x = prefs.get_bounds(screen_width=400, screen_height=400)[0]
    assert x == 100  # 400 // 4 default


def test_node_get_int_with_invalid_value(tmp_path: Path) -> None:
    """``_node_get_int`` returns the default when the stored value
    cannot be converted to ``int``."""
    import json

    path = tmp_path / "div.json"
    path.write_text(
        json.dumps({"test": {"window_prefs_": {"DIV": "xx"}}}),
        encoding="utf-8",
    )
    prefs = WindowPrefs("test", path=path)
    assert prefs.get_divider_location(screen_width=400) == 50  # 400 // 8


def test_default_prefs_path_uses_xdg_on_posix(monkeypatch, tmp_path: Path) -> None:
    """``_default_prefs_path`` honours ``XDG_CONFIG_HOME`` on non-Windows."""
    from pypdfbox.debugger.ui import window_prefs

    monkeypatch.setattr(window_prefs.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = window_prefs._default_prefs_path()  # noqa: SLF001
    assert path == tmp_path / "pypdfbox" / "debugger.json"


def test_default_prefs_path_falls_back_to_home_on_posix(monkeypatch) -> None:
    from pypdfbox.debugger.ui import window_prefs

    monkeypatch.setattr(window_prefs.sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    path = window_prefs._default_prefs_path()  # noqa: SLF001
    assert path.name == "debugger.json"
    assert "pypdfbox" in path.parts


def test_default_prefs_path_on_windows(monkeypatch, tmp_path: Path) -> None:
    from pypdfbox.debugger.ui import window_prefs

    monkeypatch.setattr(window_prefs.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    path = window_prefs._default_prefs_path()  # noqa: SLF001
    assert path == tmp_path / "pypdfbox" / "debugger.json"


def test_default_prefs_path_on_windows_no_appdata(monkeypatch) -> None:
    from pypdfbox.debugger.ui import window_prefs

    monkeypatch.setattr(window_prefs.sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    path = window_prefs._default_prefs_path()  # noqa: SLF001
    assert path.name == "debugger.json"
    assert "pypdfbox" in path.parts


def test_load_handles_oserror(monkeypatch, tmp_path: Path) -> None:
    """A non-FileNotFoundError ``OSError`` on read should yield defaults
    without raising."""
    path = tmp_path / "exists.json"
    path.write_text('{"x": {"y": {}}}', encoding="utf-8")

    orig_read_text = Path.read_text

    def boom(self: Path, *args: object, **kwargs: object) -> str:
        if self == path:
            raise PermissionError("locked")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    prefs = WindowPrefs("test", path=path)
    # ``_data`` should default to empty on read failure.
    assert prefs.get_extended_state() == 0


def test_save_handles_mkdir_oserror(monkeypatch, tmp_path: Path) -> None:
    """If creating the parent directory fails, ``_save`` swallows the error
    and silently no-ops."""
    target_dir = tmp_path / "no-perms"
    target = target_dir / "prefs.json"

    orig_mkdir = Path.mkdir

    def boom(
        self: Path,
        *args: object,
        **kwargs: object,
    ) -> None:
        if self == target_dir:
            raise PermissionError("read-only")
        orig_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", boom)

    prefs = WindowPrefs("test", path=target)
    # Should not raise even though the parent dir creation will fail.
    prefs.set_bounds((1, 2, 3, 4))
    # And the file should not have been written.
    assert not target.exists()


def test_save_handles_write_oserror(monkeypatch, tmp_path: Path) -> None:
    """If writing the file fails, ``_save`` swallows the error silently."""
    target = tmp_path / "prefs.json"
    prefs = WindowPrefs("test", path=target)

    orig_write_text = Path.write_text

    def boom(self: Path, *args: object, **kwargs: object) -> int:
        if self == target:
            raise PermissionError("locked file")
        return orig_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", boom)
    # Should not raise.
    prefs.set_bounds((9, 9, 9, 9))
