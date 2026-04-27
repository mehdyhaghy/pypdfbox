from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import AppendRectangle
from pypdfbox.contentstream.operator.path.append_rectangle import (
    AppendRectangle as AppendRectangleDirect,
)
from pypdfbox.cos import COSFloat


def test_class_attribute_operator_name() -> None:
    assert AppendRectangle.OPERATOR_NAME == "re"


def test_get_name_returns_re() -> None:
    assert AppendRectangle().get_name() == "re"


def test_re_export_matches_module_class() -> None:
    assert AppendRectangle is AppendRectangleDirect


def test_process_with_four_operands_is_noop() -> None:
    """``re`` consumes four numbers (x y width height)."""
    AppendRectangle().process(
        Operator.get_operator("re"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(100.0), COSFloat(50.0)],
    )


def test_process_accepts_empty_operands_list() -> None:
    AppendRectangle().process(Operator.get_operator("re"), [])
