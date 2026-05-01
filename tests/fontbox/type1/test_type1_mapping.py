"""Tests for ``Type1Mapping`` — value-object behaviour."""

from __future__ import annotations

from pypdfbox.fontbox.type1.type1_mapping import Type1Mapping


class _DummyCharString:
    def __init__(self, name: str) -> None:
        self.glyph_name = name


def test_getters_return_constructor_args() -> None:
    cs = _DummyCharString("A")
    m = Type1Mapping(code=65, name="A", char_string=cs)
    assert m.get_code() == 65
    assert m.get_name() == "A"
    assert m.get_type1_char_string() is cs


def test_properties_mirror_getters() -> None:
    cs = _DummyCharString("A")
    m = Type1Mapping(code=65, name="A", char_string=cs)
    assert m.code == 65
    assert m.name == "A"
    assert m.char_string is cs


def test_repr_includes_fields() -> None:
    m = Type1Mapping(code=65, name="A", char_string=None)
    text = repr(m)
    assert "Type1Mapping" in text
    assert "65" in text
    assert "A" in text


def test_equality_is_structural_for_same_charstring() -> None:
    cs = _DummyCharString("A")
    a = Type1Mapping(code=65, name="A", char_string=cs)
    b = Type1Mapping(code=65, name="A", char_string=cs)
    assert a == b
    assert hash(a) == hash(b)


def test_equality_distinguishes_different_charstring() -> None:
    a = Type1Mapping(code=65, name="A", char_string=_DummyCharString("A"))
    b = Type1Mapping(code=65, name="A", char_string=_DummyCharString("A"))
    # Different charstring instances → not equal even though names match.
    assert a != b


def test_inequality_with_non_mapping_returns_false() -> None:
    m = Type1Mapping(code=65, name="A", char_string=None)
    assert m != "A"
    assert m != 65


def test_none_charstring_is_hashable() -> None:
    m = Type1Mapping(code=65, name="A", char_string=None)
    assert hash(m) == hash(m)


def test_code_is_coerced_to_int() -> None:
    m = Type1Mapping(code=65.0, name="A", char_string=None)  # type: ignore[arg-type]
    assert m.code == 65
    assert isinstance(m.code, int)


def test_name_is_coerced_to_str() -> None:
    m = Type1Mapping(code=65, name="A", char_string=None)
    assert isinstance(m.name, str)


# ---------- tuple-style unpacking ----------


def test_as_tuple_returns_three_field_tuple() -> None:
    cs = _DummyCharString("A")
    m = Type1Mapping(code=65, name="A", char_string=cs)
    assert m.as_tuple() == (65, "A", cs)


def test_as_tuple_with_none_charstring() -> None:
    m = Type1Mapping(code=0, name=".notdef", char_string=None)
    assert m.as_tuple() == (0, ".notdef", None)


def test_iter_supports_unpacking() -> None:
    cs = _DummyCharString("A")
    m = Type1Mapping(code=65, name="A", char_string=cs)
    code, name, char_string = m  # tuple-style unpack
    assert code == 65
    assert name == "A"
    assert char_string is cs


def test_iter_yields_three_items_in_order() -> None:
    m = Type1Mapping(code=65, name="A", char_string=None)
    assert list(m) == [65, "A", None]


# ---------- with_char_string ----------


def test_with_char_string_returns_new_instance() -> None:
    original = Type1Mapping(code=65, name="A", char_string=None)
    new_cs = _DummyCharString("A")
    updated = original.with_char_string(new_cs)
    # original is untouched
    assert original.char_string is None
    # updated has the new charstring but same code+name
    assert updated.code == 65
    assert updated.name == "A"
    assert updated.char_string is new_cs
    # they are distinct instances
    assert updated is not original


def test_with_char_string_to_none() -> None:
    cs = _DummyCharString("A")
    original = Type1Mapping(code=65, name="A", char_string=cs)
    cleared = original.with_char_string(None)
    assert cleared.char_string is None
    # original still has its charstring
    assert original.char_string is cs
