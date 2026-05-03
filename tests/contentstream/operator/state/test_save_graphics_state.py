from __future__ import annotations

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.save_graphics_state import (
    SaveGraphicsState,
)


def test_class_advertises_lowercase_q_operator_name() -> None:
    assert SaveGraphicsState.OPERATOR_NAME == "q"
    assert SaveGraphicsState().get_name() == "q"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SaveGraphicsState, OperatorProcessor)


def test_process_with_no_operands_does_not_raise() -> None:
    p = SaveGraphicsState()
    p.process(Operator.get_operator("q"), [])


def test_default_registry_routes_lowercase_q_to_save_graphics_state() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("q")
    assert isinstance(handler, SaveGraphicsState)
    assert handler.get_name() == "q"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(Operator.get_operator("q"), [])


def test_process_invokes_engine_save_graphics_state_when_bound() -> None:
    # Upstream ``Save.process`` delegates to ``getContext().saveGraphicsState()``.
    # Mirror that: when bound to an engine, dispatching ``q`` must call
    # the engine's save hook so rendering subclasses can push a frame.
    calls: list[str] = []

    class TrackingEngine(PDFStreamEngine):
        def save_graphics_state(self) -> None:
            calls.append("save")

    engine = TrackingEngine()
    processor = SaveGraphicsState()
    processor.set_context(engine)
    processor.process(Operator.get_operator("q"), [])
    assert calls == ["save"]


def test_process_without_context_falls_through_to_log_path() -> None:
    # Standalone (registry-only) dispatch keeps prior no-raise behaviour
    # so existing registry consumers stay unaffected — the lite scaffold
    # has no engine to forward to.
    processor = SaveGraphicsState()
    processor.process(Operator.get_operator("q"), [])


def test_process_with_extra_operands_still_invokes_save() -> None:
    # ``q`` takes no operands per ISO 32000-1, but malformed streams may
    # pass extras. Upstream ignores them — we match.
    from pypdfbox.cos import COSInteger

    calls: list[str] = []

    class TrackingEngine(PDFStreamEngine):
        def save_graphics_state(self) -> None:
            calls.append("save")

    engine = TrackingEngine()
    processor = SaveGraphicsState()
    processor.set_context(engine)
    processor.process(
        Operator.get_operator("q"), [COSInteger.get(1), COSInteger.get(2)]
    )
    assert calls == ["save"]
