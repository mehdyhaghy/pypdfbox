"""Hand-written tests for :class:`Type2KeyWord`."""

from __future__ import annotations

from pypdfbox.fontbox.cff.type1_keyword import Key
from pypdfbox.fontbox.cff.type2_keyword import Type2KeyWord


def test_value_of_key_by_int_one_byte() -> None:
    # HSTEM has b0=1
    kw = Type2KeyWord.value_of_key(1)
    assert kw is not None
    assert kw.name == "HSTEM"


def test_value_of_key_by_int_two_byte() -> None:
    # AND has b0=12, b1=3 -> hash_value=(12<<4)+3
    kw = Type2KeyWord.value_of_key(12, 3)
    assert kw is not None
    assert kw.name == "AND"


def test_value_of_key_unknown_one_byte_returns_none() -> None:
    # 0 is not registered
    assert Type2KeyWord.value_of_key(0) is None


def test_value_of_key_unknown_two_byte_returns_none() -> None:
    assert Type2KeyWord.value_of_key(12, 0xFF) is None


def test_value_of_key_via_key_instance() -> None:
    key = Key.value_of_key(1)
    assert key is not None
    kw = Type2KeyWord.value_of_key(key)
    assert kw is not None
    assert kw.name == "HSTEM"


def test_value_of_key_via_key_not_in_table_returns_none() -> None:
    # Construct a synthetic Key that isn't in Type2KeyWord._BY_KEY.
    # Type1KeyWord has CLOSEPATH which is not a Type2 operator.
    closepath = Key.value_of_key(9)
    assert closepath is not None
    # CLOSEPATH is a Type1-only operator, Type2 has no entry for it.
    assert Type2KeyWord.value_of_key(closepath) is None


def test_repr_includes_class_and_name() -> None:
    kw = Type2KeyWord.value_of_key(1)
    assert kw is not None
    assert repr(kw) == "Type2KeyWord.HSTEM"


def test_str_returns_name() -> None:
    kw = Type2KeyWord.value_of_key(1)
    assert kw is not None
    assert str(kw) == "HSTEM"


def test_hash_is_stable_per_name() -> None:
    kw1 = Type2KeyWord.value_of_key(1)
    kw2 = Type2KeyWord.value_of_key(1)
    assert hash(kw1) == hash(kw2)


def test_equality_matches_name() -> None:
    kw1 = Type2KeyWord.value_of_key(1)
    kw2 = Type2KeyWord.value_of_key(1)
    assert kw1 == kw2


def test_equality_against_non_keyword_returns_notimplemented() -> None:
    kw = Type2KeyWord.value_of_key(1)
    assert kw is not None
    # Python turns NotImplemented into False for ==.
    assert (kw == "HSTEM") is False
    assert (kw == 1) is False
    assert (kw == None) is False  # noqa: E711


def test_values_returns_all_registered() -> None:
    values = Type2KeyWord.values()
    # 49 Type2 operators per CharStringCommand.java:330-343.
    assert len(values) == 49
    # Returned list is a snapshot — mutating it must not affect the
    # internal table.
    values.clear()
    assert len(Type2KeyWord.values()) == 49


def test_class_attribute_access_works() -> None:
    # Each name should be reachable as a class attribute.
    assert Type2KeyWord.HSTEM.name == "HSTEM"
    assert Type2KeyWord.VSTEM.name == "VSTEM"
    assert Type2KeyWord.ENDCHAR.name == "ENDCHAR"
