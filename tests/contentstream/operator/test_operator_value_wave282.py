from __future__ import annotations

from pypdfbox.contentstream.operator import Operator, OperatorName
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.graphics.concatenate_matrix import (
    ConcatenateMatrix,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSBase, COSDictionary, COSInteger, COSName


def test_inline_image_name_predicate_matches_instance_alias() -> None:
    assert Operator.is_inline_image_operator_name("BI") is True
    assert Operator.is_inline_image_operator_name("ID") is True
    assert Operator.is_inline_image_operator_name("EI") is False
    assert Operator("BI").is_inline_image() is True
    assert Operator("ID").is_inline_image_operator() is True
    assert Operator("Tj").is_inline_image() is False


def test_operator_clear_helpers_reset_optional_payloads() -> None:
    op = Operator("BI")
    op.set_operands([COSInteger.get(1)])
    op.set_image_data(b"")
    op.set_image_parameters(COSDictionary())

    assert op.has_operands() is True
    assert op.has_image_data() is True
    assert op.has_image_parameters() is True

    op.clear_operands()
    op.clear_image_data()
    op.clear_image_parameters()

    assert op.get_operands() == []
    assert op.has_image_data() is False
    assert op.has_image_parameters() is False


def test_operator_len_matches_operator_name_length() -> None:
    assert len(Operator("Tj")) == 2
    assert len(Operator("BMC")) == 3
    assert len(Operator("'")) == 1


def test_non_stroking_color_space_predicates_match_stroking_surface() -> None:
    name = COSName.get_pdf_name("DeviceRGB")
    operands: list[COSBase] = [name]

    assert SetNonStrokingColorSpace.is_color_space_name(operands) is True
    assert SetNonStrokingColorSpace.get_color_space_name(operands) is name
    assert SetNonStrokingColorSpace.is_color_space_name([]) is False
    assert SetNonStrokingColorSpace.get_color_space_name([COSInteger.get(1)]) is None


def test_registry_accepts_engine_bound_handler_family() -> None:
    handler = OperatorRegistry().lookup(OperatorName.CONCAT)

    assert isinstance(handler, ConcatenateMatrix)
