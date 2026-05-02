from __future__ import annotations

from pypdfbox.contentstream import Operator, OperatorName, PDFStreamEngine
from pypdfbox.contentstream.operator.text import MoveText, NextLine
from pypdfbox.cos import COSBase, COSFloat, COSNumber


class _Spy(PDFStreamEngine):
    def __init__(self, leading: float = 0.0) -> None:
        super().__init__()
        self._leading: float = leading
        self.move_calls: list[tuple[float, float]] = []

    def get_text_leading(self) -> float:
        return self._leading

    def move_text_position(self, tx: float, ty: float) -> None:
        self.move_calls.append((tx, ty))


def _bind() -> tuple[NextLine, _Spy]:
    p = NextLine()
    engine = _Spy(leading=14.0)
    engine.add_operator(p)
    engine.add_operator(MoveText())
    return p, engine


def test_get_name() -> None:
    assert NextLine().get_name() == "T*"


def test_process_decomposes_to_move_text_with_negative_leading() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("T*"), [])
    assert engine.move_calls == [(0.0, -14.0)]


def test_process_dispatches_move_text_operands() -> None:
    """MoveText must receive two COSNumber operands. We tap the engine
    via :meth:`process_operator` to verify the operand round-trip."""
    captured: list[list[COSBase]] = []

    class _CaptureMoveText(MoveText):
        def process(self, operator, operands):  # type: ignore[no-untyped-def]
            captured.append(list(operands))

    engine = _Spy(leading=20.0)
    engine.add_operator(NextLine())
    engine.add_operator(_CaptureMoveText())
    engine.get_operators()["T*"].process(Operator.get_operator("T*"), [])
    assert len(captured) == 1
    operands = captured[0]
    assert len(operands) == 2
    assert isinstance(operands[0], COSNumber)
    assert isinstance(operands[1], COSNumber)
    assert operands[0].float_value() == 0.0
    assert operands[1].float_value() == -20.0


def test_process_with_zero_leading() -> None:
    """Leading of 0 still fires Td; no vertical shift."""
    engine = _Spy(leading=0.0)
    p = NextLine()
    engine.add_operator(p)
    engine.add_operator(MoveText())
    p.process(Operator.get_operator("T*"), [])
    assert engine.move_calls == [(0.0, 0.0)]


def test_process_falls_back_to_zero_leading_when_engine_lacks_accessor() -> None:
    """Cluster #2 base engine has no ``get_text_leading``."""

    class _NoLeading(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[float, float]] = []

        def move_text_position(self, tx: float, ty: float) -> None:
            self.calls.append((tx, ty))

    engine = _NoLeading()
    p = NextLine()
    engine.add_operator(p)
    engine.add_operator(MoveText())
    p.process(Operator.get_operator("T*"), [])
    assert engine.calls == [(0.0, 0.0)]


def test_process_swallows_bogus_leading_accessor() -> None:
    """A misbehaving subclass that returns non-numeric text leading must
    not break the dispatch — fall through to zero."""

    class _BadLeading(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[float, float]] = []

        def get_text_leading(self) -> object:
            return "definitely-not-a-number"

        def move_text_position(self, tx: float, ty: float) -> None:
            self.calls.append((tx, ty))

    engine = _BadLeading()
    p = NextLine()
    engine.add_operator(p)
    engine.add_operator(MoveText())
    p.process(Operator.get_operator("T*"), [])
    assert engine.calls == [(0.0, 0.0)]


def test_get_name_matches_operator_name_constant() -> None:
    """``get_name()`` returns :data:`OperatorName.NEXT_LINE` — guards
    against drift between the constants table and the handler."""
    assert NextLine().get_name() == OperatorName.NEXT_LINE == "T*"


def test_tx_operand_is_cos_float_zero_constant() -> None:
    """Upstream uses the interned ``COSFloat.ZERO`` constant for the
    synthesized ``Td`` ``tx`` operand — not a freshly constructed
    ``COSFloat(0.0)``. We mirror the byte-identity for parity."""
    captured: list[list[COSBase]] = []

    class _Capture(MoveText):
        def process(self, operator, operands):  # type: ignore[no-untyped-def]
            captured.append(list(operands))

    engine = _Spy(leading=3.0)
    engine.add_operator(NextLine())
    engine.add_operator(_Capture())
    engine.get_operators()["T*"].process(Operator.get_operator("T*"), [])
    assert captured[0][0] is COSFloat.ZERO


def test_extra_operands_silently_ignored() -> None:
    """``T*`` takes zero operands per ISO 32000-1 §9.4.2; upstream just
    ignores any leftover stack and decomposes regardless. We do the
    same — operand list is unused."""
    p, engine = _bind()
    p.process(Operator.get_operator("T*"), [COSFloat(99.0)])
    assert engine.move_calls == [(0.0, -14.0)]


def test_infinite_leading_clamped_to_flt_max() -> None:
    """A pathological subclass returning ``inf`` for the leading must
    not crash. ``COSFloat`` clamps to single-precision FLT_MAX
    (mirroring Java float-conversion semantics), so the synthesized
    ``Td`` ty operand is ``-FLT_MAX`` rather than raw ``-inf``."""
    _flt_max = 3.4028234663852886e38
    engine = _Spy(leading=float("inf"))
    p = NextLine()
    engine.add_operator(p)
    engine.add_operator(MoveText())
    p.process(Operator.get_operator("T*"), [])
    assert engine.move_calls == [(0.0, -_flt_max)]
