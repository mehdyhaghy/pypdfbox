"""Hand-written tests for ``CharStringCommand`` and the keyword tables."""

from __future__ import annotations

from pypdfbox.fontbox.cff import (
    CharStringCommand,
    Key,
    Type1KeyWord,
    Type2KeyWord,
)


def test_key_value_of_one_byte() -> None:
    assert Key.value_of_key(1) is Key.HSTEM
    assert Key.value_of_key(13) is Key.HSBW
    assert Key.value_of_key(12) is Key.ESCAPE


def test_key_value_of_two_byte() -> None:
    assert Key.value_of_key(12, 0) is Key.DOTSECTION
    assert Key.value_of_key(12, 3) is Key.AND


def test_key_value_of_unknown() -> None:
    assert Key.value_of_key(99) is None


def test_type1_keyword_lookup() -> None:
    # Mirrors upstream Type1KeyWord.valueOfKey contracts.
    assert Type1KeyWord.value_of_key(1) is Type1KeyWord.HSTEM
    assert Type1KeyWord.value_of_key(12, 0) is Type1KeyWord.DOTSECTION
    # AND is Type 2 only — Type1KeyWord lookup must be None.
    assert Type1KeyWord.value_of_key(12, 3) is None


def test_type2_keyword_lookup() -> None:
    assert Type2KeyWord.value_of_key(1) is Type2KeyWord.HSTEM
    assert Type2KeyWord.value_of_key(12, 3) is Type2KeyWord.AND
    # DOTSECTION is Type 1 only — Type2KeyWord lookup must be None.
    assert Type2KeyWord.value_of_key(12, 0) is None


def test_type1_keyword_value_of_key_via_key() -> None:
    assert Type1KeyWord.value_of_key(Key.HSTEM) is Type1KeyWord.HSTEM
    assert Type1KeyWord.value_of_key(Key.AND) is None


def test_type2_keyword_value_of_key_via_key() -> None:
    assert Type2KeyWord.value_of_key(Key.HSTEM) is Type2KeyWord.HSTEM
    assert Type2KeyWord.value_of_key(Key.DOTSECTION) is None


def test_keyword_str() -> None:
    assert str(Type1KeyWord.HSTEM) == "HSTEM"
    assert str(Type2KeyWord.AND) == "AND"


def test_char_string_command_one_byte() -> None:
    # Mirrors CharStringCommandTest.testCharStringCommand (line 42-47).
    cmd = CharStringCommand.get_instance(1)
    assert cmd.get_type1_key_word() is Type1KeyWord.HSTEM
    assert cmd.get_type2_key_word() is Type2KeyWord.HSTEM
    assert str(cmd) == "HSTEM|"


def test_char_string_command_two_byte_type1_only() -> None:
    # Mirrors CharStringCommandTest.testCharStringCommand (line 49-52).
    cmd = CharStringCommand.get_instance(12, 0)
    assert cmd.get_type1_key_word() is Type1KeyWord.DOTSECTION
    assert cmd.get_type2_key_word() is None
    assert str(cmd) == "DOTSECTION|"


def test_char_string_command_two_byte_type2_only_via_array() -> None:
    # Mirrors CharStringCommandTest.testCharStringCommand (line 54-58).
    cmd = CharStringCommand.get_instance([12, 3])
    assert cmd.get_type1_key_word() is None
    assert cmd.get_type2_key_word() is Type2KeyWord.AND
    assert str(cmd) == "AND|"


def test_char_string_command_unknown() -> None:
    # Mirrors CharStringCommandTest.testUnknownCharStringCommand.
    cmd = CharStringCommand.get_instance(99)
    assert str(cmd) == "unknown command|"


def test_char_string_command_equality_and_hash() -> None:
    a = CharStringCommand.get_instance(1)
    b = CharStringCommand.get_instance(1)
    assert a == b
    assert hash(a) == hash(b)


def test_char_string_command_inequality() -> None:
    assert CharStringCommand.get_instance(1) != CharStringCommand.get_instance(3)
    assert CharStringCommand.get_instance(1) != "HSTEM"


def test_char_string_command_static_singletons() -> None:
    # Mirrors the upstream COMMAND_* static fields. ``getInstance`` must
    # return the same cached entries used to build COMMAND_*.
    assert (
        CharStringCommand.COMMAND_CLOSEPATH
        is CharStringCommand.get_instance(Key.CLOSEPATH.hash_value)
    )
    assert (
        CharStringCommand.COMMAND_HSBW
        is CharStringCommand.get_instance(Key.HSBW.hash_value)
    )


def test_char_string_command_get_instance_array_overload() -> None:
    # Single-element array → one-byte lookup.
    cmd = CharStringCommand.get_instance([1])
    assert cmd.get_type1_key_word() is Type1KeyWord.HSTEM
    # Empty / oversize arrays fall back to UNKNOWN.
    unknown = CharStringCommand.get_instance([])
    assert str(unknown) == "unknown command|"


def test_char_string_command_name_property() -> None:
    # ``.name`` mirrors the operator mnemonic the existing
    # ``type1_char_string`` / ``type2_char_string`` modules look up.
    assert CharStringCommand.get_instance(1).name == "HSTEM"
    assert CharStringCommand.get_instance(12, 3).name == "AND"
    assert CharStringCommand.get_instance(99).name is None


# -- Explicit upstream-method mirrors ----------------------------------


def test_to_string_method_matches_str() -> None:
    # Upstream ``toString`` (CharStringCommand.java:234-250).
    cmd = CharStringCommand.get_instance(1)
    assert cmd.to_string() == "HSTEM|"
    assert cmd.to_string() == str(cmd)


def test_to_string_unknown_command() -> None:
    cmd = CharStringCommand.get_instance(99)
    assert cmd.to_string() == "unknown command|"


def test_hash_code_matches_hash() -> None:
    # Upstream ``hashCode`` (CharStringCommand.java:256-259).
    cmd = CharStringCommand.get_instance(1)
    assert cmd.hash_code() == hash(cmd)


def test_equals_strict_class_check() -> None:
    # Upstream ``equals`` (CharStringCommand.java:265-274). Strict class
    # equality — non-CharStringCommand and ``None`` always yield False.
    a = CharStringCommand.get_instance(1)
    b = CharStringCommand.get_instance(1)
    assert a.equals(b) is True
    assert a.equals(CharStringCommand.get_instance(3)) is False
    assert a.equals(None) is False
    assert a.equals("HSTEM") is False


def test_get_key_hash_value_resolves_via_keyword_table() -> None:
    # Upstream ``getKeyHashValue`` (CharStringCommand.java:195-208).
    # Key.AND has hashValue (12<<4)+3 = 195.
    assert CharStringCommand.get_key_hash_value(12, 3) == (12 << 4) + 3
    # Unknown two-byte pair -> KEY_UNKNOWN (99).
    assert CharStringCommand.get_key_hash_value(12, 250) == 99


def test_create_map_returns_command_table_copy() -> None:
    # Upstream ``createMap`` (CharStringCommand.java:56-123). We expose
    # the populated table; the returned dict must be a copy, not the
    # shared cache, so callers can't mutate the singleton table.
    table = CharStringCommand.create_map()
    assert isinstance(table, dict)
    # Sanity-check a representative entry.
    from pypdfbox.fontbox.cff import Key

    assert table[Key.HSTEM.hash_value] is CharStringCommand.get_instance(1)
    assert table is not CharStringCommand._CHAR_STRING_COMMANDS
