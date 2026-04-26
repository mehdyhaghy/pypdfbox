from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.text import BeginText


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.text_matrix: object = "untouched"
        self.text_line_matrix: object = "untouched"

    def begin_text(self) -> None:
        self.calls.append("begin_text")

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        self.text_matrix = matrix
        self.calls.append("set_text_matrix")

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.text_line_matrix = matrix
        self.calls.append("set_text_line_matrix")


def test_get_name() -> None:
    assert BeginText().get_name() == "BT"


def test_process_resets_matrices_and_notifies() -> None:
    engine = _Spy()
    p = BeginText()
    engine.add_operator(p)
    p.process(Operator.get_operator("BT"), [])
    assert engine.calls == ["set_text_matrix", "set_text_line_matrix", "begin_text"]
    assert engine.text_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert engine.text_line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    # Independent list instances so mutation can't bleed across.
    assert engine.text_matrix is not engine.text_line_matrix
