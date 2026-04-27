from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import (
    DefineMarkedContentPoint,
)
from pypdfbox.cos import COSDictionary, COSName, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[COSName | None, COSDictionary | None]] = []

    def marked_content_point(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.calls.append((tag, properties))


def test_get_name() -> None:
    assert DefineMarkedContentPoint().get_name() == "MP"


def test_operator_name_constant() -> None:
    assert DefineMarkedContentPoint.OPERATOR_NAME == "MP"


def test_process_forwards_tag() -> None:
    engine = _Spy()
    p = DefineMarkedContentPoint()
    engine.add_operator(p)
    tag = COSName.get_pdf_name("Marker")
    p.process(Operator.get_operator("MP"), [tag])
    assert engine.calls == [(tag, None)]


def test_process_with_no_operands_passes_none_tag() -> None:
    engine = _Spy()
    p = DefineMarkedContentPoint()
    engine.add_operator(p)
    p.process(Operator.get_operator("MP"), [])
    assert engine.calls == [(None, None)]


def test_process_with_non_name_operand() -> None:
    engine = _Spy()
    p = DefineMarkedContentPoint()
    engine.add_operator(p)
    p.process(Operator.get_operator("MP"), [COSString("not-a-name")])
    assert engine.calls == [(None, None)]


def test_process_without_context_is_no_op() -> None:
    p = DefineMarkedContentPoint()
    p.process(Operator.get_operator("MP"), [COSName.get_pdf_name("X")])


def test_process_engine_without_hook_is_silent() -> None:
    engine = PDFStreamEngine()
    p = DefineMarkedContentPoint()
    engine.add_operator(p)
    p.process(Operator.get_operator("MP"), [COSName.get_pdf_name("X")])
