from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_compact_cos_array_omitted_zero_revision_is_entry_wave312() -> None:
    backing = COSArray([_name("Zero"), _name("Changed"), COSInteger.get(7)])

    revs: Revisions[COSName] = Revisions(backing)

    assert revs.size() == 2
    assert revs.get_object_at(0) == _name("Zero")
    assert revs.get_revision_number_at(0) == 0
    assert revs.get_object_at(1) == _name("Changed")
    assert revs.get_revision_number_at(1) == 7


def test_set_revision_number_inserts_slot_for_compact_entry_wave312() -> None:
    backing = COSArray([_name("Zero"), _name("Next")])
    revs: Revisions[COSName] = Revisions(backing)

    revs.set_revision_number_at(0, 4)

    assert backing.size() == 3
    assert revs.get_revision_number_at(0) == 4
    assert revs.get_object_at(1) == _name("Next")
    assert revs.get_revision_number_at(1) == 0


def test_remove_at_preserves_following_compact_entry_wave312() -> None:
    backing = COSArray([_name("First"), COSInteger.get(2), _name("Second")])
    revs: Revisions[COSName] = Revisions(backing)

    removed = revs.remove_at(0)

    assert removed == _name("First")
    assert backing.size() == 1
    assert revs.size() == 1
    assert revs.get_object_at(0) == _name("Second")
    assert revs.get_revision_number_at(0) == 0
