from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.text import ShowText, ShowTextLine
from pypdfbox.cos import COSBase, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []
        self.shown: bytes | None = None
        self.unsupported: list[str] = []

    def show_text_string(self, text: bytes) -> None:
        self.shown = text
        self.events.append("show_text_string")

    def unsupported_operator(self, operator: Operator, operands: list[COSBase]) -> None:
        self.unsupported.append(operator.get_name())


def test_get_name() -> None:
    assert ShowTextLine().get_name() == "'"


def test_process_decomposes_to_next_line_then_show() -> None:
    engine = _Spy()
    engine.add_operator(ShowText())
    p = ShowTextLine()
    engine.add_operator(p)
    p.process(Operator.get_operator("'"), [COSString(b"hi")])
    # NEXT_LINE has no handler — falls through to unsupported.
    assert "T*" in engine.unsupported
    assert engine.shown == b"hi"
