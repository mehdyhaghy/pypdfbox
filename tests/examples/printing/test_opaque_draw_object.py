"""Tests for ``pypdfbox.examples.printing.opaque_draw_object``."""

from __future__ import annotations

import logging

import pytest

from pypdfbox.contentstream.operator.graphics.graphics_operator_processor import (
    GraphicsOperatorProcessor,
)
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.printing.opaque_draw_object import OpaqueDrawObject
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeOperator:
    def get_name(self) -> str:
        return "Do"


class _FakeImageXObject:
    """Class name must literally match ``PDImageXObject`` so the example's
    ``type(xobject).__name__`` dispatch fires."""


_FakeImageXObject.__name__ = "PDImageXObject"


class _FakeFormXObject:
    pass


_FakeFormXObject.__name__ = "PDFormXObject"


class _FakeResources:
    def __init__(self, xobject: object | None) -> None:
        self._xo = xobject

    def get_x_object(self, name):  # noqa: ANN001
        return self._xo


class _FakeContext:
    def __init__(
        self,
        xobject: object | None,
        *,
        level: int = 0,
    ) -> None:
        self._resources = _FakeResources(xobject)
        self.level = level
        self.drawn_images: list[object] = []
        self.shown_forms: list[object] = []
        self.increase_calls = 0
        self.decrease_calls = 0

    def get_resources(self):  # noqa: ANN201
        return self._resources

    def draw_image(self, image: object) -> None:
        self.drawn_images.append(image)

    def show_form(self, form: object) -> None:
        self.shown_forms.append(form)

    def increase_level(self) -> None:
        self.level += 1
        self.increase_calls += 1

    def decrease_level(self) -> None:
        self.level -= 1
        self.decrease_calls += 1

    def get_level(self) -> int:
        return self.level


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_subclasses_graphics_operator_processor() -> None:
    assert issubclass(OpaqueDrawObject, GraphicsOperatorProcessor)


def test_get_name_returns_do() -> None:
    op = OpaqueDrawObject(None)
    assert op.get_name() == OperatorName.DRAW_OBJECT


def test_process_raises_on_empty_operands() -> None:
    op = OpaqueDrawObject(None)
    with pytest.raises(MissingOperandException):
        op.process(_FakeOperator(), [])


def test_process_returns_silently_for_non_name_operand() -> None:
    op = OpaqueDrawObject(None)
    op.process(_FakeOperator(), [object()])


def test_process_returns_when_context_is_none() -> None:
    op = OpaqueDrawObject(None)
    # No context -> get_graphics_context() is None, early return without error.
    op.process(_FakeOperator(), [COSName.get_pdf_name("Im0")])


def test_process_raises_when_xobject_missing() -> None:
    context = _FakeContext(None)
    op = OpaqueDrawObject(context)
    with pytest.raises(MissingResourceException, match="Missing XObject"):
        op.process(_FakeOperator(), [COSName.get_pdf_name("Im0")])


def test_process_draws_image_xobject() -> None:
    img = _FakeImageXObject()
    context = _FakeContext(img)
    op = OpaqueDrawObject(context)
    op.process(_FakeOperator(), [COSName.get_pdf_name("Im0")])
    assert context.drawn_images == [img]
    assert context.shown_forms == []
    # Image branch must not touch the recursion counter.
    assert context.increase_calls == 0
    assert context.decrease_calls == 0


def test_process_shows_form_xobject_and_balances_level() -> None:
    form = _FakeFormXObject()
    context = _FakeContext(form, level=0)
    op = OpaqueDrawObject(context)
    op.process(_FakeOperator(), [COSName.get_pdf_name("Fm0")])
    assert context.shown_forms == [form]
    assert context.increase_calls == 1
    assert context.decrease_calls == 1
    assert context.level == 0


def test_process_skips_form_when_recursion_too_deep(
    caplog: pytest.LogCaptureFixture,
) -> None:
    form = _FakeFormXObject()
    # Pre-set the depth just below the cap so increase_level() pushes us over.
    context = _FakeContext(form, level=50)
    op = OpaqueDrawObject(context)
    with caplog.at_level(logging.ERROR):
        op.process(_FakeOperator(), [COSName.get_pdf_name("Fm0")])
    assert context.shown_forms == []
    assert any("recursion is too deep" in r.message for r in caplog.records)
    # Decrease must still fire (finally clause), so counter returns to start.
    assert context.decrease_calls == 1
    assert context.level == 50


def test_process_ignores_unknown_xobject_type() -> None:
    class _Other:
        pass

    _Other.__name__ = "PDSomethingElse"
    context = _FakeContext(_Other())
    op = OpaqueDrawObject(context)
    op.process(_FakeOperator(), [COSName.get_pdf_name("X0")])
    assert context.drawn_images == []
    assert context.shown_forms == []
