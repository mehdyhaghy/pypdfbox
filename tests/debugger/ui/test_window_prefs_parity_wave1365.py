"""Wave 1365 parity tests for :class:`WindowPrefs`.

Upstream ``WindowPrefs.java`` persists window geometry preferences. The
existing waves cover the happy path, defaults, and error returns. This file
fills in the remaining upstream-mirrored semantics:

* ``set_bounds`` overwrites all four fields atomically (no partial updates).
* ``get_bounds`` with a custom screen size uses that size for defaults.
* Divider location persists independently of bounds.
* Extended-state defaults to ``NORMAL`` (= 0) when never written.
* A non-integer value stored under a known key still falls back to the
  caller-supplied default (covers the ``TypeError/ValueError`` branch of
  ``_coerce_int``).
* The JSON file uses ``sort_keys=True`` so two saves with the same data
  produce identical bytes (deterministic-output parity).
* A second slug under the same file does not affect the first slug's bounds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.debugger.ui.window_prefs import WindowPrefs


@pytest.fixture
def prefs_path(tmp_path: Path) -> Path:
    return tmp_path / "prefs.json"


def test_set_bounds_overwrites_all_fields(prefs_path: Path) -> None:
    prefs = WindowPrefs("scope.a", path=prefs_path)
    prefs.set_bounds((10, 20, 100, 200))
    prefs.set_bounds((300, 400, 500, 600))
    assert prefs.get_bounds() == (300, 400, 500, 600)


def test_get_bounds_honours_caller_screen_size(prefs_path: Path) -> None:
    """When nothing was ever stored, defaults come from the keyword args."""
    prefs = WindowPrefs("scope.s", path=prefs_path)
    # screen_width // 4, screen_height // 4, screen_width // 2, screen_height // 2
    assert prefs.get_bounds(screen_width=400, screen_height=200) == (
        100,
        50,
        200,
        100,
    )


def test_divider_independent_of_bounds(prefs_path: Path) -> None:
    """Setting bounds must not blow away an existing divider value."""
    prefs = WindowPrefs("scope.d", path=prefs_path)
    prefs.set_divider_location(123)
    prefs.set_bounds((1, 2, 3, 4))
    assert prefs.get_divider_location() == 123
    assert prefs.get_bounds() == (1, 2, 3, 4)


def test_extended_state_defaults_to_normal(prefs_path: Path) -> None:
    """A never-written extended state reads back as NORMAL (= 0)."""
    prefs = WindowPrefs("scope.e", path=prefs_path)
    assert prefs.get_extended_state() == 0


def test_get_bounds_falls_back_when_stored_field_is_non_numeric(
    prefs_path: Path,
) -> None:
    """A bogus stored W value triggers ``_coerce_int`` → default branch."""
    # Hand-craft a payload with a non-numeric W under the expected key.
    slug = "scope.bad"
    payload = {slug: {"window_prefs_": {"X": 10, "Y": 20, "W": "oops", "H": 40}}}
    prefs_path.write_text(json.dumps(payload), encoding="utf-8")
    prefs = WindowPrefs(slug, path=prefs_path)
    x, y, w, h = prefs.get_bounds(screen_width=400, screen_height=200)
    # X and Y are valid; W falls back to screen_width // 2; H is valid.
    assert x == 10
    assert y == 20
    assert w == 200
    assert h == 40


def test_save_is_deterministic_with_sorted_keys(prefs_path: Path) -> None:
    """Writing the same data twice yields identical bytes (sort_keys=True)."""
    prefs = WindowPrefs("scope.det", path=prefs_path)
    prefs.set_bounds((1, 2, 3, 4))
    first_bytes = prefs_path.read_bytes()
    # A noop re-save: assign the same value to trigger another write.
    prefs.set_bounds((1, 2, 3, 4))
    second_bytes = prefs_path.read_bytes()
    assert first_bytes == second_bytes
    # The payload must in fact be sorted at the slug-level — verify by
    # walking the parsed dict.
    parsed = json.loads(first_bytes.decode("utf-8"))
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_two_slugs_in_one_file_are_isolated(prefs_path: Path) -> None:
    """Two ``WindowPrefs`` instances pointing at the same file must not
    bleed bounds across slugs."""
    a = WindowPrefs("slug.a", path=prefs_path)
    b = WindowPrefs("slug.b", path=prefs_path)
    a.set_bounds((1, 2, 3, 4))
    b.set_bounds((10, 20, 30, 40))
    # Reload from disk via fresh instances.
    a2 = WindowPrefs("slug.a", path=prefs_path)
    b2 = WindowPrefs("slug.b", path=prefs_path)
    assert a2.get_bounds() == (1, 2, 3, 4)
    assert b2.get_bounds() == (10, 20, 30, 40)
