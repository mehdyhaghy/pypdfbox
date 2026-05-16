"""Coverage-boost tests for ``XReferenceEntry`` abstract base.

Targets the abstract surface, the ``compare_to`` None-handling
branches, and the four rich-comparison dunders (``__lt__``, ``__le__``,
``__gt__``, ``__ge__``) including their ``NotImplemented`` returns for
non-``XReferenceEntry`` operands.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.pdfparser.xref.free_x_reference import FreeXReference
from pypdfbox.pdfparser.xref.x_reference_entry import XReferenceEntry


def _entry(num: int) -> FreeXReference:
    return FreeXReference(COSObjectKey(num, 0), 0)


# ---------------------------------------------------------------------
# Abstract surface guard
# ---------------------------------------------------------------------


def test_x_reference_entry_is_abstract() -> None:
    with pytest.raises(TypeError):
        XReferenceEntry()  # type: ignore[abstract]


# ---------------------------------------------------------------------
# compare_to — None-handling branches
# ---------------------------------------------------------------------


def test_compare_to_with_none_other_returns_one() -> None:
    a = _entry(3)
    assert a.compare_to(None) == 1


def test_compare_to_with_other_having_none_key_returns_one() -> None:
    a = _entry(1)

    class _NullKeyEntry(XReferenceEntry):
        def get_type(self):  # type: ignore[override]
            return None

        def get_referenced_key(self):  # type: ignore[override]
            return None

        def get_first_column_value(self) -> int:
            return 0

        def get_second_column_value(self) -> int:
            return 0

        def get_third_column_value(self) -> int:
            return 0

    other = _NullKeyEntry()
    assert a.compare_to(other) == 1


def test_compare_to_when_own_key_is_none_returns_minus_one() -> None:
    class _NullKeyEntry(XReferenceEntry):
        def get_type(self):  # type: ignore[override]
            return None

        def get_referenced_key(self):  # type: ignore[override]
            return None

        def get_first_column_value(self) -> int:
            return 0

        def get_second_column_value(self) -> int:
            return 0

        def get_third_column_value(self) -> int:
            return 0

    a = _NullKeyEntry()
    b = _entry(5)
    assert a.compare_to(b) == -1


def test_compare_to_orders_by_key() -> None:
    a = _entry(1)
    b = _entry(2)
    assert a.compare_to(b) < 0
    assert b.compare_to(a) > 0
    assert a.compare_to(_entry(1)) == 0


# ---------------------------------------------------------------------
# Rich comparison dunders — equal, less-than, greater-than paths
# ---------------------------------------------------------------------


def test_lt_le_gt_ge_orderings_against_xreference_entry() -> None:
    a = _entry(1)
    b = _entry(2)
    same = _entry(1)
    # __lt__
    assert a < b
    assert not (b < a)
    # __le__
    assert a <= b
    assert a <= same
    assert not (b <= a)
    # __gt__
    assert b > a
    assert not (a > b)
    # __ge__
    assert b >= a
    assert a >= same
    assert not (a >= b)


# ---------------------------------------------------------------------
# Rich comparison dunders — NotImplemented for foreign types
# ---------------------------------------------------------------------


def test_lt_returns_not_implemented_for_non_entry() -> None:
    a = _entry(1)
    assert a.__lt__(object()) is NotImplemented


def test_le_returns_not_implemented_for_non_entry() -> None:
    a = _entry(1)
    assert a.__le__("not-an-entry") is NotImplemented


def test_gt_returns_not_implemented_for_non_entry() -> None:
    a = _entry(1)
    assert a.__gt__(42) is NotImplemented


def test_ge_returns_not_implemented_for_non_entry() -> None:
    a = _entry(1)
    assert a.__ge__(None) is NotImplemented


def test_sort_uses_lt_dunder() -> None:
    entries = [_entry(3), _entry(1), _entry(2)]
    entries.sort()
    keys = [e.get_referenced_key().get_number() for e in entries]
    assert keys == [1, 2, 3]
