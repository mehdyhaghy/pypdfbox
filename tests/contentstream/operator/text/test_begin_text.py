from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.text import BeginText


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.text_matrix: list[float] | None = None
        self.text_line_matrix: list[float] | None = None
        self.begin_text_calls: int = 0

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        # store a copy so later mutations of identity don't leak in
        self.text_matrix = list(matrix) if matrix is not None else None

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.text_line_matrix = list(matrix) if matrix is not None else None

    def begin_text(self) -> None:
        self.begin_text_calls += 1


def _bind() -> tuple[BeginText, _Spy]:
    p = BeginText()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


def test_get_name() -> None:
    assert BeginText().get_name() == "BT"


def test_process_resets_text_and_text_line_matrices_to_identity() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("BT"), [])
    assert engine.text_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert engine.text_line_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_process_notifies_engine_begin_text() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("BT"), [])
    assert engine.begin_text_calls == 1


def test_process_ignores_extra_operands() -> None:
    """BT takes no operands; passing extras must not fail."""
    from pypdfbox.cos import COSInteger

    p, engine = _bind()
    p.process(Operator.get_operator("BT"), [COSInteger.get(99)])
    assert engine.begin_text_calls == 1


def test_identity_lists_passed_to_engine_are_independent_copies() -> None:
    """Successive BT calls must not share the same list instance — a
    subclass that mutates the matrix in place must not poison the next
    BT's reset."""
    p, engine = _bind()
    p.process(Operator.get_operator("BT"), [])
    first_tm = engine.text_matrix
    first_tlm = engine.text_line_matrix
    p.process(Operator.get_operator("BT"), [])
    second_tm = engine.text_matrix
    second_tlm = engine.text_line_matrix
    assert first_tm is not second_tm
    assert first_tlm is not second_tlm


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import BeginText as Reexport

    assert Reexport is BeginText
