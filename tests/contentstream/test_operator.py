from __future__ import annotations

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
