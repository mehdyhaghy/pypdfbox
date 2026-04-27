from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import EndMarkedContent
from pypdfbox.cos import COSName


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.end_calls: int = 0

    def end_marked_content_sequence(self) -> None:
        self.end_calls += 1


def test_get_name() -> None:
    assert EndMarkedContent().get_name() == "EMC"


def test_operator_name_constant() -> None:
    assert EndMarkedContent.OPERATOR_NAME == "EMC"


def test_process_calls_end_hook() -> None:
    engine = _Spy()
    p = EndMarkedContent()
    engine.add_operator(p)
    p.process(Operator.get_operator("EMC"), [])
    assert engine.end_calls == 1


def test_process_ignores_stray_operands() -> None:
    # EMC takes no operands but the parser may have leftovers; the
    # operator must ignore them quietly.
    engine = _Spy()
    p = EndMarkedContent()
    engine.add_operator(p)
    p.process(Operator.get_operator("EMC"), [COSName.get_pdf_name("Stray")])
    assert engine.end_calls == 1


def test_process_without_context_is_no_op() -> None:
    p = EndMarkedContent()
    p.process(Operator.get_operator("EMC"), [])


def test_process_engine_without_hook_is_silent() -> None:
    engine = PDFStreamEngine()
    p = EndMarkedContent()
    engine.add_operator(p)
    p.process(Operator.get_operator("EMC"), [])
