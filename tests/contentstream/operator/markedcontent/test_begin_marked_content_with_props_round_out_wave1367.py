"""Round-out tests for :class:`BeginMarkedContentWithProps` (``BDC``) —
wave 1367, retargeted to upstream-strict semantics in wave 1535.

The registered ``BDC`` processor lives at
``pypdfbox.contentstream.operator.markedcontent.begin_marked_content_with_props``
(a parallel ``BeginMarkedContentSequenceWithProperties`` lives in
``..begin_marked_content_sequence_with_properties``). Wave 1535's live
oracle proved upstream ``BDC`` is strict on malformed input — it raises
:class:`MissingOperandException` on operand underflow and returns
without opening a sequence when the tag is not a name or the property
list cannot be resolved. The earlier "lenient" expectations (fire the
hook with ``None``) were a divergence; this file now pins the
oracle-proven behavior.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import OperatorProcessor
from pypdfbox.contentstream.operator.markedcontent import (
    BeginMarkedContentWithProps,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_resources import PDResources


class _Spy(PDFStreamEngine):
    def __init__(self, resources: PDResources | None = None) -> None:
        super().__init__()
        if resources is not None:
            self._resources = resources
        self.calls: list[tuple[COSName | None, COSDictionary | None]] = []

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.calls.append((tag, properties))


def test_subclass_relationship() -> None:
    assert issubclass(BeginMarkedContentWithProps, OperatorProcessor)


def test_operator_name_constant_and_get_name_match() -> None:
    assert BeginMarkedContentWithProps.OPERATOR_NAME == "BDC"
    assert BeginMarkedContentWithProps().get_name() == "BDC"
    assert BeginMarkedContentWithProps().name == "BDC"


def test_process_with_non_name_tag_returns_silently() -> None:
    """Wave-1535 oracle: a non-name in the tag slot makes BDC return
    without opening a sequence (upstream ``if (!(operands.get(0)
    instanceof COSName)) return;``)."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("BDC"),
        [COSString("not-a-name"), COSDictionary()],
    )
    assert engine.calls == []


def test_process_with_non_name_non_dict_property_operand_does_not_fire() -> None:
    """Wave-1535 oracle: a string in the properties slot resolves to None,
    so BDC returns without opening a sequence."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"), [tag, COSString("oops")]
    )
    assert engine.calls == []


def test_process_with_integer_property_operand_does_not_fire() -> None:
    """Wave-1535 oracle: an integer in the properties slot resolves to
    None → no sequence opened."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"), [tag, COSInteger.get(5)]
    )
    assert engine.calls == []


def test_process_with_named_property_no_engine_resources_does_not_fire() -> None:
    """Wave-1535 oracle: no resources → named lookup yields None → BDC
    returns without opening a sequence."""
    engine = _Spy()  # no resources
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"),
        [tag, COSName.get_pdf_name("MyProps")],
    )
    assert engine.calls == []


def test_process_engine_without_hook_is_silent() -> None:
    """Bare engine without ``begin_marked_content_sequence`` is tolerated."""
    engine = PDFStreamEngine()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("Span"), COSDictionary()],
    )


def test_process_empty_operands_raises_missing_operand() -> None:
    """Wave-1535 oracle: zero operands → MissingOperandException (the
    engine catches + continues; no sequence opens)."""
    from pypdfbox.contentstream.operator import MissingOperandException

    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("BDC"), [])
    assert engine.calls == []


def test_get_context_round_trips_engine() -> None:
    engine = _Spy()
    p = BeginMarkedContentWithProps(engine)
    assert p.get_context() is engine


def test_set_context_late_binding_works() -> None:
    """Without a context, ``get_context`` raises (strict variant); after
    ``set_context`` it returns the engine and dispatch succeeds."""
    p = BeginMarkedContentWithProps()
    with pytest.raises(RuntimeError, match="no PDFStreamEngine context"):
        p.get_context()
    engine = _Spy()
    p.set_context(engine)
    assert p.get_context() is engine
    p.process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("Span"), COSDictionary()],
    )
    assert len(engine.calls) == 1


def test_process_with_only_tag_raises_missing_operand() -> None:
    """Wave-1535 oracle: ``BDC`` requires both operands; a single operand
    raises MissingOperandException upstream (engine catches + continues)."""
    from pypdfbox.contentstream.operator import MissingOperandException

    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("BDC"), [tag])
    assert engine.calls == []


def test_lenient_variant_is_distinct_from_strict_variant() -> None:
    """The two BDC implementations are different classes living at
    distinct module paths. Since wave 1535 both follow upstream's strict
    policy on malformed input (return without opening a sequence /
    MissingOperandException on underflow); they remain separate classes
    that coexist under one upstream-faithful token."""
    from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_sequence_with_properties import (  # noqa: E501
        BeginMarkedContentSequenceWithProperties,
    )

    assert BeginMarkedContentWithProps is not BeginMarkedContentSequenceWithProperties
    # Both advertise the same operator name (``BDC``) — they coexist as
    # parallel implementations under one upstream-faithful token.
    assert (
        BeginMarkedContentWithProps.OPERATOR_NAME
        == BeginMarkedContentSequenceWithProperties.OPERATOR_NAME
        == "BDC"
    )
