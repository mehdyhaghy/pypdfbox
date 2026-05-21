"""Hand-written tests for ``BeginMarkedContentSequenceWithProperties``.

Wave 1365. The strict upstream-faithful ``BDC`` variant raises
``MissingOperandException`` on fewer than two operands and silently skips on
non-name tags / unresolved property references. The lenient sibling
``BeginMarkedContentWithProps`` is exercised elsewhere.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.markedcontent import (
    BeginMarkedContentSequenceWithProperties,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_resources import PDResources


class _Spy(PDFStreamEngine):
    def __init__(self, resources: PDResources | None = None) -> None:
        super().__init__()
        if resources is not None:
            self._resources = resources
        self.calls: list[tuple[COSName, COSDictionary]] = []

    def begin_marked_content_sequence(  # type: ignore[override]
        self, tag: COSName, properties: COSDictionary | None
    ) -> None:
        self.calls.append((tag, properties))


def test_get_name() -> None:
    assert BeginMarkedContentSequenceWithProperties().get_name() == "BDC"


def test_operator_name_constant() -> None:
    assert BeginMarkedContentSequenceWithProperties.OPERATOR_NAME == "BDC"


def test_process_no_operands_raises() -> None:
    op = BeginMarkedContentSequenceWithProperties()
    with pytest.raises(MissingOperandException):
        op.process(Operator.get_operator("BDC"), [])


def test_process_one_operand_raises() -> None:
    op = BeginMarkedContentSequenceWithProperties()
    with pytest.raises(MissingOperandException):
        op.process(
            Operator.get_operator("BDC"), [COSName.get_pdf_name("Span")]
        )


def test_process_non_name_tag_is_no_op() -> None:
    engine = _Spy()
    op = BeginMarkedContentSequenceWithProperties()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("BDC"),
        [COSString("not-a-name"), COSDictionary()],
    )
    assert engine.calls == []


def test_process_without_context_is_no_op() -> None:
    op = BeginMarkedContentSequenceWithProperties()
    op.process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("Span"), COSDictionary()],
    )


def test_process_inline_dict_calls_hook() -> None:
    engine = _Spy()
    op = BeginMarkedContentSequenceWithProperties()
    engine.add_operator(op)
    tag = COSName.get_pdf_name("Span")
    props = COSDictionary()
    props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(2))
    op.process(Operator.get_operator("BDC"), [tag, props])
    assert engine.calls == [(tag, props)]


def test_process_named_property_resolves_via_resources() -> None:
    res = PDResources()
    cos_props = COSDictionary()
    cos_props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(7))
    name = COSName.get_pdf_name("PropName")
    res.put(COSName.get_pdf_name("Properties"), name, cos_props)

    engine = _Spy(resources=res)
    op = BeginMarkedContentSequenceWithProperties()
    engine.add_operator(op)
    tag = COSName.get_pdf_name("OC")
    op.process(Operator.get_operator("BDC"), [tag, name])
    assert len(engine.calls) == 1
    seen_tag, seen_props = engine.calls[0]
    assert seen_tag is tag
    assert seen_props is not None
    assert seen_props.get_int(COSName.get_pdf_name("MCID")) == 7


def test_process_unresolved_named_property_skips_hook() -> None:
    res = PDResources()
    engine = _Spy(resources=res)
    op = BeginMarkedContentSequenceWithProperties()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("BDC"),
        [
            COSName.get_pdf_name("Span"),
            COSName.get_pdf_name("Missing"),
        ],
    )
    # Strict variant skips when the property dict cannot be resolved.
    assert engine.calls == []


def test_process_property_neither_dict_nor_name_skips() -> None:
    engine = _Spy()
    op = BeginMarkedContentSequenceWithProperties()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("Span"), COSInteger.get(0)],
    )
    assert engine.calls == []


def test_constructor_accepts_engine_context() -> None:
    engine = _Spy()
    op = BeginMarkedContentSequenceWithProperties(engine)
    assert op.get_context() is engine
