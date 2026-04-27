from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import LineTo
from pypdfbox.contentstream.operator.path.line_to import LineTo as LineToDirect
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert LineTo.OPERATOR_NAME == "l"


def test_get_name_returns_l() -> None:
    assert LineTo().get_name() == "l"


def test_re_export_matches_module_class() -> None:
    assert LineTo is LineToDirect


def test_process_with_two_operands_is_noop() -> None:
    LineTo().process(
        Operator.get_operator("l"),
        [COSFloat(1.5), COSFloat(2.5)],
    )


def test_process_accepts_empty_operands_list() -> None:
    LineTo().process(Operator.get_operator("l"), [])
