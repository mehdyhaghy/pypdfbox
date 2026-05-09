from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_default_attribute_object import (
    PDDefaultAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions
from pypdfbox.pdmodel.documentinterchange.taggedpdf import PDUserAttributeObject


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_get_revision_number_at_returns_zero_for_non_integer_revision_slot() -> None:
    backing = COSArray([_name("First"), _name("NotARevision")])
    revs: Revisions[COSName] = Revisions(backing)
    revs._revision_offset = lambda _index: 1  # type: ignore[method-assign]

    assert revs.get_revision_number_at(0) == 0


def test_set_revision_number_at_out_of_range_raises_wave767() -> None:
    revs: Revisions[COSName] = Revisions()

    with pytest.raises(IndexError):
        revs.set_revision_number_at(0, 1)


def test_repr_lists_objects_and_revision_numbers_wave767() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("P"), 0)
    revs.add_object(_name("Span"), 3)

    assert repr(revs) == (
        "{object=/P, revisionNumber=0; object=/Span, revisionNumber=3}"
    )


def test_get_object_at_out_of_range_raises_from_entry_offset_wave767() -> None:
    revs: Revisions[COSName] = Revisions()
    revs.add_object(_name("P"))

    with pytest.raises(IndexError):
        revs.get_object_at(1)


def test_create_dispatches_user_properties_owner_wave767() -> None:
    dictionary = COSDictionary()
    dictionary.set_name(COSName.get_pdf_name("O"), PDUserAttributeObject.OWNER)

    attribute = PDAttributeObject.create(dictionary)

    assert isinstance(attribute, PDUserAttributeObject)
    assert attribute.get_cos_object() is dictionary


def test_array_to_string_rejects_non_iterable_wave767() -> None:
    with pytest.raises(TypeError, match="int"):
        PDAttributeObject.array_to_string(7)


def test_potentially_notify_changed_returns_for_both_missing_wave767() -> None:
    obj = PDDefaultAttributeObject()

    obj._potentially_notify_changed(None, None)


def test_potentially_notify_changed_returns_for_equal_values_wave767() -> None:
    obj = PDDefaultAttributeObject()

    obj._potentially_notify_changed(COSInteger.get(8), COSInteger.get(8))


def test_object_reference_returns_none_when_annotation_dispatch_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation

    def raise_value_error(_dictionary: object) -> PDAnnotation:
        raise ValueError("bad annotation")

    monkeypatch.setattr(PDAnnotation, "create", staticmethod(raise_value_error))
    objr = PDObjectReference()
    target = COSDictionary()
    target.set_name(COSName.TYPE, "Annot")
    objr.set_obj(target)

    assert objr.get_referenced_object() is None
