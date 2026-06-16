"""Wave 1577 fuzz parity tests for the generic name/number tree lookup.

Hammers ``PDNameTreeNode.get_value`` / ``PDNumberTreeNode.get_value`` and the
``/Limits`` descent machinery against the Apache PDFBox 3.0.7 contract:

* a flat ``/Names`` leaf — exact hit, miss, byte/string ordering;
* ``/Kids`` descent via ``/Limits`` (key in first kid, last kid, between kids);
* boundary inclusivity (key == lower limit, key == upper limit);
* a number tree via ``/Nums``;
* ``get_names`` / ``get_numbers`` flattening behaviour (NON-recursive own-leaf
  for name trees, recursive for number trees — mirroring upstream);
* ``get_kids`` returning ``None`` on a leaf;
* an empty tree and a key outside all limits;
* ``set_names`` / ``set_numbers`` round-trips;
* the ``get_lower_limit`` / ``get_upper_limit`` accessors.

Two upstream-divergence contracts are asserted explicitly (both pinned in the
live oracle ``test_name_number_tree_fuzz_wave1549.py`` and CHANGES.md):

* D1 — NAME-tree overlapping ``/Limits``: upstream early-returns the first
  in-range kid's ``null`` and loses a later sibling's value; pypdfbox falls
  through to the sibling and recovers it.
* the NUMBER-tree fall-through where upstream itself loops while ``null``, so a
  sibling holding the key IS reached on both sides.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_NUMS = COSName.get_pdf_name("Nums")
_LIMITS = COSName.get_pdf_name("Limits")


# ---------- concrete int number-tree node ----------


class _IntNumberTreeNode(PDNumberTreeNode[int]):
    def convert_cos_to_value(self, base: COSBase) -> int:
        if not isinstance(base, COSInteger):
            raise OSError(f"Expected COSInteger, got {type(base).__name__}")
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNumberTreeNode:
        return _IntNumberTreeNode(dic)


# ---------- raw COS builders (full control over /Limits) ----------


def _name_leaf(
    pairs: list[tuple[str, str]],
    *,
    limits: tuple[str, str] | None = None,
    no_limits: bool = False,
) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for k, v in pairs:
        arr.add(COSString(k))
        arr.add(COSString(v))
    d.set_item(_NAMES, arr)
    if not no_limits:
        lo, hi = limits if limits is not None else (pairs[0][0], pairs[-1][0])
        lim = COSArray()
        lim.add(COSString(lo))
        lim.add(COSString(hi))
        d.set_item(_LIMITS, lim)
    return d


def _num_leaf(
    pairs: list[tuple[int, str]],
    *,
    limits: tuple[int, int] | None = None,
    no_limits: bool = False,
) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for k, v in pairs:
        arr.add(COSInteger.get(k))
        arr.add(COSInteger.get(int(v)))
    d.set_item(_NUMS, arr)
    if not no_limits:
        lo, hi = limits if limits is not None else (pairs[0][0], pairs[-1][0])
        lim = COSArray()
        lim.add(COSInteger.get(lo))
        lim.add(COSInteger.get(hi))
        d.set_item(_LIMITS, lim)
    return d


def _kids(*children: COSDictionary) -> COSDictionary:
    d = COSDictionary()
    arr = COSArray()
    for c in children:
        arr.add(c)
    d.set_item(_KIDS, arr)
    return d


def _name_tree(d: COSDictionary) -> PDStringNameTreeNode:
    return PDStringNameTreeNode(d)


def _num_tree(d: COSDictionary) -> _IntNumberTreeNode:
    return _IntNumberTreeNode(d)


# =================== NAME TREE: flat /Names leaf ===================


def test_name_flat_leaf_exact_hit() -> None:
    t = _name_tree(_name_leaf([("alpha", "1"), ("kappa", "2"), ("omega", "3")]))
    assert t.get_value("alpha") == "1"
    assert t.get_value("kappa") == "2"
    assert t.get_value("omega") == "3"


def test_name_flat_leaf_miss() -> None:
    t = _name_tree(_name_leaf([("alpha", "1"), ("omega", "3")]))
    assert t.get_value("beta") is None
    assert t.get_value("zzzzz") is None
    assert t.get_value("") is None


def test_name_flat_leaf_ordering_is_byte_lexicographic() -> None:
    # Uppercase sorts BEFORE lowercase by code point (Java compareTo agrees on
    # ASCII). Keys are stored sorted; lookup is exact so every present key hits.
    t = _name_tree(_name_leaf([("Apple", "u"), ("apple", "l"), ("banana", "b")]))
    assert t.get_value("Apple") == "u"
    assert t.get_value("apple") == "l"
    assert t.get_value("banana") == "b"
    # case-distinct miss
    assert t.get_value("APPLE") is None


def test_name_get_names_returns_full_own_map() -> None:
    t = _name_tree(_name_leaf([("a", "1"), ("b", "2"), ("c", "3")]))
    assert t.get_names() == {"a": "1", "b": "2", "c": "3"}


def test_name_get_kids_none_on_leaf() -> None:
    t = _name_tree(_name_leaf([("a", "1")]))
    assert t.get_kids() is None
    assert t.is_leaf_node()


def test_name_limit_accessors_on_leaf() -> None:
    t = _name_tree(_name_leaf([("a", "1"), ("z", "2")]))
    assert t.get_lower_limit() == "a"
    assert t.get_upper_limit() == "z"


# =================== NAME TREE: /Kids descent ===================


def _name_two_kid_tree() -> PDStringNameTreeNode:
    # first kid covers [key0..key3]; second covers [key5..key9]
    first = _name_leaf([("key0", "v0"), ("key3", "v3")])
    second = _name_leaf([("key5", "v5"), ("key9", "v9")])
    return _name_tree(_kids(first, second))


def test_name_descent_key_in_first_kid() -> None:
    assert _name_two_kid_tree().get_value("key0") == "v0"
    assert _name_two_kid_tree().get_value("key3") == "v3"


def test_name_descent_key_in_last_kid() -> None:
    assert _name_two_kid_tree().get_value("key5") == "v5"
    assert _name_two_kid_tree().get_value("key9") == "v9"


def test_name_descent_key_between_kids_is_none() -> None:
    # key4 falls in the gap [key3..key5] — no kid's /Limits cover it.
    assert _name_two_kid_tree().get_value("key4") is None


def test_name_descent_key_below_all_limits_is_none() -> None:
    assert _name_two_kid_tree().get_value("AAA") is None


def test_name_descent_key_above_all_limits_is_none() -> None:
    assert _name_two_kid_tree().get_value("zzzzzz") is None


def test_name_get_kids_present_on_intermediate() -> None:
    t = _name_two_kid_tree()
    kids = t.get_kids()
    assert kids is not None
    assert len(kids) == 2
    assert kids[0].get_lower_limit() == "key0"
    assert kids[1].get_upper_limit() == "key9"


def test_name_get_names_none_on_intermediate_node() -> None:
    # upstream getNames() is NON-recursive: an intermediate (kids-only) node
    # returns null, not a flattened map.
    assert _name_two_kid_tree().get_names() is None


# =================== NAME TREE: /Limits boundary inclusivity ===================


def test_name_boundary_key_equals_lower_limit_hits() -> None:
    # single-key leaf: lower == upper == "mid"
    t = _name_tree(_kids(_name_leaf([("mid", "vm")], limits=("mid", "mid"))))
    assert t.get_value("mid") == "vm"


def test_name_boundary_key_equals_upper_limit_hits() -> None:
    t = _name_tree(_kids(_name_leaf([("a", "va"), ("m", "vm")], limits=("a", "m"))))
    assert t.get_value("m") == "vm"
    assert t.get_value("a") == "va"


def test_name_boundary_just_outside_limits_is_none() -> None:
    # "n" > upper "m": not covered, and the key isn't present anyway.
    t = _name_tree(_kids(_name_leaf([("a", "va"), ("m", "vm")], limits=("a", "m"))))
    assert t.get_value("n") is None


# =================== NAME TREE: misordered / overlapping ===================


def test_name_descent_misordered_kids_still_found() -> None:
    # leaf holding key5 listed SECOND, after a higher-sorting leaf.
    t = _name_tree(
        _kids(
            _name_leaf([("zzz", "vz")]),
            _name_leaf([("key0", "v0"), ("key5", "v5")]),
        )
    )
    assert t.get_value("key5") == "v5"
    assert t.get_value("zzz") == "vz"


def test_name_overlapping_limits_recovers_sibling_value_d1() -> None:
    # D1: first kid's /Limits falsely claim key0..zzz (so descent enters it) but
    # it only holds key0; key5 lives in the second kid. UPSTREAM early-returns
    # the first kid's null and LOSES key5; pypdfbox falls through and RECOVERS
    # it. Asserting the pypdfbox-side (more robust) behaviour, which is the
    # documented divergence pinned in the wave-1549 live oracle + CHANGES.md.
    t = _name_tree(
        _kids(
            _name_leaf([("key0", "v0")], limits=("key0", "zzz")),
            _name_leaf([("key5", "v5")]),
        )
    )
    assert t.get_value("key0") == "v0"
    assert t.get_value("key5") == "v5"  # upstream would yield None here


# =================== NAME TREE: empty / set round-trip ===================


def test_name_empty_tree_returns_none() -> None:
    t = _name_tree(COSDictionary())
    assert t.get_value("anything") is None
    assert t.get_names() is None
    assert t.get_kids() is None


def test_name_set_names_round_trip_sorted() -> None:
    t = _name_tree(COSDictionary())
    t.set_names({"gamma": "3", "alpha": "1", "beta": "2"})
    assert t.get_names() == {"alpha": "1", "beta": "2", "gamma": "3"}
    assert t.get_value("alpha") == "1"
    assert t.get_value("gamma") == "3"
    # stored sorted by key
    arr = t.get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(arr, COSArray)
    keys = [arr.get_object(i).get_string() for i in range(0, arr.size(), 2)]
    assert keys == ["alpha", "beta", "gamma"]


def test_name_set_names_none_clears() -> None:
    t = _name_tree(_name_leaf([("a", "1")]))
    t.set_names(None)
    assert t.get_names() is None
    assert not t.get_cos_object().contains_key(_NAMES)
    assert not t.get_cos_object().contains_key(_LIMITS)


def test_name_lower_upper_limit_setter_round_trip() -> None:
    t = _name_tree(COSDictionary())
    t.set_lower_limit("aardvark")
    t.set_upper_limit("zebra")
    assert t.get_lower_limit() == "aardvark"
    assert t.get_upper_limit() == "zebra"


# =================== NUMBER TREE ===================


def test_num_flat_leaf_via_nums() -> None:
    t = _num_tree(_num_leaf([(0, "0"), (5, "5"), (50, "50")]))
    assert t.get_value(0) == 0
    assert t.get_value(5) == 5
    assert t.get_value(50) == 50


def test_num_flat_leaf_miss() -> None:
    t = _num_tree(_num_leaf([(0, "0"), (50, "50")]))
    assert t.get_value(7) is None
    assert t.get_value(-100) is None
    assert t.get_value(1000) is None


def test_num_get_numbers_full_map() -> None:
    t = _num_tree(_num_leaf([(0, "0"), (5, "5"), (50, "50")]))
    assert t.get_numbers() == {0: 0, 5: 5, 50: 50}


def test_num_get_number_alias() -> None:
    t = _num_tree(_num_leaf([(5, "5")]))
    assert t.get_number(5) == 5
    assert t.get_number(6) is None


def test_num_negative_keys() -> None:
    t = _num_tree(_num_leaf([(-100, "1"), (0, "2"), (5, "3")]))
    assert t.get_value(-100) == 1
    assert t.get_value(0) == 2
    assert t.get_value(-50) is None


def test_num_descent_two_kids() -> None:
    t = _num_tree(
        _num_tree(_kids(_num_leaf([(0, "0"), (5, "5")]), _num_leaf([(50, "50")])))
        .get_cos_object()
    )
    assert t.get_value(0) == 0
    assert t.get_value(5) == 5
    assert t.get_value(50) == 50
    assert t.get_value(7) is None
    assert t.get_value(1000) is None


def test_num_boundary_key_equals_limits() -> None:
    t = _num_tree(_kids(_num_leaf([(10, "1"), (20, "2")], limits=(10, 20))))
    assert t.get_value(10) == 1  # lower bound
    assert t.get_value(20) == 2  # upper bound
    assert t.get_value(21) is None
    assert t.get_value(9) is None


def test_num_single_key_leaf_lo_equals_hi() -> None:
    t = _num_tree(_kids(_num_leaf([(5, "5")], limits=(5, 5))))
    assert t.get_value(5) == 5
    assert t.get_value(4) is None
    assert t.get_value(6) is None


def test_num_overlapping_limits_falls_through_to_sibling() -> None:
    # Unlike the NAME tree (D1), upstream's number-tree getValue loops while the
    # result is null, so a sibling holding the key IS reached on BOTH sides.
    t = _num_tree(
        _kids(
            _num_leaf([(0, "0")], limits=(0, 50)),
            _num_leaf([(5, "5")]),
        )
    )
    assert t.get_value(0) == 0
    assert t.get_value(5) == 5


def test_num_misordered_kids_still_found() -> None:
    t = _num_tree(
        _kids(
            _num_leaf([(50, "50")]),
            _num_leaf([(0, "0"), (5, "5")]),
        )
    )
    assert t.get_value(5) == 5
    assert t.get_value(50) == 50


def test_num_empty_tree_returns_none() -> None:
    t = _num_tree(COSDictionary())
    assert t.get_value(0) is None
    assert t.get_numbers() is None
    assert t.get_kids() is None


def test_num_set_numbers_round_trip_sorted() -> None:
    t = _num_tree(COSDictionary())
    t.set_numbers({30: 3, 10: 1, 20: 2})
    assert t.get_numbers() == {10: 1, 20: 2, 30: 3}
    assert t.get_value(10) == 1
    arr = t.get_cos_object().get_dictionary_object(_NUMS)
    assert isinstance(arr, COSArray)
    keys = [int(arr.get_object(i).value) for i in range(0, arr.size(), 2)]
    assert keys == [10, 20, 30]


def test_num_set_numbers_none_clears() -> None:
    t = _num_tree(_num_leaf([(1, "1")]))
    t.set_numbers(None)
    assert t.get_numbers() is None
    assert not t.get_cos_object().contains_key(_NUMS)
    assert not t.get_cos_object().contains_key(_LIMITS)


def test_num_limit_setters_round_trip() -> None:
    t = _num_tree(COSDictionary())
    t.set_lower_limit(-5)
    t.set_upper_limit(99)
    assert t.get_lower_limit() == -5
    assert t.get_upper_limit() == 99


def test_num_get_numbers_recursive_across_kids() -> None:
    # NUMBER-tree get_numbers DOES flatten across /Kids (diverges from the name
    # tree's non-recursive get_names) — mirrors upstream PDNumberTreeNode.
    t = _num_tree(_kids(_num_leaf([(0, "0"), (5, "5")]), _num_leaf([(50, "50")])))
    assert t.get_numbers() == {0: 0, 5: 5, 50: 50}


def test_num_contains_rejects_bool() -> None:
    t = _num_tree(_num_leaf([(1, "1")]))
    assert 1 in t
    assert True not in t  # bool is an int subclass but not a valid key


@pytest.mark.parametrize(
    ("key", "expected"),
    [(0, 0), (5, 5), (50, 50), (7, None), (-1, None), (51, None)],
)
def test_num_sweep_parametrised(key: int, expected: int | None) -> None:
    t = _num_tree(_num_leaf([(0, "0"), (5, "5"), (50, "50")]))
    assert t.get_value(key) == expected
