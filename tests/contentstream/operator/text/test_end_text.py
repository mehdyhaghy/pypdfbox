from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.text import EndText


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.text_matrix_calls: list[list[float] | None] = []
        self.text_line_matrix_calls: list[list[float] | None] = []
        self.end_text_calls: int = 0

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        self.text_matrix_calls.append(matrix)

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.text_line_matrix_calls.append(matrix)

    def end_text(self) -> None:
        self.end_text_calls += 1


def _bind() -> tuple[EndText, _Spy]:
    p = EndText()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


def test_get_name() -> None:
    assert EndText().get_name() == "ET"


def test_process_clears_text_and_text_line_matrices() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("ET"), [])
    assert engine.text_matrix_calls == [None]
    assert engine.text_line_matrix_calls == [None]


def test_process_notifies_engine_end_text() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("ET"), [])
    assert engine.end_text_calls == 1


def test_process_ignores_extra_operands() -> None:
    from pypdfbox.cos import COSFloat

    p, engine = _bind()
    p.process(Operator.get_operator("ET"), [COSFloat(1.5)])
    assert engine.end_text_calls == 1


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import EndText as Reexport

    assert Reexport is EndText
