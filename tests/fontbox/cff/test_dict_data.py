"""Hand-written tests for :class:`pypdfbox.fontbox.cff.dict_data.DictData`,
:class:`Entry`, and :class:`Key`.

Mirrors upstream ``CFFParser.DictData`` (``CFFParser.java`` lines
1308-1430): operator-keyed entry map, add/get/get_number/get_array/
get_boolean/get_delta semantics, plus ``Entry.get_delta`` running-sum
behaviour for delta-encoded operand lists.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.dict_data import DictData, Entry, Key


def _entry(operator: str, *operands: object) -> Entry:
    e = Entry()
    for op in operands:
        e.add_operand(op)
    e.operator_name = operator
    return e


# -- Entry --------------------------------------------------------------


def test_entry_add_and_size() -> None:
    e = Entry()
    assert not e.has_operands()
    assert e.size() == 0
    e.add_operand(7)
    e.add_operand(42)
    assert e.has_operands()
    assert e.size() == 2
    assert e.get_number(0) == 7
    assert e.get_number(1) == 42
    assert e.get_operands() == [7, 42]


def test_entry_get_boolean_recognises_zero_and_one() -> None:
    e = _entry("isFixedPitch", 0)
    assert e.get_boolean(0, default_value=True) is False
    e2 = _entry("isFixedPitch", 1)
    assert e2.get_boolean(0, default_value=False) is True


def test_entry_get_boolean_falls_back_for_other_values() -> None:
    e = _entry("isFixedPitch", 5)
    # Non-{0,1} integers fall back to the default (upstream warns).
    assert e.get_boolean(0, default_value=True) is True
    assert e.get_boolean(0, default_value=False) is False


def test_entry_get_delta_running_sum() -> None:
    # PDFBOX-4038 example from upstream: BlueValues are stored as deltas
    # and ``get_delta`` materialises the running sum.
    e = _entry("BlueValues", -12, 12, 496, 12, 70, 12, 45, 12, 5, 12, 37, 12)
    assert e.get_delta() == [-12, 0, 496, 508, 578, 590, 635, 647, 652, 664, 701, 713]


def test_entry_to_string_contains_operands_and_operator() -> None:
    e = _entry("FontBBox", -200, -200, 1000, 900)
    rep = e.to_string()
    assert "operands=[-200, -200, 1000, 900]" in rep
    assert "operator=FontBBox" in rep


# -- DictData -----------------------------------------------------------


def test_dictdata_add_skips_entries_without_operator() -> None:
    d = DictData()
    e = Entry()  # operator_name still None
    e.add_operand(1)
    d.add(e)
    assert d.entries == {}


def test_dictdata_get_entry_returns_added_entry() -> None:
    d = DictData()
    e = _entry("FullName", 391)
    d.add(e)
    assert d.get_entry("FullName") is e
    assert d.get_entry("Notice") is None


def test_dictdata_get_number_with_default() -> None:
    d = DictData()
    d.add(_entry("ItalicAngle", -10))
    assert d.get_number("ItalicAngle", 0) == -10
    assert d.get_number("UnderlinePosition", -100) == -100


def test_dictdata_get_array_with_default() -> None:
    d = DictData()
    d.add(_entry("FontBBox", -100, -100, 1000, 900))
    assert d.get_array("FontBBox", None) == [-100, -100, 1000, 900]
    assert d.get_array("XUID", None) is None
    assert d.get_array("XUID", []) == []


def test_dictdata_get_boolean_with_default() -> None:
    d = DictData()
    d.add(_entry("isFixedPitch", 1))
    assert d.get_boolean("isFixedPitch", default_value=False) is True
    assert d.get_boolean("ForceBold", default_value=False) is False


def test_dictdata_get_delta_running_sum() -> None:
    d = DictData()
    d.add(_entry("BlueValues", -12, 12, 496, 12))
    assert d.get_delta("BlueValues", None) == [-12, 0, 496, 508]
    assert d.get_delta("OtherBlues", None) is None


def test_dictdata_get_entry_via_key_object() -> None:
    d = DictData()
    d.add(_entry("FullName", 391))
    assert d.get_entry(Key("FullName")) is not None
    assert d.get_entry(Key("Notice")) is None


def test_key_equality_and_hash() -> None:
    a = Key("Notice")
    b = Key("Notice")
    c = Key("FullName")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert a.equals(b) and not a.equals(c)
    # ``hash_code`` mirrors upstream ``Object.hashCode`` (we hash the
    # name string); ``__hash__`` follows dataclass semantics — they
    # are different views of the same equality, both deterministic.
    assert a.hash_code() == b.hash_code()
    assert a.hash_code() != c.hash_code()
    assert "Notice" in a.to_string()


def test_dictdata_to_string_contains_entries() -> None:
    d = DictData()
    d.add(_entry("FullName", 391))
    rep = d.to_string()
    assert "DictData" in rep
    assert "FullName" in rep
