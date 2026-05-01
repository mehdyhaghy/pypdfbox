from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import BeginMarkedContent
from pypdfbox.cos import COSDictionary, COSName, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[COSName | None, COSDictionary | None]] = []

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.calls.append((tag, properties))


def test_get_name() -> None:
    assert BeginMarkedContent().get_name() == "BMC"


def test_operator_name_constant() -> None:
    assert BeginMarkedContent.OPERATOR_NAME == "BMC"


def test_process_forwards_tag_to_engine() -> None:
    engine = _Spy()
    p = BeginMarkedContent()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Span")
    p.process(Operator.get_operator("BMC"), [tag])
    assert engine.calls == [(tag, None)]


def test_process_with_no_operands_passes_none_tag() -> None:
    engine = _Spy()
    p = BeginMarkedContent()
    engine.add_operator(p)
    p.process(Operator.get_operator("BMC"), [])
    assert engine.calls == [(None, None)]


def test_process_with_non_name_first_operand_skips_tag() -> None:
    engine = _Spy()
    p = BeginMarkedContent()
    engine.add_operator(p)
    # Malformed: BMC with a string operand instead of a name. Hook still
    # fires but with tag=None, mirroring upstream tolerance.
    p.process(Operator.get_operator("BMC"), [COSString("not-a-name")])
    assert engine.calls == [(None, None)]


def test_process_without_context_is_no_op() -> None:
    # Constructed standalone (no engine context); process() must not
    # raise — the registry-only path uses this shape.
    p = BeginMarkedContent()
    p.process(Operator.get_operator("BMC"), [COSName.get_pdf_name("P")])


def test_process_engine_without_hook_is_silent() -> None:
    # Bare PDFStreamEngine has no begin_marked_content_sequence hook;
    # the operator must defensively skip it without raising.
    engine = PDFStreamEngine()
    p = BeginMarkedContent()
    engine.add_operator(p)
    p.process(Operator.get_operator("BMC"), [COSName.get_pdf_name("P")])


def test_name_property_matches_get_name() -> None:
    # ``name`` is a Pythonic alias mirroring Operator.name and must
    # return the same token as get_name() / OPERATOR_NAME.
    p = BeginMarkedContent()
    assert p.name == p.get_name() == p.OPERATOR_NAME == "BMC"


def test_constructor_accepts_engine_context() -> None:
    # Upstream constructor: BeginMarkedContentSequence(PDFStreamEngine).
    # Our base ``OperatorProcessor`` mirrors that — the context is bound
    # via the constructor, retrievable via get_context().
    engine = _Spy()
    p = BeginMarkedContent(engine)
    assert p.get_context() is engine
