"""Wave 1365 parity tests for :class:`RecentFiles`.

Upstream ``RecentFiles.java`` is the MRU-list backing store the debugger
"Recent Files" submenu reads from. The existing waves cover the happy path
and many error cases; this file fills in remaining upstream semantics:

* ``add_file`` evicts only when length exceeds ``maximum``, not when it
  equals it — verifies the upstream off-by-one threshold of ``maximum + 1``.
* ``get_files`` caps the survivor list at ``maximum`` by discarding the
  oldest survivor (covers the post-existence-filter pop-front branch).
* ``remove_file`` on a path that's not in the queue is a silent no-op
  (upstream's ``LinkedList.remove(Object)`` returns false; we suppress the
  Python ``ValueError`` via ``contextlib.suppress``).
* ``add_file(None)`` is a no-op (defensive parity with the Java port).
* ``break_string`` handles a single-character input correctly (the
  ``while remaining > 0`` loop runs exactly once).
* ``close()`` followed by a fresh ``RecentFiles`` with the same slug
  rehydrates the history (the full persist round-trip).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.debugger.ui.recent_files import RecentFiles


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "recent.json"


def test_add_file_below_threshold_does_not_evict(
    tmp_path: Path, store: Path
) -> None:
    """``maximum = 3`` => four adds fit (upstream threshold is ``max + 1``);
    the fifth add evicts the oldest."""
    paths = [tmp_path / f"f{i}.pdf" for i in range(5)]
    for p in paths:
        p.write_bytes(b"")
    recent = RecentFiles("scope", 3, path=store)
    for p in paths[:4]:
        recent.add_file(str(p))
    # Four entries still fit because upstream caps at ``maximum + 1``.
    assert len(recent._file_paths) == 4
    recent.add_file(str(paths[4]))
    # Now the fifth add evicts the oldest.
    assert len(recent._file_paths) == 4
    assert str(paths[0]) not in list(recent._file_paths)
    assert str(paths[4]) in list(recent._file_paths)


def test_get_files_caps_survivors_at_maximum(
    tmp_path: Path, store: Path
) -> None:
    """All four paths exist on disk; ``get_files()`` drops the oldest to
    cap at ``maximum``."""
    paths = [tmp_path / f"g{i}.pdf" for i in range(4)]
    for p in paths:
        p.write_bytes(b"")
    recent = RecentFiles("scope-g", 3, path=store)
    for p in paths:
        recent.add_file(str(p))
    files = recent.get_files()
    # Exactly maximum survivors; oldest dropped.
    assert len(files) == 3
    assert str(paths[0]) not in files
    assert str(paths[3]) in files


def test_remove_file_absent_path_is_noop(tmp_path: Path, store: Path) -> None:
    """Removing a path not in the queue must not raise."""
    real = tmp_path / "real.pdf"
    real.write_bytes(b"")
    recent = RecentFiles("scope-r", 5, path=store)
    recent.add_file(str(real))
    recent.remove_file(str(tmp_path / "ghost.pdf"))  # absent
    assert list(recent._file_paths) == [str(real)]


def test_add_file_none_is_noop(store: Path) -> None:
    """Passing ``None`` to ``add_file`` does not corrupt the queue."""
    recent = RecentFiles("scope-n", 5, path=store)
    recent.add_file(None)
    assert recent.is_empty()


def test_break_string_single_character() -> None:
    """One character runs the loop once and yields one piece."""
    recent = RecentFiles("scope-s", 5)
    assert recent.break_string("x") == ["x"]


def test_close_round_trips_via_disk(tmp_path: Path, store: Path) -> None:
    """``close`` persists; a fresh instance with the same slug + path reads
    the history back."""
    real = tmp_path / "persisted.pdf"
    real.write_bytes(b"")
    first = RecentFiles("scope-rt", 4, path=store)
    first.add_file(str(real))
    first.close()
    # Re-open and verify the history was rehydrated.
    second = RecentFiles("scope-rt", 4, path=store)
    assert list(second._file_paths) == [str(real)]
    # Other scopes remain absent.
    other = RecentFiles("scope-other", 4, path=store)
    assert other.is_empty()


def test_close_preserves_other_scope_via_disk(
    tmp_path: Path, store: Path
) -> None:
    """Closing scope A must not wipe scope B's history (the JSON merge
    branch of ``write_history_to_pref``)."""
    a_file = tmp_path / "a.pdf"
    b_file = tmp_path / "b.pdf"
    a_file.write_bytes(b"")
    b_file.write_bytes(b"")
    a = RecentFiles("a", 3, path=store)
    a.add_file(str(a_file))
    a.close()
    b = RecentFiles("b", 3, path=store)
    b.add_file(str(b_file))
    b.close()
    # Both scopes survive.
    payload = json.loads(store.read_text(encoding="utf-8"))
    assert "a" in payload and "b" in payload
    assert payload["a"] == [str(a_file)]
    assert payload["b"] == [str(b_file)]
