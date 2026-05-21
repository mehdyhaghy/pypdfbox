"""Parity tests for the engine-coupled ``Save`` (``q``) handler.

Targets ``pypdfbox/contentstream/operator/state/save.py`` — mirrors
``org.apache.pdfbox.contentstream.operator.state.Save``. The
sibling ``save_graphics_state.py`` exports the legacy
``SaveGraphicsState`` shape and is tested separately; this file
focuses on the upstream-named ``Save`` handler that the standalone
``OperatorRegistry`` does *not* wire (the registry uses
``SaveGraphicsState``) but which the rendering engine instantiates
with a bound context.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import OperatorName
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.state.save import Save
from pypdfbox.cos import COSInteger


class _SaveSpy(PDFStreamEngine):
    """Counts ``save_graphics_state`` calls so handler dispatch is
    observable from the test."""

    def __init__(self) -> None:
        super().__init__()
        self.save_calls: int = 0

    def save_graphics_state(self) -> None:
        self.save_calls += 1


def test_operator_name_constant_is_q() -> None:
    assert Save.OPERATOR_NAME == OperatorName.SAVE
    assert Save.OPERATOR_NAME == "q"


def test_get_name_returns_q() -> None:
    assert Save().get_name() == "q"


def test_inherits_from_operator_processor() -> None:
    assert issubclass(Save, OperatorProcessor)


def test_process_with_engine_invokes_save_graphics_state() -> None:
    """Happy path: a bound engine receives a single
    ``save_graphics_state`` call when ``q`` is processed."""
    engine = _SaveSpy()
    Save(engine).process(Operator.get_operator("q"), [])
    assert engine.save_calls == 1


def test_process_without_context_is_silent() -> None:
    """An unbound ``Save`` (no engine context) must not raise — it
    early-returns when ``self._context is None``."""
    Save().process(Operator.get_operator("q"), [])


def test_process_ignores_operands() -> None:
    """``q`` takes no operands; extras are silently dropped (matches
    upstream behaviour of consuming the stack without inspecting it)."""
    engine = _SaveSpy()
    Save(engine).process(
        Operator.get_operator("q"),
        [COSInteger.get(1), COSInteger.get(2)],
    )
    assert engine.save_calls == 1


def test_repeated_process_calls_each_save_once() -> None:
    """Three ``q`` dispatches → three ``save_graphics_state`` calls."""
    engine = _SaveSpy()
    handler = Save(engine)
    op = Operator.get_operator("q")
    for _ in range(3):
        handler.process(op, [])
    assert engine.save_calls == 3


def test_set_context_rebinds_engine() -> None:
    """A processor constructed without context may be late-bound via
    ``set_context`` (mirrors the engine's ``add_operator`` flow)."""
    engine = _SaveSpy()
    handler = Save()
    assert handler.get_context() is None
    handler.set_context(engine)
    assert handler.get_context() is engine
    handler.process(Operator.get_operator("q"), [])
    assert engine.save_calls == 1


def test_engine_add_operator_binds_and_dispatches() -> None:
    """End-to-end: registering the processor with the engine binds it
    and routes ``q`` correctly."""
    engine = _SaveSpy()
    handler = Save()
    engine.add_operator(handler)
    assert engine.get_operator("q") is handler
    handler.process(Operator.get_operator("q"), [])
    assert engine.save_calls == 1


def test_get_name_is_idempotent() -> None:
    """``get_name`` is a pure accessor — repeated calls are stable."""
    h = Save()
    assert h.get_name() == h.get_name() == "q"


def test_subclass_save_hook_receives_call() -> None:
    """The rendering subclass overrides ``save_graphics_state`` to
    actually push a frame; verify the handler hits the overridden
    method by stack inspection rather than a counter."""

    class _StackEngine(PDFStreamEngine):
        def save_graphics_state(self) -> None:
            self._graphics_stack.append(object())

        def get_graphics_state(self) -> Any:
            if not self._graphics_stack:
                return None
            return self._graphics_stack[-1]

    engine = _StackEngine()
    starting = engine.get_graphics_stack_size()
    Save(engine).process(Operator.get_operator("q"), [])
    assert engine.get_graphics_stack_size() == starting + 1
