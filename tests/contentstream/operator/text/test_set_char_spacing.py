from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetCharSpacing
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.spacing: float | None = None
        self.calls: int = 0

    def set_character_spacing(self, spacing: float) -> None:
        self.spacing = spacing
        self.calls += 1


def _bind(p: SetCharSpacing) -> _Spy:
    engine = _Spy()
    engine.add_operator(p)
    return engine


def test_get_name() -> None:
    assert SetCharSpacing().get_name() == "Tc"


def test_process_dispatches_with_float() -> None:
    p = SetCharSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tc"), [COSFloat(0.5)])
    assert engine.spacing == 0.5
    assert engine.calls == 1


def test_process_accepts_cos_integer() -> None:
    p = SetCharSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tc"), [COSInteger.get(2)])
    assert engine.spacing == 2.0


def test_process_accepts_negative_spacing() -> None:
    p = SetCharSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tc"), [COSFloat(-0.25)])
    assert engine.spacing == -0.25


def test_zero_operands_raises() -> None:
    p = SetCharSpacing()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tc"), [])


def test_wrong_type_silently_drops() -> None:
    p = SetCharSpacing()
    engine = _bind(p)
    p.process(Operator.get_operator("Tc"), [COSString(b"oops")])
    assert engine.spacing is None
    assert engine.calls == 0


def test_re_export_canonical() -> None:
    """SetCharSpacing must be importable from the package surface."""
    from pypdfbox.contentstream.operator.text import (
        SetCharSpacing as Reexport,
    )

    assert Reexport is SetCharSpacing


def test_process_uses_last_argument_when_malformed() -> None:
    """Upstream uses the LAST argument so malformed multi-arg `Tc`
    instructions still parse — see the comment in
    ``SetCharSpacing.java#process``: 'we will assume the last argument
    in the list'."""
    p = SetCharSpacing()
    engine = _bind(p)
    # Two-argument malformed `Tc` — must pick up the LAST value.
    p.process(
        Operator.get_operator("Tc"),
        [COSFloat(99.0), COSFloat(0.5)],
    )
    assert engine.spacing == 0.5
    assert engine.calls == 1


def test_process_last_argument_drops_when_non_number() -> None:
    """When the LAST operand is non-numeric the call is dropped, even
    if an earlier operand was a number — matches upstream's
    ``charSpacing instanceof COSNumber`` short-circuit on the
    last-arg pick."""
    p = SetCharSpacing()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tc"),
        [COSFloat(2.0), COSString(b"oops")],
    )
    assert engine.spacing is None
    assert engine.calls == 0
