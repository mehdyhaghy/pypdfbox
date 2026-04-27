from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path import MoveTo
from pypdfbox.contentstream.operator.path.move_to import MoveTo as MoveToDirect
from pypdfbox.cos import COSFloat, COSInteger


def test_class_attribute_operator_name() -> None:
    assert MoveTo.OPERATOR_NAME == "m"


def test_get_name_returns_m() -> None:
    assert MoveTo().get_name() == "m"


def test_re_export_matches_module_class() -> None:
    assert MoveTo is MoveToDirect


def test_process_with_two_operands_is_noop() -> None:
    handler = MoveTo()
    handler.process(
        Operator.get_operator("m"),
        [COSFloat(10.0), COSFloat(20.5)],
    )


def test_process_accepts_integer_operands() -> None:
    handler = MoveTo()
    handler.process(
        Operator.get_operator("m"),
        [COSInteger.get(0), COSInteger.get(0)],
    )


def test_process_accepts_empty_operands_list() -> None:
    """Lite stub does not enforce arity; engine layer will."""
    MoveTo().process(Operator.get_operator("m"), [])
