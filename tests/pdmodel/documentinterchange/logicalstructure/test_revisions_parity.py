from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


# ---------- empty / clear ----------


def test_is_empty_on_fresh_instance() -> None:
    revs: Revisions[COSName] = Revisions()
    assert revs.is_empty()
    assert revs.size() == 0
    assert len(revs) == 0


def test_is_empty_after_add_then_clear() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("H1"), 0)
    revs.add_object(_name("H2"), 1)
    assert not revs.is_empty()
    assert revs.size() == 2

    revs.clear()
    assert revs.is_empty()
    assert revs.size() == 0
    assert revs.to_cos_array().size() == 0


# ---------- contains / index_of ----------


def test_contains_and_index_of_round_trip() -> None:
    revs: Revisions[COSName] = Revisions()
    h1 = _name("H1")
    h2 = _name("H2")
    revs.add_object(h1, 0)
    revs.add_object(h2, 2)

    assert revs.contains(h1)
    assert revs.contains(h2)
    assert revs.index_of(h1) == 0
    assert revs.index_of(h2) == 1


def test_index_of_returns_minus_one_when_missing() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("H1"), 0)
    assert not revs.contains(_name("Span"))
    assert revs.index_of(_name("Span")) == -1


# ---------- setters ----------


def test_set_object_at_replaces_value_keeps_revision() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("H1"), 3)
    revs.set_object_at(0, _name("H2"))
    assert revs.get_object_at(0) == _name("H2")
    assert revs.get_revision_number_at(0) == 3


def test_set_revision_number_at_replaces_revision_keeps_value() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("P"), 0)
    revs.set_revision_number_at(0, 5)
    assert revs.get_revision_number_at(0) == 5
    assert revs.get_object_at(0) == _name("P")


def test_set_object_at_out_of_range_raises() -> None:
    revs: Revisions[COSName] = Revisions()
    with pytest.raises(IndexError):
        revs.set_object_at(0, _name("X"))


def test_set_revision_number_at_negative_raises() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("P"), 0)
    with pytest.raises(ValueError):
        revs.set_revision_number_at(0, -1)


# ---------- set_revision_number (object-based, upstream parity) ----------


def test_set_revision_number_finds_object_and_updates() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("A"), 1)
    revs.add_object(_name("B"), 2)
    revs.add_object(_name("C"), 3)

    revs.set_revision_number(_name("B"), 99)
    assert revs.get_revision_number_at(0) == 1
    assert revs.get_revision_number_at(1) == 99
    assert revs.get_revision_number_at(2) == 3
    # Values themselves untouched.
    assert revs.get_object_at(1) == _name("B")


def test_set_revision_number_missing_value_is_noop() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("A"), 5)
    # Upstream uses `if (index > -1)` — silently does nothing when the
    # object isn't found. We mirror that.
    revs.set_revision_number(_name("Missing"), 99)
    assert revs.get_revision_number_at(0) == 5


def test_set_revision_number_on_empty_collection_is_noop() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.set_revision_number(_name("X"), 7)  # must not raise
    assert revs.is_empty()


def test_set_revision_number_negative_rejected() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("X"), 0)
    with pytest.raises(ValueError):
        revs.set_revision_number(_name("X"), -1)


def test_set_revision_number_zero_is_accepted() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("X"), 5)
    revs.set_revision_number(_name("X"), 0)
    assert revs.get_revision_number_at(0) == 0


def test_set_revision_number_negative_rejected_even_when_missing() -> None:
    # Validation happens before the index lookup so the failure mode is
    # consistent regardless of presence.
    revs: Revisions[COSName] = Revisions()
    with pytest.raises(ValueError):
        revs.set_revision_number(_name("Absent"), -1)


# ---------- get_revision_number (object-based) ----------


def test_get_revision_number_returns_paired_revision() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("A"), 7)
    revs.add_object(_name("B"), 11)
    assert revs.get_revision_number(_name("A")) == 7
    assert revs.get_revision_number(_name("B")) == 11


def test_get_revision_number_returns_minus_one_when_missing() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("A"), 7)
    assert revs.get_revision_number(_name("Missing")) == -1


def test_get_revision_number_on_empty_returns_minus_one() -> None:
    revs: Revisions[COSName] = Revisions()
    assert revs.get_revision_number(_name("X")) == -1


def test_get_revision_number_zero_is_distinguishable_from_missing() -> None:
    # Zero is a real revision; -1 is the "not found" sentinel. The two
    # must not collide.
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("Zero"), 0)
    assert revs.get_revision_number(_name("Zero")) == 0
    assert revs.get_revision_number(_name("Missing")) == -1


# ---------- add_object validation ----------


def test_add_object_rejects_negative_revision() -> None:
    # Symmetric with set_revision_number_at: negative revisions are
    # invalid PDF state and must be rejected at the entry-point.
    revs: Revisions[COSName] = Revisions()
    with pytest.raises(ValueError):
        revs.add_object(_name("X"), -1)


def test_add_object_zero_revision_is_default() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("X"))
    assert revs.size() == 1
    assert revs.get_revision_number_at(0) == 0


def test_add_object_negative_does_not_corrupt_array() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("Good"), 3)
    with pytest.raises(ValueError):
        revs.add_object(_name("Bad"), -2)
    # The good entry is still there and the bad entry didn't land.
    assert revs.size() == 1
    assert revs.get_object_at(0) == _name("Good")
    assert revs.to_cos_array().size() == 2


# ---------- iterator ----------


def test_iterator_yields_entries_in_order() -> None:
    revs: Revisions[COSName] = Revisions()
    items = [_name("A"), _name("B"), _name("C")]
    for i, item in enumerate(items):
        revs.add_object(item, i)

    assert list(revs.iterator()) == items
    assert list(revs) == items


# ---------- remove_at ----------


def test_remove_at_returns_removed_object() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("A"), 0)
    revs.add_object(_name("B"), 1)
    revs.add_object(_name("C"), 2)

    removed = revs.remove_at(1)
    assert removed == _name("B")
    assert revs.size() == 2
    assert revs.get_object_at(0) == _name("A")
    assert revs.get_revision_number_at(0) == 0
    assert revs.get_object_at(1) == _name("C")
    assert revs.get_revision_number_at(1) == 2


def test_remove_at_out_of_range_raises() -> None:
    revs: Revisions[COSName] = Revisions()
    with pytest.raises(IndexError):
        revs.remove_at(0)


# ---------- from_cos_array ----------


def test_from_cos_array_round_trip() -> None:
    src = Revisions[COSName]()
    src.add_object(_name("H1"), 0)
    src.add_object(_name("H2"), 4)

    backing: COSArray = src.to_cos_array()
    parsed = Revisions.from_cos_array(backing)
    assert parsed.size() == 2
    assert parsed.get_object_at(0) == _name("H1")
    assert parsed.get_revision_number_at(0) == 0
    assert parsed.get_object_at(1) == _name("H2")
    assert parsed.get_revision_number_at(1) == 4
    assert parsed.to_cos_array() is backing
