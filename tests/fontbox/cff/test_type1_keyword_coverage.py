"""Coverage-boost tests for :mod:`pypdfbox.fontbox.cff.type1_keyword`.

Targets the still-uncovered surface after wave 1330: ``Key.get_hash_value``,
``Key.__repr__``, ``Key.__eq__`` (the ``NotImplemented`` arm + equality
between distinct instances with the same hash), ``Type1KeyWord.__repr__``,
``Type1KeyWord.__eq__`` (the ``NotImplemented`` arm), and the
``values()`` class method.

The names here trace 1-to-1 to upstream
``CharStringCommand.Type1KeyWord`` / ``CharStringCommand.Key`` so a
coverage regression bisect maps straight back to the upstream operation.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.type1_keyword import Key, Type1KeyWord

# ---------- Key ------------------------------------------------------------

def test_key_get_hash_value_one_byte() -> None:
    # HSTEM has b0=1, no b1 → hash_value == 1.
    assert Key.HSTEM.get_hash_value() == 1


def test_key_get_hash_value_two_byte() -> None:
    # DIV (12, 12) → (12 << 4) + 12 == 204.
    assert Key.DIV.get_hash_value() == (12 << 4) + 12


def test_key_repr_uses_name() -> None:
    assert repr(Key.HSTEM) == "Key.HSTEM"


def test_key_eq_against_non_key_returns_not_implemented() -> None:
    # __eq__ returning NotImplemented falls through to Python's default
    # comparison, which is "not equal" for unrelated types.
    assert (Key.HSTEM == "HSTEM") is False
    assert (Key.HSTEM == 1) is False


def test_key_eq_between_equal_instances_is_true() -> None:
    # Construct a fresh Key instance with the same hash and verify the
    # equality arm.
    other = Key("HSTEM_DUP", 1)
    # Cover both directions through Python's symmetric ``==`` dispatch.
    assert other == Key.HSTEM
    assert Key.HSTEM == other  # noqa: SIM300


def test_key_eq_between_different_instances_is_false() -> None:
    assert Key.HSTEM != Key.VSTEM


def test_key_hash_matches_for_equal_instances() -> None:
    other = Key("HSTEM_DUP", 1)
    assert hash(other) == hash(Key.HSTEM)


def test_key_value_of_key_one_byte_lookup() -> None:
    assert Key.value_of_key(1) is Key.HSTEM


def test_key_value_of_key_two_byte_lookup() -> None:
    assert Key.value_of_key(12, 12) is Key.DIV


def test_key_value_of_key_unknown_returns_none() -> None:
    # 99 is not a registered one-byte hash.
    assert Key.value_of_key(99) is None
    # Two-byte hash unknown as well.
    assert Key.value_of_key(12, 99) is None


# ---------- Type1KeyWord ---------------------------------------------------

def test_type1_keyword_repr_uses_name() -> None:
    assert repr(Type1KeyWord.HSTEM) == "Type1KeyWord.HSTEM"


def test_type1_keyword_str_returns_name() -> None:
    # Mirrors Java's Enum.toString().
    assert str(Type1KeyWord.HSTEM) == "HSTEM"


def test_type1_keyword_eq_against_non_keyword_returns_not_implemented() -> None:
    assert (Type1KeyWord.HSTEM == "HSTEM") is False
    assert (Type1KeyWord.HSTEM == 1) is False


def test_type1_keyword_eq_between_equal_instances_is_true() -> None:
    duplicate = Type1KeyWord("HSTEM", Key.HSTEM)
    assert duplicate == Type1KeyWord.HSTEM


def test_type1_keyword_eq_between_different_is_false() -> None:
    assert Type1KeyWord.HSTEM != Type1KeyWord.VSTEM


def test_type1_keyword_hash_matches_for_equal_instances() -> None:
    duplicate = Type1KeyWord("HSTEM", Key.HSTEM)
    assert hash(duplicate) == hash(Type1KeyWord.HSTEM)


def test_type1_keyword_value_of_key_one_byte() -> None:
    assert Type1KeyWord.value_of_key(1) is Type1KeyWord.HSTEM


def test_type1_keyword_value_of_key_two_byte() -> None:
    assert Type1KeyWord.value_of_key(12, 12) is Type1KeyWord.DIV


def test_type1_keyword_value_of_key_with_key_instance() -> None:
    # The Key-overload arm: pass a Key, get back the matching Type1KeyWord.
    assert Type1KeyWord.value_of_key(Key.HSTEM) is Type1KeyWord.HSTEM


def test_type1_keyword_value_of_key_unknown_one_byte_returns_none() -> None:
    # 99 isn't a registered one-byte op → Key.value_of_key returns None,
    # taking the ``key is None`` short-circuit.
    assert Type1KeyWord.value_of_key(99) is None


def test_type1_keyword_value_of_key_known_key_without_type1_mapping() -> None:
    # Key.AND exists but no Type1KeyWord wraps it (AND is Type 2 only).
    # Exercises the ``return cls._BY_KEY.get(key)`` arm with a miss.
    assert Type1KeyWord.value_of_key(Key.AND) is None


def test_type1_keyword_values_returns_all_registered_members() -> None:
    members = Type1KeyWord.values()
    # Snapshot test against the upstream literal list at
    # CharStringCommand.java:281-289 (26 entries).
    assert len(members) == 26
    assert Type1KeyWord.HSTEM in members
    assert Type1KeyWord.ENDCHAR in members
    # values() returns a copy — mutating it must not affect class state.
    members.clear()
    assert len(Type1KeyWord.values()) == 26
