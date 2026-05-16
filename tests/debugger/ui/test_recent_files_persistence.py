"""Hand-written tests for the upstream-named persistence entry points on
:class:`pypdfbox.debugger.ui.RecentFiles` (``break_string``,
``read_history_from_pref``, ``write_history_to_pref``).

These cover the three methods ported in wave 1307 to round out parity with
``org.apache.pdfbox.debugger.ui.RecentFiles`` from Apache PDFBox 3.0.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.debugger.ui.recent_files import RecentFiles


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "recent.json"


# --- break_string -----------------------------------------------------------


def test_break_string_short_input_returns_single_piece(store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    pieces = recent.break_string("/short/path.pdf")
    assert pieces == ["/short/path.pdf"]


def test_break_string_empty_input_returns_empty_list(store: Path) -> None:
    """Upstream's ``while (remainingLength > 0)`` never executes for an
    empty string, yielding ``String[0]``. Match that exactly."""
    recent = RecentFiles("scope.a", 5, path=store)
    assert recent.break_string("") == []


def test_break_string_exactly_max_value_length(store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    payload = "x" * RecentFiles.MAX_VALUE_LENGTH
    pieces = recent.break_string(payload)
    assert pieces == [payload]
    assert len(pieces) == 1


def test_break_string_chunks_past_threshold(store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    payload = "a" * (RecentFiles.MAX_VALUE_LENGTH * 2 + 17)
    pieces = recent.break_string(payload)
    # Two full-size chunks plus a tail.
    assert len(pieces) == 3
    assert len(pieces[0]) == RecentFiles.MAX_VALUE_LENGTH
    assert len(pieces[1]) == RecentFiles.MAX_VALUE_LENGTH
    assert len(pieces[2]) == 17
    # Concatenation is lossless.
    assert "".join(pieces) == payload


def test_break_string_just_over_threshold(store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    payload = "b" * (RecentFiles.MAX_VALUE_LENGTH + 1)
    pieces = recent.break_string(payload)
    assert len(pieces) == 2
    assert len(pieces[0]) == RecentFiles.MAX_VALUE_LENGTH
    assert pieces[1] == "b"


# --- write/read round trip --------------------------------------------------


def test_write_then_read_round_trip(tmp_path: Path, store: Path) -> None:
    recent = RecentFiles("scope.a", 5, path=store)
    entries = [
        str(tmp_path / "alpha.pdf"),
        str(tmp_path / "beta.pdf"),
        str(tmp_path / "gamma.pdf"),
    ]
    recent.write_history_to_pref(entries)

    # Fresh instance reads what was written.
    again = RecentFiles("scope.a", 5, path=store)
    assert again.read_history_from_pref() == entries


def test_write_default_uses_in_memory_queue(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    recent = RecentFiles("scope.a", 5, path=store)
    recent.add_file(str(a))
    recent.write_history_to_pref()  # no argument → uses queue
    again = RecentFiles("scope.a", 5, path=store)
    assert again.read_history_from_pref() == [str(a)]


def test_write_empty_is_a_noop(store: Path) -> None:
    """Upstream short-circuits on an empty queue; no file should be written."""
    recent = RecentFiles("scope.a", 5, path=store)
    recent.write_history_to_pref([])
    assert not store.exists()


def test_read_missing_pref_file_returns_empty_list(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    recent = RecentFiles("scope.a", 5, path=missing)
    assert recent.read_history_from_pref() == []


def test_read_empty_pref_file_returns_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")
    recent = RecentFiles("scope.a", 5, path=path)
    assert recent.read_history_from_pref() == []


def test_read_pref_file_other_scope_returns_empty_list(
    tmp_path: Path, store: Path
) -> None:
    """A populated pref file that does not contain our scope returns []."""
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    seeder = RecentFiles("scope.other", 5, path=store)
    seeder.add_file(str(a))
    seeder.close()
    # Now read from a different scope name.
    recent = RecentFiles("scope.a", 5, path=store)
    assert recent.read_history_from_pref() == []


def test_write_chunked_long_path_round_trips(tmp_path: Path, store: Path) -> None:
    """A path longer than ``MAX_VALUE_LENGTH`` survives the chunk-and-join."""
    recent = RecentFiles("scope.a", 5, path=store)
    long_path = "/" + ("p" * (RecentFiles.MAX_VALUE_LENGTH * 2 + 5))
    recent.write_history_to_pref([long_path])
    again = RecentFiles("scope.a", 5, path=store)
    assert again.read_history_from_pref() == [long_path]


def test_write_preserves_other_scopes(tmp_path: Path, store: Path) -> None:
    a = tmp_path / "a.pdf"
    a.write_bytes(b"%PDF-1.4\n")
    b = tmp_path / "b.pdf"
    b.write_bytes(b"%PDF-1.4\n")
    one = RecentFiles("scope.one", 5, path=store)
    one.write_history_to_pref([str(a)])
    two = RecentFiles("scope.two", 5, path=store)
    two.write_history_to_pref([str(b)])
    payload = json.loads(store.read_text(encoding="utf-8"))
    assert payload["scope.one"] == [str(a)]
    assert payload["scope.two"] == [str(b)]


def test_legacy_private_aliases_still_work(tmp_path: Path, store: Path) -> None:
    """The underscore-prefixed names map to the public methods."""
    recent = RecentFiles("scope.a", 5, path=store)
    entries = [str(tmp_path / "x.pdf")]
    recent._write_history_to_pref(entries)  # noqa: SLF001
    again = RecentFiles("scope.a", 5, path=store)
    assert again._read_history_from_pref() == entries  # noqa: SLF001
