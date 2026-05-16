"""Coverage-boost tests for ``pypdfbox.util.small_map``.

Targets branches missed by ``test_util_wave1281.py`` — None-key/value
guards, entry-view set/equals/hash, find_value helper, remove-by-key
with last-entry shrink, MutableMapping dunders, and the
``init_map`` constructor shape.
"""

from __future__ import annotations

import pytest

from pypdfbox.util.small_map import SmallMap, SmallMapEntry


# ---------------------------------------------------------------------------
# constructor + put_all
# ---------------------------------------------------------------------------


def test_constructor_seeds_from_init_map() -> None:
    sm = SmallMap({"a": 1, "b": 2})
    assert sm.size() == 2
    assert sm.get("a") == 1
    assert sm.get("b") == 2


def test_default_constructor_starts_empty() -> None:
    sm: SmallMap = SmallMap()
    assert sm.is_empty()
    assert sm.size() == 0


# ---------------------------------------------------------------------------
# find_key / find_value helpers
# ---------------------------------------------------------------------------


def test_find_key_returns_minus_one_when_empty_or_none() -> None:
    sm: SmallMap = SmallMap()
    assert sm.find_key("missing") == -1
    sm.put("a", 1)
    assert sm.find_key(None) == -1
    assert sm.find_key("missing") == -1
    assert sm.find_key("a") == 0


def test_find_value_returns_minus_one_when_empty_or_none() -> None:
    sm: SmallMap = SmallMap()
    assert sm.find_value("missing") == -1
    sm.put("a", 1)
    sm.put("b", 2)
    assert sm.find_value(None) == -1
    assert sm.find_value(999) == -1
    assert sm.find_value(2) == 3


# ---------------------------------------------------------------------------
# put / put_all / get / remove
# ---------------------------------------------------------------------------


def test_put_rejects_none_key_or_value() -> None:
    sm: SmallMap = SmallMap()
    with pytest.raises(TypeError):
        sm.put(None, 1)
    with pytest.raises(TypeError):
        sm.put("a", None)


def test_put_overwrite_returns_previous_value() -> None:
    sm: SmallMap = SmallMap()
    assert sm.put("a", 1) is None
    assert sm.put("a", 2) == 1
    assert sm.get("a") == 2


def test_put_appends_when_key_missing() -> None:
    sm = SmallMap({"a": 1})
    assert sm.put("b", 2) is None
    assert sm.size() == 2


def test_get_with_default_when_missing() -> None:
    sm: SmallMap = SmallMap()
    assert sm.get("missing", "fallback") == "fallback"
    sm.put("a", 1)
    assert sm.get("missing") is None
    assert sm.get("a") == 1


def test_remove_unknown_key_returns_none() -> None:
    sm: SmallMap = SmallMap()
    assert sm.remove("missing") is None
    sm.put("a", 1)
    assert sm.remove("missing") is None


def test_remove_only_entry_resets_internal_array() -> None:
    sm = SmallMap({"a": 1})
    assert sm.remove("a") == 1
    assert sm.is_empty()
    # internal array set back to None to mirror upstream's empty state
    assert sm._map_arr is None


def test_remove_keeps_other_entries() -> None:
    sm = SmallMap({"a": 1, "b": 2, "c": 3})
    assert sm.remove("b") == 2
    assert sm.key_set() == ["a", "c"]
    assert sm.values() == [1, 3]


def test_contains_key_and_value() -> None:
    sm = SmallMap({"a": 1})
    assert sm.contains_key("a")
    assert not sm.contains_key("b")
    assert sm.contains_value(1)
    assert not sm.contains_value(999)


def test_clear_resets_to_empty() -> None:
    sm = SmallMap({"a": 1, "b": 2})
    sm.clear()
    assert sm.is_empty()
    assert sm.size() == 0


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------


def test_key_set_values_entry_set_empty_when_empty() -> None:
    sm: SmallMap = SmallMap()
    assert sm.key_set() == []
    assert sm.values() == []
    assert sm.entry_set() == []


def test_entry_set_iteration_and_get_value() -> None:
    sm = SmallMap({"a": 1, "b": 2})
    entries = sm.entry_set()
    assert len(entries) == 2
    pairs = {(e.get_key(), e.get_value()) for e in entries}
    assert pairs == {("a", 1), ("b", 2)}


# ---------------------------------------------------------------------------
# SmallMapEntry surface
# ---------------------------------------------------------------------------


def test_entry_set_value_updates_underlying_map() -> None:
    sm = SmallMap({"a": 1})
    entry = sm.entry_set()[0]
    old = entry.set_value(99)
    assert old == 1
    assert sm.get("a") == 99


def test_entry_set_value_rejects_none() -> None:
    sm = SmallMap({"a": 1})
    entry = sm.entry_set()[0]
    with pytest.raises(TypeError):
        entry.set_value(None)


def test_entry_equals_and_hash() -> None:
    sm = SmallMap({"a": 1})
    e1 = sm.entry_set()[0]
    e2 = sm.entry_set()[0]
    assert e1 == e2
    assert e1.equals(e2)
    assert not e1.equals("not an entry")
    assert hash(e1) == hash("a")
    assert e1.hash_code() == hash(e1)
    # entry views read live from the owner — so two entries with mismatched
    # values are unreachable through this API; cover the non-entry inequality
    # path instead.
    assert e1 != "not-an-entry-instance"


def test_entry_with_distinct_keys_are_not_equal() -> None:
    sm = SmallMap({"a": 1, "b": 1})
    e_a, e_b = sm.entry_set()
    assert e_a != e_b


# ---------------------------------------------------------------------------
# MutableMapping protocol
# ---------------------------------------------------------------------------


def test_dunder_get_set_del_and_contains() -> None:
    sm = SmallMap({"a": 1})
    assert sm["a"] == 1
    sm["b"] = 2
    assert sm["b"] == 2
    del sm["a"]
    assert "a" not in sm
    assert "b" in sm

    with pytest.raises(KeyError):
        _ = sm["missing"]
    with pytest.raises(KeyError):
        del sm["missing"]


def test_dunder_iter_and_len() -> None:
    sm = SmallMap({"a": 1, "b": 2})
    assert list(iter(sm)) == ["a", "b"]
    assert len(sm) == 2
