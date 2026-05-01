from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import (
    BeginMarkedContentWithProps,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName
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


def test_get_name() -> None:
    assert BeginMarkedContentWithProps().get_name() == "BDC"


def test_operator_name_constant() -> None:
    assert BeginMarkedContentWithProps.OPERATOR_NAME == "BDC"


def test_process_with_inline_dict() -> None:
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    props = COSDictionary()
    props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(7))
    p.process(Operator.get_operator("BDC"), [tag, props])
    assert engine.calls == [(tag, props)]


def test_process_with_named_property_resolves_via_resources() -> None:
    # Build a resources object with /Properties/MyProps -> dict{ MCID: 3 }
    res = PDResources()
    cos_props = COSDictionary()
    cos_props.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(3))
    name = COSName.get_pdf_name("MyProps")
    res.put(COSName.get_pdf_name("Properties"), name, cos_props)

    engine = _Spy(resources=res)
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("OC")
    p.process(Operator.get_operator("BDC"), [tag, name])
    assert len(engine.calls) == 1
    seen_tag, seen_props = engine.calls[0]
    assert seen_tag is tag
    assert seen_props is not None
    assert seen_props.get_int(COSName.get_pdf_name("MCID")) == 3


def test_process_with_unresolved_named_property_passes_none() -> None:
    # Resources lack /Properties/Missing — property resolution returns None.
    res = PDResources()
    engine = _Spy(resources=res)
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(
        Operator.get_operator("BDC"),
        [tag, COSName.get_pdf_name("Missing")],
    )
    assert engine.calls == [(tag, None)]


def test_process_with_only_tag_passes_none_properties() -> None:
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(Operator.get_operator("BDC"), [tag])
    assert engine.calls == [(tag, None)]


def test_process_with_no_operands() -> None:
    engine = _Spy()
    p = BeginMarkedContentWithProps()
    engine.add_operator(p)
    p.process(Operator.get_operator("BDC"), [])
    assert engine.calls == [(None, None)]


def test_process_without_context_is_no_op() -> None:
    p = BeginMarkedContentWithProps()
    p.process(
        Operator.get_operator("BDC"),
        [COSName.get_pdf_name("P"), COSDictionary()],
    )


def test_name_property_matches_get_name() -> None:
    p = BeginMarkedContentWithProps()
    assert p.name == p.get_name() == p.OPERATOR_NAME == "BDC"


def test_constructor_accepts_engine_context() -> None:
    engine = _Spy()
    p = BeginMarkedContentWithProps(engine)
    assert p.get_context() is engine
