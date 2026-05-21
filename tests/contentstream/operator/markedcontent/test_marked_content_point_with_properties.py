"""Hand-written tests for ``MarkedContentPointWithProperties`` — wave 1365.

This is the strict ``DP`` variant that raises ``MissingOperandException`` on
fewer than two operands. The lenient sibling
``DefineMarkedContentPointWithProps`` (also bound to ``DP``) is exercised
elsewhere — this file is targeted at the upstream-faithful class.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.markedcontent import (
    MarkedContentPointWithProperties,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_resources import PDResources


class _Spy(PDFStreamEngine):
    def __init__(self, resources: PDResources | None = None) -> None:
        super().__init__()
        if resources is not None:
            self._resources = resources
        self.calls: list[tuple[COSName, COSDictionary]] = []

    def marked_content_point(  # type: ignore[override]
        self, tag: COSName, properties: COSDictionary
    ) -> None:
        self.calls.append((tag, properties))


def test_get_name() -> None:
    assert MarkedContentPointWithProperties().get_name() == "DP"


def test_operator_name_constant() -> None:
    assert MarkedContentPointWithProperties.OPERATOR_NAME == "DP"


def test_process_missing_operand_raises() -> None:
    op = MarkedContentPointWithProperties()
    with pytest.raises(MissingOperandException):
        op.process(Operator.get_operator("DP"), [])


def test_process_one_operand_raises() -> None:
    op = MarkedContentPointWithProperties()
    with pytest.raises(MissingOperandException):
        op.process(
            Operator.get_operator("DP"), [COSName.get_pdf_name("Tag")]
        )


def test_process_non_name_first_operand_is_no_op() -> None:
    engine = _Spy()
    op = MarkedContentPointWithProperties()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("DP"),
        [COSString("oops"), COSDictionary()],
    )
    assert engine.calls == []


def test_process_without_context_is_no_op() -> None:
    op = MarkedContentPointWithProperties()
    # No exception; falls out after the context check.
    op.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Tag"), COSDictionary()],
    )


def test_process_inline_dict_calls_hook() -> None:
    engine = _Spy()
    op = MarkedContentPointWithProperties()
    engine.add_operator(op)
    tag = COSName.get_pdf_name("Tag")
    props = COSDictionary()
    props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(3))
    op.process(Operator.get_operator("DP"), [tag, props])
    assert engine.calls == [(tag, props)]


def test_process_named_property_resolves_via_resources() -> None:
    res = PDResources()
    cos_props = COSDictionary()
    cos_props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(11))
    name = COSName.get_pdf_name("MyProps")
    res.put(COSName.get_pdf_name("Properties"), name, cos_props)

    engine = _Spy(resources=res)
    op = MarkedContentPointWithProperties()
    engine.add_operator(op)
    tag = COSName.get_pdf_name("Marker")
    op.process(Operator.get_operator("DP"), [tag, name])
    assert len(engine.calls) == 1
    seen_tag, seen_props = engine.calls[0]
    assert seen_tag is tag
    assert seen_props.get_int(COSName.get_pdf_name("MCID")) == 11


def test_process_unresolved_named_property_skips_hook() -> None:
    res = PDResources()
    engine = _Spy(resources=res)
    op = MarkedContentPointWithProperties()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Tag"), COSName.get_pdf_name("Missing")],
    )
    # No property dict resolved → hook never invoked (strict variant).
    assert engine.calls == []


def test_process_neither_dict_nor_name_skips() -> None:
    engine = _Spy()
    op = MarkedContentPointWithProperties()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Tag"), COSInteger.get(7)],
    )
    assert engine.calls == []


def test_constructor_accepts_engine_context() -> None:
    engine = _Spy()
    op = MarkedContentPointWithProperties(engine)
    assert op.get_context() is engine
