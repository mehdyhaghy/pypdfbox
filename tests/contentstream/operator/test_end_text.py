from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.text import EndText


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.text_matrix: object = "untouched"
        self.text_line_matrix: object = "untouched"

    def end_text(self) -> None:
        self.calls.append("end_text")

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        self.text_matrix = matrix
        self.calls.append("set_text_matrix")

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.text_line_matrix = matrix
        self.calls.append("set_text_line_matrix")


def test_get_name() -> None:
    assert EndText().get_name() == "ET"


def test_process_clears_matrices_and_notifies() -> None:
    engine = _Spy()
    p = EndText()
    engine.add_operator(p)
    p.process(Operator.get_operator("ET"), [])
    assert engine.calls == ["set_text_matrix", "set_text_line_matrix", "end_text"]
    assert engine.text_matrix is None
    assert engine.text_line_matrix is None
