from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSObjectKey,
)
from pypdfbox.cos.pd_linearization_dictionary import PDLinearizationDictionary


def _make_lin_dict(
    *,
    linearized: int | float | None = 1,
    length: int = 12345,
    hint: list[int] | None = None,
    first_page_obj: int = 7,
    end_first_page: int = 5678,
    pages: int = 10,
    first_xref: int = 999,
) -> COSDictionary:
    d = COSDictionary()
    if linearized is not None:
        if isinstance(linearized, float):
            d.set_item(COSName.get_pdf_name("Linearized"), COSFloat(linearized))
        else:
            d.set_int("Linearized", linearized)
    d.set_int("L", length)
    if hint is not None:
        arr = COSArray([COSInteger.get(x) for x in hint])
        d.set_item(COSName.get_pdf_name("H"), arr)
    d.set_int("O", first_page_obj)
    d.set_int("E", end_first_page)
    d.set_int("N", pages)
    d.set_int("T", first_xref)
    return d


def _attach_as_first_object(doc: COSDocument, dictionary: COSDictionary) -> COSObject:
    """Register ``dictionary`` as object (1, 0) in ``doc``'s pool."""
    key = COSObjectKey(1, 0)
    obj = doc.get_object_from_pool(key)
    obj.set_object(dictionary)
    return obj


# ---------------------------------------------------------------------------
# COSDocument.get_linearized_dictionary integration
# ---------------------------------------------------------------------------


def test_linearized_document_returns_typed_wrapper() -> None:
    with COSDocument() as doc:
        lin = _make_lin_dict(hint=[123, 456])
        _attach_as_first_object(doc, lin)
        wrapper = doc.get_linearized_dictionary()
        assert wrapper is not None
        assert isinstance(wrapper, PDLinearizationDictionary)
        assert wrapper.is_linearized()
        assert wrapper.get_linearized_version() == 1.0
        assert wrapper.get_length_of_file() == 12345
        assert wrapper.get_first_page_object_number() == 7
        assert wrapper.get_end_of_first_page() == 5678
        assert wrapper.get_number_of_pages() == 10
        assert wrapper.get_offset_of_first_xref() == 999
        assert wrapper.get_cos_object() is lin


def test_non_linearized_document_returns_none() -> None:
    with COSDocument() as doc:
        plain = COSDictionary()
        plain.set_name("Type", "Catalog")
        _attach_as_first_object(doc, plain)
        assert doc.get_linearized_dictionary() is None


def test_empty_document_returns_none() -> None:
    with COSDocument() as doc:
        assert doc.get_linearized_dictionary() is None


def test_get_linearized_dictionary_is_cached() -> None:
    with COSDocument() as doc:
        lin = _make_lin_dict(hint=[10, 20])
        _attach_as_first_object(doc, lin)
        first = doc.get_linearized_dictionary()
        second = doc.get_linearized_dictionary()
        assert first is second


def test_scans_past_non_dict_first_object() -> None:
    """Defensive scan: if obj 1 isn't a dict, the dict landing on obj 2 still wins."""
    with COSDocument() as doc:
        # obj 1: plain integer (no dict, can't be linearisation)
        obj1 = doc.get_object_from_pool(COSObjectKey(1, 0))
        obj1.set_object(COSInteger.get(42))
        # obj 2: the actual linearisation dict
        obj2 = doc.get_object_from_pool(COSObjectKey(2, 0))
        obj2.set_object(_make_lin_dict())
        wrapper = doc.get_linearized_dictionary()
        assert wrapper is not None
        assert wrapper.get_number_of_pages() == 10


# ---------------------------------------------------------------------------
# /H array shapes
# ---------------------------------------------------------------------------


def test_hint_table_two_ints() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(hint=[123, 456]))
    assert wrapper.get_hint_table() == (123, 456)


def test_hint_table_four_ints() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(hint=[123, 456, 789, 1000]))
    assert wrapper.get_hint_table() == (123, 456, 789, 1000)


def test_hint_table_missing_returns_none() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(hint=None))
    assert wrapper.get_hint_table() is None


def test_hint_table_wrong_arity_returns_none() -> None:
    d = _make_lin_dict(hint=None)
    arr = COSArray([COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)])
    d.set_item(COSName.get_pdf_name("H"), arr)
    wrapper = PDLinearizationDictionary(d)
    assert wrapper.get_hint_table() is None


def test_hint_table_non_numeric_entry_returns_none() -> None:
    d = _make_lin_dict(hint=None)
    arr = COSArray([COSInteger.get(1), COSName.get_pdf_name("Bogus")])
    d.set_item(COSName.get_pdf_name("H"), arr)
    wrapper = PDLinearizationDictionary(d)
    assert wrapper.get_hint_table() is None


# ---------------------------------------------------------------------------
# is_linearized() truthiness
# ---------------------------------------------------------------------------


def test_is_linearized_true_for_one() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(linearized=1))
    assert wrapper.is_linearized() is True


def test_is_linearized_false_for_zero() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(linearized=0))
    assert wrapper.is_linearized() is False
    # And accordingly never picked up by COSDocument's scan.
    with COSDocument() as doc:
        _attach_as_first_object(doc, _make_lin_dict(linearized=0))
        assert doc.get_linearized_dictionary() is None


def test_is_linearized_false_when_absent() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(linearized=None))
    assert wrapper.is_linearized() is False
    assert wrapper.get_linearized_version() == 0.0


def test_is_linearized_true_for_float_one() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict(linearized=1.0))
    assert wrapper.is_linearized() is True
    assert wrapper.get_linearized_version() == 1.0


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def test_constructor_rejects_non_dict() -> None:
    with pytest.raises(TypeError):
        PDLinearizationDictionary(object())  # type: ignore[arg-type]


def test_repr_shape() -> None:
    wrapper = PDLinearizationDictionary(_make_lin_dict())
    text = repr(wrapper)
    assert "PDLinearizationDictionary" in text
    assert "L=12345" in text
    assert "N=10" in text
