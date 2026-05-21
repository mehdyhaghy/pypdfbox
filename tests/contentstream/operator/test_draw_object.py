"""Hand-written tests for ``DrawObject`` (``Do``) — wave 1365.

Exercises the recursion guard, form / transparency-group dispatch and the
``is_image_x_object`` short-circuit through a minimal ``PDFStreamEngine``
subclass.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.draw_object import DrawObject
from pypdfbox.cos import COSInteger, COSName


class _StubResources:
    def __init__(
        self,
        *,
        x_object: object | None = None,
        is_image: bool = False,
    ) -> None:
        self._x_object = x_object
        self._is_image = is_image
        self.image_calls: list[COSName] = []
        self.x_calls: list[COSName] = []

    def is_image_x_object(self, name: COSName) -> bool:
        self.image_calls.append(name)
        return self._is_image

    def get_x_object(self, name: COSName) -> Any:
        self.x_calls.append(name)
        return self._x_object


class _FormXObject:
    is_form_xobject = True


class _PDTransparencyGroup:
    """Class name controls dispatch in ``_is_transparency_group``."""

    is_form_xobject = True


# Rename so ``type(obj).__name__`` matches what DrawObject checks for.
_PDTransparencyGroup.__name__ = "PDTransparencyGroup"


class _SpyEngine(PDFStreamEngine):
    def __init__(self, resources: _StubResources | None) -> None:
        super().__init__()
        self._resources = resources  # type: ignore[assignment]
        self.shown_forms: list[Any] = []
        self.shown_groups: list[Any] = []

    def show_form(self, form: Any) -> None:  # type: ignore[override]
        self.shown_forms.append(form)

    def show_transparency_group(self, form: Any) -> None:  # type: ignore[override]
        self.shown_groups.append(form)


def test_get_name() -> None:
    assert DrawObject().get_name() == "Do"


def test_operator_name_constant() -> None:
    assert DrawObject.OPERATOR_NAME == "Do"


def test_process_no_operands_raises() -> None:
    op = DrawObject()
    with pytest.raises(MissingOperandException):
        op.process(Operator.get_operator("Do"), [])


def test_process_non_name_operand_is_no_op() -> None:
    op = DrawObject()
    # No exception; just silently returns.
    op.process(Operator.get_operator("Do"), [COSInteger.get(5)])


def test_process_without_context_is_no_op() -> None:
    op = DrawObject()
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("Im0")]
    )


def test_process_no_resources_is_no_op() -> None:
    engine = _SpyEngine(resources=None)
    op = DrawObject()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("Im0")]
    )
    assert engine.shown_forms == []
    assert engine.shown_groups == []


def test_process_image_xobject_short_circuits() -> None:
    res = _StubResources(is_image=True, x_object=_FormXObject())
    engine = _SpyEngine(resources=res)
    op = DrawObject()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("Im0")]
    )
    # Image short-circuit: get_x_object never called, no show_form.
    assert res.image_calls == [COSName.get_pdf_name("Im0")]
    assert res.x_calls == []
    assert engine.shown_forms == []


def test_process_form_xobject_shows_form() -> None:
    form = _FormXObject()
    res = _StubResources(x_object=form)
    engine = _SpyEngine(resources=res)
    op = DrawObject()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("Fm0")]
    )
    assert engine.shown_forms == [form]
    assert engine.shown_groups == []
    assert engine.get_level() == 0  # decreased after dispatch


def test_process_transparency_group_dispatches_to_show_transparency_group() -> None:
    group = _PDTransparencyGroup()
    res = _StubResources(x_object=group)
    engine = _SpyEngine(resources=res)
    op = DrawObject()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("Fm1")]
    )
    assert engine.shown_groups == [group]
    assert engine.shown_forms == []


def test_process_recursion_guard_at_50() -> None:
    form = _FormXObject()
    res = _StubResources(x_object=form)
    engine = _SpyEngine(resources=res)
    # Push engine level just past 50 — DrawObject increases then checks.
    for _ in range(50):
        engine.increase_level()
    op = DrawObject()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("Fm0")]
    )
    # show_form should NOT have been invoked due to depth cap.
    assert engine.shown_forms == []
    # Level is restored after the finally.
    assert engine.get_level() == 50


def test_process_non_form_unknown_xobject_is_no_op() -> None:
    # An xobject whose type name is neither PDFormXObject nor
    # PDTransparencyGroup and which lacks is_form_xobject — silently skipped.
    class _Unknown:
        pass

    res = _StubResources(x_object=_Unknown())
    engine = _SpyEngine(resources=res)
    op = DrawObject()
    engine.add_operator(op)
    op.process(
        Operator.get_operator("Do"), [COSName.get_pdf_name("X")]
    )
    assert engine.shown_forms == []
    assert engine.shown_groups == []


def test_constructor_accepts_engine_context() -> None:
    engine = _SpyEngine(resources=None)
    op = DrawObject(engine)
    assert op.get_context() is engine
