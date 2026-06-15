from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import (
    DefineMarkedContentPointWithProps,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName
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


def test_get_name() -> None:
    assert DefineMarkedContentPointWithProps().get_name() == "DP"


def test_operator_name_constant() -> None:
    assert DefineMarkedContentPointWithProps.OPERATOR_NAME == "DP"


def test_process_with_inline_dict() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    props = COSDictionary()
    props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(11))
    p.process(Operator.get_operator("DP"), [tag, props])
    assert engine.calls == [(tag, props)]


def test_process_with_named_property_resolves_via_resources() -> None:
    res = PDResources()
    cos_props = COSDictionary()
    cos_props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(5))
    name = COSName.get_pdf_name("MyProps")
    res.put(COSName.get_pdf_name("Properties"), name, cos_props)

    engine = _Spy(resources=res)
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(Operator.get_operator("DP"), [tag, name])
    assert len(engine.calls) == 1
    seen_tag, seen_props = engine.calls[0]
    assert seen_tag is tag
    assert seen_props is not None
    assert seen_props.get_int(COSName.get_pdf_name("MCID")) == 5


def test_process_with_unresolved_named_property_does_not_fire() -> None:
    # Wave-1535 oracle: DP returns without notifying the engine when the
    # property list cannot be resolved (mirrors BDC).
    res = PDResources()
    engine = _Spy(resources=res)
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(
        Operator.get_operator("DP"),
        [tag, COSName.get_pdf_name("Missing")],
    )
    assert engine.calls == []


def test_process_with_only_tag_raises_missing_operand() -> None:
    # Wave-1535 oracle: DP requires two operands; underflow raises
    # MissingOperandException upstream.
    import pytest

    from pypdfbox.contentstream.operator import MissingOperandException

    engine = _Spy()
    p = DefineMarkedContentPointWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("DP"), [tag])
    assert engine.calls == []


def test_process_without_context_is_no_op() -> None:
    p = DefineMarkedContentPointWithProps()
    p.process(
        Operator.get_operator("DP"),
        [COSName.get_pdf_name("X"), COSDictionary()],
    )


def test_name_property_matches_get_name() -> None:
    p = DefineMarkedContentPointWithProps()
    assert p.name == p.get_name() == p.OPERATOR_NAME == "DP"


def test_constructor_accepts_engine_context() -> None:
    engine = _Spy()
    p = DefineMarkedContentPointWithProps(engine)
    assert p.get_context() is engine
