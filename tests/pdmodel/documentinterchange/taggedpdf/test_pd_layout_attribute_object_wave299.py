from __future__ import annotations

from pypdfbox.cos import COSInteger
from pypdfbox.pdmodel.documentinterchange.taggedpdf import PDLayoutAttributeObject


def test_set_all_column_gaps_writes_scalar_column_gap() -> None:
    obj = PDLayoutAttributeObject()

    obj.set_all_column_gaps(12)

    assert obj.get_column_gap() == 12.0
    raw = obj.get_cos_object().get_dictionary_object("ColumnGap")
    assert isinstance(raw, COSInteger)


def test_set_all_column_gaps_none_removes_column_gap() -> None:
    obj = PDLayoutAttributeObject()
    obj.set_column_gaps([6.0, 8.0])

    obj.set_all_column_gaps(None)

    assert obj.get_cos_object().get_dictionary_object("ColumnGap") is None
    assert obj.get_column_gap() is None
