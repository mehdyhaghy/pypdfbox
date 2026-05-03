"""Hand-written tests for :class:`pypdfbox.contentstream.operator.text.ShowText`.

The engine-level ``Tj`` round-trip is exercised in
``tests/contentstream/test_pdf_stream_engine.py``; this file covers the
``ShowText.process`` operator-handler surface itself — the silent-no-op
shapes upstream documents (empty operands, non-string operand) and the
:class:`MissingOperandException` we raise on a zero-operand call (a
strictly more conservative shape — see the class docstring).
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorName,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator import OperatorProcessor
from pypdfbox.contentstream.operator.text import ShowText
from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.shown: list[bytes] = []
        self.calls: int = 0

    def show_text_string(self, text: bytes) -> None:
        self.shown.append(text)
        self.calls += 1


def _bind() -> tuple[ShowText, _Spy]:
    p = ShowText()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


# ---------- name ----------


def test_get_name() -> None:
    assert ShowText().get_name() == "Tj"


def test_get_name_matches_operator_name_constant() -> None:
    assert ShowText().get_name() == OperatorName.SHOW_TEXT


def test_show_text_is_operator_processor_subclass() -> None:
    assert issubclass(ShowText, OperatorProcessor)


# ---------- happy path ----------


def test_process_dispatches_string_bytes_to_engine() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSString(b"Hello")])
    assert engine.shown == [b"Hello"]
    assert engine.calls == 1


def test_process_preserves_raw_bytes_unchanged() -> None:
    """``Tj`` operands are raw byte strings (not Unicode); the operator
    must not mutate, decode, or re-encode them — the engine's
    ``show_text`` is responsible for font-driven byte-to-code mapping."""
    p, engine = _bind()
    raw = bytes(range(256))
    p.process(Operator.get_operator("Tj"), [COSString(raw)])
    assert engine.shown == [raw]


def test_process_empty_string_still_dispatches() -> None:
    """Upstream ignores ``( )Tj`` (empty operand *list*), but
    ``(<empty>)Tj`` (a single empty ``COSString``) reaches
    ``showTextString``. We mirror that asymmetry."""
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSString(b"")])
    assert engine.shown == [b""]
    assert engine.calls == 1


def test_process_uses_first_operand_only() -> None:
    """Upstream consults ``arguments.get(0)`` and ignores the rest."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tj"),
        [COSString(b"first"), COSString(b"second"), COSString(b"third")],
    )
    assert engine.shown == [b"first"]


def test_process_returns_none() -> None:
    p, engine = _bind()
    result = p.process(Operator.get_operator("Tj"), [COSString(b"x")])
    assert result is None


# ---------- silent-no-op shapes (mirroring upstream) ----------


def test_non_string_first_operand_silently_drops_cos_integer() -> None:
    """Mirrors upstream's ``!(base instanceof COSString)`` short-circuit."""
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSInteger.get(7)])
    assert engine.shown == []
    assert engine.calls == 0


def test_non_string_first_operand_silently_drops_cos_float() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSFloat(3.14)])
    assert engine.shown == []
    assert engine.calls == 0


def test_non_string_first_operand_silently_drops_cos_name() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSName.get_pdf_name("F1")])
    assert engine.shown == []
    assert engine.calls == 0


def test_non_string_first_operand_silently_drops_cos_array() -> None:
    """A ``COSArray`` is the ``TJ`` shape — passing it to ``Tj`` is a
    stream bug, but upstream silently ignores it rather than crashing."""
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSArray()])
    assert engine.shown == []


def test_non_string_first_operand_silently_drops_cos_null() -> None:
    p, engine = _bind()
    p.process(Operator.get_operator("Tj"), [COSNull.NULL])
    assert engine.shown == []


# ---------- zero-operand: pypdfbox raises (strictly more conservative) ----------


def test_zero_operands_raises_missing_operand_exception() -> None:
    """Upstream silently no-ops on empty operand list; pypdfbox raises
    :class:`MissingOperandException` instead. The engine's
    ``operator_exception`` hook still demotes it to a log line so the
    end-to-end behaviour matches upstream — see the class docstring."""
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tj"), [])


def test_zero_operands_message_carries_operator_name() -> None:
    p, _ = _bind()
    op = Operator.get_operator("Tj")
    with pytest.raises(MissingOperandException) as exc_info:
        p.process(op, [])
    msg = str(exc_info.value)
    assert "Tj" in msg
    assert "too few operands" in msg
    assert exc_info.value.operator is op
    assert exc_info.value.operands == []


# ---------- engine binding ----------


def test_get_context_unbound_raises() -> None:
    """Calling ``process`` before registration raises ``RuntimeError``
    (upstream's ``OperatorProcessor.context`` is also non-null at use)."""
    p = ShowText()
    with pytest.raises(RuntimeError):
        p.process(Operator.get_operator("Tj"), [COSString(b"x")])


def test_unbound_short_circuit_path_does_not_touch_context() -> None:
    """When the operand is the wrong type, ``process`` returns *before*
    consulting the engine — so an unbound :class:`ShowText` must not
    raise on a non-``COSString`` first operand either."""
    p = ShowText()
    # No engine registered, but the wrong-type guard returns before
    # ``get_context`` is reached, so this must not raise.
    p.process(Operator.get_operator("Tj"), [COSInteger.get(0)])


def test_unbound_zero_operand_raises_before_context_lookup() -> None:
    """Conversely the zero-operand branch raises
    :class:`MissingOperandException` *before* the context lookup, so an
    unbound :class:`ShowText` produces the operand error (not a bind
    error) on an empty operand list."""
    p = ShowText()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tj"), [])


# ---------- multi-call & re-binding ----------


def test_multiple_consecutive_show_text_calls_are_dispatched_in_order() -> None:
    p, engine = _bind()
    op = Operator.get_operator("Tj")
    p.process(op, [COSString(b"A")])
    p.process(op, [COSString(b"B")])
    p.process(op, [COSString(b"C")])
    assert engine.shown == [b"A", b"B", b"C"]
    assert engine.calls == 3


def test_process_does_not_consume_or_mutate_operands_list() -> None:
    """The operator handler must not mutate the caller's operand list —
    the parser owns it and may reuse it."""
    p, _ = _bind()
    operands: list = [COSString(b"hi"), COSString(b"there")]
    snapshot = list(operands)
    p.process(Operator.get_operator("Tj"), operands)
    assert operands == snapshot


# ---------- re-exports ----------


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import ShowText as Reexport

    assert Reexport is ShowText


def test_show_text_module_path_canonical() -> None:
    """The engine-coupled :class:`ShowText` lives at
    ``pypdfbox.contentstream.operator.text.show_text`` — the package
    re-export should point at the same class."""
    from pypdfbox.contentstream.operator.text import show_text as module

    assert module.ShowText is ShowText
