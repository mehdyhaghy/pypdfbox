"""Round-out tests for the lenient :class:`BeginMarkedContentWithProps`
(``BDC``) — wave 1367.

The lenient ``BDC`` variant lives at
``pypdfbox.contentstream.operator.markedcontent.begin_marked_content_with_props``
(while the strict ``BeginMarkedContentSequenceWithProperties`` lives in
``..begin_marked_content_sequence_with_properties``). Both are dispatched
under the same operator token, but the lenient one preserves operands of
the wrong shape via ``None`` instead of raising — the original tests
cover the happy paths, this file pins down the edge / defensive paths
flagged in wave 1367's scoping notes.
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


def test_process_with_non_name_tag_passes_none_tag() -> None:
    """Lenient: a string in the tag slot is tolerated by passing ``None``
    rather than raising. The strict variant returns silently instead."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("BDC"),
        [COSString("not-a-name"), COSDictionary()],
    )
    # Hook still fires; tag is None.
    assert len(engine.calls) == 1
    tag, props = engine.calls[0]
    assert tag is None
    # The dict was inline so it should still resolve.
    assert isinstance(props, COSDictionary)


def test_process_with_non_name_non_dict_property_operand_passes_none() -> None:
    """A string in the properties slot resolves to ``None`` — neither
    inline dict nor named property-list lookup applies."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"), [tag, COSString("oops")]
    )
    assert engine.calls == [(tag, None)]


def test_process_with_integer_property_operand_passes_none() -> None:
    """Integers in the properties slot are also tolerated (resolve to
    ``None``)."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"), [tag, COSInteger.get(5)]
    )
    assert engine.calls == [(tag, None)]


def test_process_with_named_property_no_engine_resources_passes_none() -> None:
    """No resources on the engine context → named lookup yields None."""
    engine = _Spy()  # no resources
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"),
        [tag, COSName.get_pdf_name("MyProps")],
    )
    assert len(engine.calls) == 1
    seen_tag, seen_props = engine.calls[0]
    assert seen_tag is tag
    # Resources are absent — resolution returns None.
    assert seen_props is None


def test_process_engine_without_hook_is_silent() -> None:
    """Bare engine without ``begin_marked_content_sequence`` is tolerated."""
    engine = PDFStreamEngine()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("Span"), COSDictionary()],
    )


def test_process_empty_operands_passes_none_tag_and_props() -> None:
    """Zero operands: tag → ``None``, props → ``None``, hook still fires."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    p.process(Operator.get_operator("BDC"), [])
    assert engine.calls == [(None, None)]


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


def test_process_with_only_tag_works_engine_hook_receives_none_props() -> None:
    """``BDC`` upstream requires both operands; the lenient variant
    still fires the hook with ``properties=None`` when only the tag is
    present."""
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(Operator.get_operator("BDC"), [tag])
    assert engine.calls == [(tag, None)]


def test_lenient_variant_is_distinct_from_strict_variant() -> None:
    """The lenient and strict BDC variants are different classes with
    different policy on malformed input. They live at distinct module
    paths."""
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
