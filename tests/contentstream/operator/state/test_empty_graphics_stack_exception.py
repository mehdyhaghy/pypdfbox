from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.state import (
    EmptyGraphicsStackException,
    RestoreGraphicsState,
)


def test_message_mirrors_upstream_verbatim() -> None:
    exc = EmptyGraphicsStackException()
    # Mirrors upstream string verbatim.
    assert str(exc) == "Cannot execute restore, the graphics stack is empty"


def test_is_oserror_subclass() -> None:
    # Per the project's test-porting convention: IOException -> OSError.
    assert issubclass(EmptyGraphicsStackException, OSError)


def test_no_arg_constructor() -> None:
    # Mirrors upstream package-private no-arg constructor shape.
    exc = EmptyGraphicsStackException()
    assert isinstance(exc, EmptyGraphicsStackException)


def test_restore_raises_when_engine_stack_empty() -> None:
    # Mirrors PDFBOX-161 behaviour: invoking ``Q`` when the graphics
    # stack does not have more than one frame raises
    # ``EmptyGraphicsStackException``. The base engine ships with an
    # empty stack so a freshly bound RestoreGraphicsState fires this.
    engine = PDFStreamEngine()
    processor = RestoreGraphicsState()
    processor.set_context(engine)
    assert engine.get_graphics_stack_size() == 0
    with pytest.raises(EmptyGraphicsStackException):
        processor.process(Operator.get_operator("Q"), [])


def test_restore_does_not_raise_when_stack_has_more_than_one_frame() -> None:
    # Two frames: a Q can pop without raising.
    engine = PDFStreamEngine()
    engine._graphics_stack.append(object())
    engine._graphics_stack.append(object())
    processor = RestoreGraphicsState()
    processor.set_context(engine)
    processor.process(Operator.get_operator("Q"), [])


def test_restore_without_context_falls_through_to_log_path() -> None:
    # Standalone (registry-only) dispatch keeps prior no-raise behaviour
    # so existing registry consumers stay unaffected.
    processor = RestoreGraphicsState()
    processor.process(Operator.get_operator("Q"), [])
