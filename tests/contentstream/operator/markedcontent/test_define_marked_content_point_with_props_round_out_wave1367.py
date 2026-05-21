"""Round-out tests for the lenient :class:`DefineMarkedContentPointWithProps`
(``DP``) — wave 1367.

Parallel to ``BeginMarkedContentWithProps`` but uses the
``marked_content_point`` engine hook (no balanced ``EMC``).
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import OperatorProcessor
from pypdfbox.contentstream.operator.markedcontent import (
    DefineMarkedContentPointWithProps,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.pd_resources import PDResources


class _Spy(PDFStreamEngine):
    def __init__(self, resources: PDResources | None = None) -> None:
        super().__init__()
        if resources is not None:
            self._resources = resources
        self.calls: list[tuple[COSName | None, COSDictionary | None]] = []

    def marked_content_point(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.calls.append((tag, properties))


def test_subclass_relationship() -> None:
    assert issubclass(DefineMarkedContentPointWithProps, OperatorProcessor)


def test_operator_name_constant_and_get_name_match() -> None:
    assert DefineMarkedContentPointWithProps.OPERATOR_NAME == "DP"
    assert DefineMarkedContentPointWithProps().get_name() == "DP"
    assert DefineMarkedContentPointWithProps().name == "DP"


def test_process_with_non_name_tag_passes_none() -> None:
    """Lenient: string tag → ``None``, hook still fires."""
    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("DP"),
        [COSString("not-a-name"), COSDictionary()],
    )
    assert len(engine.calls) == 1
    tag, props = engine.calls[0]
    assert tag is None
    assert isinstance(props, COSDictionary)


def test_process_with_non_dict_non_name_property_operand_passes_none() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(
        Operator.get_operator("DP"), [tag, COSString("oops")]
    )
    assert engine.calls == [(tag, None)]


def test_process_with_integer_property_operand_passes_none() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(
        Operator.get_operator("DP"), [tag, COSInteger.get(99)]
    )
    assert engine.calls == [(tag, None)]


def test_process_with_named_property_no_resources_passes_none() -> None:
    engine = _Spy()  # no resources
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(
        Operator.get_operator("DP"),
        [tag, COSName.get_pdf_name("MyProps")],
    )
    assert engine.calls == [(tag, None)]


def test_process_with_inline_dict_ignores_resources() -> None:
    """Inline COSDictionary wins over resources — even when resources
    exist with a same-named entry, the inline dict is used."""
    res = PDResources()
    cos_props = COSDictionary()
    cos_props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(7))
    res.put(
        COSName.get_pdf_name("Properties"),
        COSName.get_pdf_name("MyProps"),
        cos_props,
    )

    engine = _Spy(resources=res)
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    inline = COSDictionary()
    inline.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(1))
    p.process(Operator.get_operator("DP"), [tag, inline])

    [(seen_tag, seen_props)] = engine.calls
    assert seen_tag is tag
    assert seen_props is inline


def test_process_engine_without_hook_is_silent() -> None:
    """Bare engine without ``marked_content_point`` is tolerated."""
    engine = PDFStreamEngine()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    p.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Marker"), COSDictionary()],
    )


def test_get_context_round_trips_engine() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps(engine)
    assert p.get_context() is engine


def test_set_context_late_binding_works() -> None:
    """Without a context, ``get_context`` raises (strict variant); after
    ``set_context`` dispatch succeeds."""
    p = DefineMarkedContentPointWithProps()
    with pytest.raises(RuntimeError, match="no PDFStreamEngine context"):
        p.get_context()
    engine = _Spy()
    p.set_context(engine)
    assert p.get_context() is engine
    p.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Marker"), COSDictionary()],
    )
    assert len(engine.calls) == 1


def test_process_empty_operands_fires_hook_with_none_pair() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    p.process(Operator.get_operator("DP"), [])
    assert engine.calls == [(None, None)]


def test_process_with_only_tag_passes_none_properties() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(Operator.get_operator("DP"), [tag])
    assert engine.calls == [(tag, None)]


def test_dp_uses_distinct_hook_from_bdc() -> None:
    """``DP`` calls ``marked_content_point``; ``BDC`` calls
    ``begin_marked_content_sequence``. The classes must dispatch to
    distinct engine hooks even though they share property resolution."""
    from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_with_props import (  # noqa: E501
        BeginMarkedContentWithProps,
    )

    class _BothHook(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.begin_calls: int = 0
            self.point_calls: int = 0

        def begin_marked_content_sequence(
            self, tag: object, props: object
        ) -> None:
            self.begin_calls += 1

        def marked_content_point(
            self, tag: object, props: object
        ) -> None:
            self.point_calls += 1

    engine = _BothHook()
    DefineMarkedContentPointWithProps(engine).process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("Marker"), COSDictionary()],
    )
    BeginMarkedContentWithProps(engine).process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("Span"), COSDictionary()],
    )
    assert engine.point_calls == 1
    assert engine.begin_calls == 1
