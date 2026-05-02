from __future__ import annotations

import copy

import pytest

from pypdfbox.contentstream import Operator, OperatorName
from pypdfbox.cos import COSDictionary, COSInteger, COSName


def test_get_name_returns_operator_string() -> None:
    op = Operator.get_operator("BT")
    assert op.get_name() == "BT"
    assert op.name == "BT"


def test_repr_matches_pdfbox_format() -> None:
    op = Operator.get_operator("Tj")
    assert repr(op) == "PDFOperator{Tj}"


def test_get_operator_caches_ordinary_operators() -> None:
    a = Operator.get_operator("Tj")
    b = Operator.get_operator("Tj")
    assert a is b


def test_get_operator_distinct_names_distinct_instances() -> None:
    assert Operator.get_operator("BT") is not Operator.get_operator("ET")


def test_get_operator_inline_image_is_not_cached() -> None:
    a = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    b = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    assert a is not b
    assert a.get_name() == "BI"


def test_get_operator_inline_image_data_is_not_cached() -> None:
    a = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE_DATA)
    b = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE_DATA)
    assert a is not b
    assert a.get_name() == "ID"


def test_constructor_rejects_leading_slash() -> None:
    with pytest.raises(ValueError):
        Operator("/Bad")


def test_operands_default_empty_then_settable() -> None:
    op = Operator("re")  # constructed directly so we don't pollute the cache
    assert op.get_operands() == []
    operands = [COSInteger.get(1), COSInteger.get(2)]
    op.set_operands(operands)
    assert op.get_operands() is operands


def test_image_data_round_trip() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE_DATA)
    assert op.get_image_data() is None
    payload = b"\x00\x01\x02\x03"
    op.set_image_data(payload)
    assert op.get_image_data() is payload


def test_image_parameters_round_trip() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    assert op.get_image_parameters() is None
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(8))
    op.set_image_parameters(params)
    assert op.get_image_parameters() is params


def test_str_matches_pdfbox_to_string_format() -> None:
    # Java's ``toString()`` returns ``"PDFOperator{<name>}"`` —
    # ``str(op)`` must match (not just ``repr``).
    op = Operator.get_operator("Tj")
    assert str(op) == "PDFOperator{Tj}"


def test_operands_property_mirrors_getter() -> None:
    op = Operator("re")
    operands = [COSInteger.get(0), COSInteger.get(0), COSInteger.get(100), COSInteger.get(50)]
    op.set_operands(operands)
    assert op.operands is operands
    assert op.operands is op.get_operands()


def test_image_data_property_mirrors_getter() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE_DATA)
    assert op.image_data is None
    op.set_image_data(b"\xde\xad\xbe\xef")
    assert op.image_data == b"\xde\xad\xbe\xef"
    assert op.image_data is op.get_image_data()


def test_image_parameters_property_mirrors_getter() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    assert op.image_parameters is None
    params = COSDictionary()
    op.set_image_parameters(params)
    assert op.image_parameters is params
    assert op.image_parameters is op.get_image_parameters()


# ---------- with_operands factory ----------


def test_with_operands_returns_uncached_instance() -> None:
    """``with_operands`` must always return a fresh, mutable ``Operator``
    so callers cannot accidentally pollute the singleton cache."""
    cached = Operator.get_operator("Tj")
    fresh = Operator.with_operands("Tj", [COSInteger.get(1)])
    assert fresh is not cached
    # Cache singleton untouched: still empty operands.
    assert cached.get_operands() == []


def test_with_operands_attaches_operands() -> None:
    operands = [COSInteger.get(10), COSInteger.get(20)]
    op = Operator.with_operands("re", operands)
    assert op.get_name() == "re"
    assert op.get_operands() is operands


def test_with_operands_two_calls_yield_distinct_instances() -> None:
    a = Operator.with_operands("Tj", [COSInteger.get(1)])
    b = Operator.with_operands("Tj", [COSInteger.get(2)])
    assert a is not b
    assert a.get_operands() != b.get_operands()


def test_with_operands_rejects_leading_slash() -> None:
    with pytest.raises(ValueError):
        Operator.with_operands("/Bad", [])


def test_with_operands_works_for_inline_image_operators() -> None:
    """Inline-image operators are never cached either way; the factory
    still produces a fresh instance with operands attached."""
    op = Operator.with_operands(OperatorName.BEGIN_INLINE_IMAGE, [])
    assert op.get_name() == "BI"
    assert op.get_operands() == []


# ---------- is_cached predicate ----------


def test_is_cached_true_for_ordinary_operator() -> None:
    assert Operator.is_cached("Tj") is True
    assert Operator.is_cached("BT") is True
    assert Operator.is_cached("re") is True


def test_is_cached_false_for_inline_image_operators() -> None:
    assert Operator.is_cached(OperatorName.BEGIN_INLINE_IMAGE) is False
    assert Operator.is_cached(OperatorName.BEGIN_INLINE_IMAGE_DATA) is False
    # And the literals, just to be explicit:
    assert Operator.is_cached("BI") is False
    assert Operator.is_cached("ID") is False


def test_is_cached_matches_get_operator_behavior() -> None:
    """Predicate must match the actual caching behaviour of
    ``get_operator`` for both kinds of operators."""
    cached_name = "Tf"
    a = Operator.get_operator(cached_name)
    b = Operator.get_operator(cached_name)
    assert (a is b) is Operator.is_cached(cached_name)

    bi_a = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    bi_b = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    assert (bi_a is bi_b) is Operator.is_cached(
        OperatorName.BEGIN_INLINE_IMAGE
    )


# ---------- is_inline_image_operator predicate ----------


def test_is_inline_image_operator_true_for_bi() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    assert op.is_inline_image_operator() is True


def test_is_inline_image_operator_true_for_id() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE_DATA)
    assert op.is_inline_image_operator() is True


def test_is_inline_image_operator_false_for_ordinary_operators() -> None:
    for name in ("BT", "ET", "Tj", "TJ", "EI", "q", "Q", "re", "m", "l"):
        assert (
            Operator.get_operator(name).is_inline_image_operator() is False
        ), f"{name!r} should not be classified as an inline-image operator"


# ---------- has_operands predicate ----------


def test_has_operands_false_by_default() -> None:
    op = Operator("re")
    assert op.has_operands() is False


def test_has_operands_true_after_set_operands() -> None:
    op = Operator("re")
    op.set_operands(
        [
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(100),
            COSInteger.get(50),
        ]
    )
    assert op.has_operands() is True


def test_has_operands_false_after_clearing_to_empty_list() -> None:
    op = Operator("Tj")
    op.set_operands([COSInteger.get(1)])
    assert op.has_operands() is True
    op.set_operands([])
    assert op.has_operands() is False


# ---------- copy ----------


def test_copy_returns_distinct_instance_for_cached_operator() -> None:
    """``copy.copy`` on a cached singleton must yield a fresh, mutable
    clone — the whole point of providing copy support."""
    cached = Operator.get_operator("Tj")
    clone = copy.copy(cached)
    assert clone is not cached
    assert clone.get_name() == cached.get_name()


def test_copy_preserves_name_and_operands() -> None:
    op = Operator("re")
    op.set_operands(
        [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)]
    )
    clone = copy.copy(op)
    assert clone.get_name() == "re"
    assert clone.get_operands() == op.get_operands()


def test_copy_operands_list_is_independent() -> None:
    """Mutating the original's operand list must not bleed into the clone."""
    op = Operator("re")
    operands = [COSInteger.get(1), COSInteger.get(2)]
    op.set_operands(operands)
    clone = copy.copy(op)

    operands.append(COSInteger.get(99))
    assert len(clone.get_operands()) == 2
    assert clone.get_operands() is not op.get_operands()


def test_copy_shares_image_parameters_and_data_references() -> None:
    """The image parameters dict and image bytes are intentionally
    shared (matches Java's field-by-field copy of the references)."""
    bi = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(8))
    bi.set_image_parameters(params)
    bi.set_image_data(b"\x01\x02\x03")

    clone = copy.copy(bi)
    assert clone.get_image_parameters() is params
    assert clone.get_image_data() == b"\x01\x02\x03"


def test_copy_does_not_leak_into_cache_singleton() -> None:
    """Copying a cached operator and assigning new operands to the
    clone must leave the cache singleton's operands untouched."""
    cached = Operator.get_operator("Tj")
    # Reset to a known empty baseline so the test is independent of order.
    cached.set_operands([])

    clone = copy.copy(cached)
    clone.set_operands([COSInteger.get(7)])

    assert cached.get_operands() == []
    assert clone.get_operands() != cached.get_operands()


def test_copy_clone_is_uncached() -> None:
    """The clone must not be the same as a fresh ``get_operator`` call —
    cloning yields an *uncached* instance."""
    cached = Operator.get_operator("BT")
    clone = copy.copy(cached)
    assert clone is not cached
    assert clone is not Operator.get_operator("BT")
