"""Hand-written tests for :class:`pypdfbox.debugger.ui.RecentFiles`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.debugger.ui.recent_files import RecentFiles


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "recent.json"


def test_fresh_history_is_empty(store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    assert recent.is_empty() is True
    assert recent.get_files() == []


def test_add_file_then_get_files(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    b.write_bytes(b"%PDF-1.4\n")
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(str(a))
    recent.add_file(str(b))
    assert recent.is_empty() is False
    assert recent.get_files() == [str(a), str(b)]


def test_get_files_filters_missing_files(tmp_path: Path, store: Path) -> None:
    real = tmp_path / "real.pdf"
    real.write_bytes(b"%PDF-1.4\n")
    ghost = tmp_path / "ghost.pdf"  # not created
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(str(real))
    recent.add_file(str(ghost))
    assert recent.get_files() == [str(real)]


def test_add_file_evicts_when_full(tmp_path: Path, store: Path) -> None:
    """Capacity test: after ``maximum + 1`` adds the oldest is dropped."""
    recent = RecentFiles("scope.a", 2, path=store)
    paths = [tmp_path / f"{i}.pdf" for i in range(4)]
    for p in paths:
        p.write_bytes(b"%PDF-1.4\n")
        recent.add_file(str(p))
    # ``maximum + 1`` == 3; once we hit 3 we start evicting on every add.
    # After 4 adds, the oldest entry should be gone.
    files = recent.get_files()
    assert str(paths[0]) not in files
    # ``getFiles`` caps the survivors at ``maximum``.
    assert len(files) <= 2


def test_remove_file(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    b.write_bytes(b"%PDF-1.4\n")
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(str(a))
    recent.add_file(str(b))
    recent.remove_file(str(a))
    assert recent.get_files() == [str(b)]
    # Removing something not in the history is a no-op.
    recent.remove_file("/nope")


def test_remove_all(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(str(a))
    assert recent.is_empty() is False
    recent.remove_all()
    assert recent.is_empty() is True


def test_close_persists_history(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    b.write_bytes(b"%PDF-1.4\n")
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(str(a))
    recent.add_file(str(b))
    recent.close()

    # Re-open and confirm we picked up the prior session.
    again = RecentFiles("scope.a", 5, path=store)
    assert again.get_files() == [str(a), str(b)]


def test_close_on_empty_does_not_wipe_other_scopes(tmp_path: Path, store: Path) -> None:
    # Pre-seed disk state for a different scope.
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    other = RecentFiles("scope.other", 5, path=store)
    other.add_file(str(a))
    other.close()
    # Now a fresh instance for a different slug that closes empty must not
    # delete the existing slug.
    recent = RecentFiles("scope.a", 5, path=store)
    recent.close()
    payload = json.loads(store.read_text(encoding="utf-8"))
    assert "scope.other" in payload


def test_two_scopes_share_one_file(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    b.write_bytes(b"%PDF-1.4\n")
    one = RecentFiles("scope.one", 5, path=store)
    two = RecentFiles("scope.two", 5, path=store)
    one.add_file(str(a))
    two.add_file(str(b))
    one.close()
    two.close()
    payload = json.loads(store.read_text(encoding="utf-8"))
    assert payload["scope.one"] == [str(a)]
    assert payload["scope.two"] == [str(b)]


def test_class_scope_uses_qualified_name(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF-1.4\n")

    class Marker:
        pass

    recent = RecentFiles(Marker, 5, path=store)
    recent.add_file(str(a))
    recent.close()
    again = RecentFiles(Marker, 5, path=store)
    assert again.get_files() == [str(a)]


def test_corrupt_file_returns_empty_history(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ not valid json", encoding="utf-8")
    recent = RecentFiles("scope.a", 5, path=path)
    assert recent.is_empty()


def test_add_none_is_a_noop(store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(None)
    assert recent.is_empty()
