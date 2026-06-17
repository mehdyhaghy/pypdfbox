"""Wave 1587 — fuzz / parity for the ``Do`` operator + XObject processing.

Targets the content-stream engine's XObject dispatch:

* the graphics ``Do`` handler
  (:class:`~pypdfbox.contentstream.operator.graphics.invoke_named_xobject.InvokeNamedXObject`)
  — image vs form vs transparency-group subtype dispatch, the
  ``MissingResourceException`` on an unresolved name, the non-stencil /
  colour-suppression image skip, and the recursion-level guard around
  ``show_form`` / ``show_transparency_group``;
* the text-extraction ``Do`` handler
  (:class:`~pypdfbox.contentstream.operator.draw_object.DrawObject`) — its
  ``is_image_x_object`` short-circuit and the same recursion guard;
* the real :class:`PDFStreamEngine` ``show_form`` /
  ``process_child_stream`` resource-stack push/pop and parent-resource
  restoration.

Compared against upstream PDFBox 3.0.7
``contentstream/operator/graphics/DrawObject.java`` and
``contentstream/operator/DrawObject.java`` (both guard the form/group
dispatch with ``increaseLevel()`` / ``getLevel() > 50`` / ``decreaseLevel()``)
and ``PDFStreamEngine.processStream`` (pushes the stream's ``/Resources``,
restores the parent's afterwards).
"""

from __future__ import annotations

import contextlib
from typing import Any

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.draw_object import DrawObject
from pypdfbox.contentstream.operator.graphics.invoke_named_xobject import (
    InvokeNamedXObject,
)
from pypdfbox.contentstream.operator.operator_processor import OperatorProcessor
from pypdfbox.contentstream.pd_content_stream import PDContentStream
from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.cos import COSBase, COSInteger, COSName
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException


# --------------------------------------------------------------------------
# Fake XObject types — the engine dispatches on ``type(obj).__name__`` so the
# class names must match the upstream PDXObject subclasses exactly.
# --------------------------------------------------------------------------
class PDImageXObject:  # noqa: N801 — mirrors upstream class name for dispatch
    def __init__(self, stencil: bool = False) -> None:
        self._stencil = stencil

    def is_stencil(self) -> bool:
        return self._stencil


class PDFormXObject:  # noqa: N801 — mirrors upstream class name for dispatch
    is_form_xobject = True


class PDTransparencyGroup:  # noqa: N801 — mirrors upstream class name
    is_form_xobject = True


class _Resources:
    def __init__(self, x_objects: dict[COSName, Any] | None = None) -> None:
        self._x_objects = x_objects or {}
        self.image_names: set[COSName] = set()

    def is_image_x_object(self, name: COSName) -> bool:
        return name in self.image_names

    def get_x_object(self, name: COSName) -> Any:
        return self._x_objects.get(name)


class _RecordingEngine:
    """Records every XObject dispatch + level transition so a test can
    assert exactly which engine hook fired and that the level counter is
    balanced (pushed before the dispatch, popped after)."""

    def __init__(
        self,
        resources: _Resources | None = None,
        process_colors: bool = True,
    ) -> None:
        self.resources = resources
        self._process_colors = process_colors
        self.level = 0
        self.max_level = 0
        self.events: list[tuple[str, Any, int]] = []

    # resource / colour gating ------------------------------------------
    def get_resources(self) -> _Resources | None:
        return self.resources

    def is_should_process_color_operators(self) -> bool:
        return self._process_colors

    # recursion-level counter -------------------------------------------
    def increase_level(self) -> None:
        self.level += 1
        self.max_level = max(self.max_level, self.level)

    def decrease_level(self) -> None:
        self.level -= 1

    def get_level(self) -> int:
        return self.level

    # XObject hooks ------------------------------------------------------
    def draw_image(self, image: Any) -> None:
        self.events.append(("draw_image", image, self.level))

    def show_form(self, form: Any) -> None:
        self.events.append(("show_form", form, self.level))

    def show_transparency_group(self, group: Any) -> None:
        self.events.append(("show_transparency_group", group, self.level))


def _op(name: str = "Do") -> Operator:
    return Operator(name)


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


# ==========================================================================
# Graphics ``Do`` (InvokeNamedXObject) — operand validation
# ==========================================================================
class TestGraphicsDoOperandValidation:
    def test_empty_operands_raises(self) -> None:
        handler = InvokeNamedXObject(_RecordingEngine(_Resources()))
        with pytest.raises(MissingOperandException):
            handler.process(_op(), [])

    def test_non_name_operand_silently_skips(self) -> None:
        engine = _RecordingEngine(_Resources())
        InvokeNamedXObject(engine).process(_op(), [COSInteger(7)])
        assert engine.events == []

    def test_none_context_is_noop(self) -> None:
        handler = InvokeNamedXObject(None)
        handler.process(_op(), [_name("Fm0")])  # no raise

    def test_none_resources_is_noop(self) -> None:
        engine = _RecordingEngine(resources=None)
        InvokeNamedXObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == []

    def test_missing_xobject_raises_missing_resource(self) -> None:
        engine = _RecordingEngine(_Resources())
        with pytest.raises(MissingResourceException):
            InvokeNamedXObject(engine).process(_op(), [_name("Nope")])


# ==========================================================================
# Graphics ``Do`` — subtype dispatch
# ==========================================================================
class TestGraphicsDoDispatch:
    def test_image_xobject_goes_to_draw_image(self) -> None:
        img = PDImageXObject()
        res = _Resources({_name("Im0"): img})
        engine = _RecordingEngine(res)
        InvokeNamedXObject(engine).process(_op(), [_name("Im0")])
        assert engine.events == [("draw_image", img, 0)]
        # image dispatch never touches the recursion level
        assert engine.max_level == 0

    def test_form_xobject_goes_to_show_form(self) -> None:
        form = PDFormXObject()
        res = _Resources({_name("Fm0"): form})
        engine = _RecordingEngine(res)
        InvokeNamedXObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == [("show_form", form, 1)]
        # level bumped during the dispatch, restored afterwards
        assert engine.level == 0
        assert engine.max_level == 1

    def test_transparency_group_goes_to_its_own_hook(self) -> None:
        group = PDTransparencyGroup()
        res = _Resources({_name("Gs0"): group})
        engine = _RecordingEngine(res)
        InvokeNamedXObject(engine).process(_op(), [_name("Gs0")])
        assert engine.events == [("show_transparency_group", group, 1)]
        assert engine.level == 0

    def test_stencil_image_painted_even_when_colors_suppressed(self) -> None:
        img = PDImageXObject(stencil=True)
        res = _Resources({_name("Im0"): img})
        engine = _RecordingEngine(res, process_colors=False)
        InvokeNamedXObject(engine).process(_op(), [_name("Im0")])
        assert engine.events == [("draw_image", img, 0)]

    def test_non_stencil_image_skipped_when_colors_suppressed(self) -> None:
        img = PDImageXObject(stencil=False)
        res = _Resources({_name("Im0"): img})
        engine = _RecordingEngine(res, process_colors=False)
        InvokeNamedXObject(engine).process(_op(), [_name("Im0")])
        assert engine.events == []

    def test_non_stencil_image_painted_when_colors_enabled(self) -> None:
        img = PDImageXObject(stencil=False)
        res = _Resources({_name("Im0"): img})
        engine = _RecordingEngine(res, process_colors=True)
        InvokeNamedXObject(engine).process(_op(), [_name("Im0")])
        assert engine.events == [("draw_image", img, 0)]


# ==========================================================================
# Graphics ``Do`` — recursion-level guard (the wave-1587 fix)
# ==========================================================================
class TestGraphicsDoRecursionGuard:
    def test_form_below_cap_dispatches(self) -> None:
        form = PDFormXObject()
        engine = _RecordingEngine(_Resources({_name("Fm0"): form}))
        engine.level = 49  # next bump -> 50, still <= 50
        InvokeNamedXObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == [("show_form", form, 50)]
        assert engine.level == 49  # restored

    def test_form_at_cap_boundary_still_dispatches(self) -> None:
        # level 49 -> 50 is allowed (guard is ``> 50``)
        form = PDFormXObject()
        engine = _RecordingEngine(_Resources({_name("Fm0"): form}))
        engine.level = 49
        InvokeNamedXObject(engine).process(_op(), [_name("Fm0")])
        assert any(e[0] == "show_form" for e in engine.events)

    def test_form_over_cap_is_skipped(self) -> None:
        form = PDFormXObject()
        engine = _RecordingEngine(_Resources({_name("Fm0"): form}))
        engine.level = 50  # next bump -> 51 > 50 -> skip
        InvokeNamedXObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == []  # dispatch suppressed
        assert engine.level == 50  # restored in finally

    def test_group_over_cap_is_skipped(self) -> None:
        group = PDTransparencyGroup()
        engine = _RecordingEngine(_Resources({_name("Gs0"): group}))
        engine.level = 60
        InvokeNamedXObject(engine).process(_op(), [_name("Gs0")])
        assert engine.events == []
        assert engine.level == 60

    def test_level_restored_when_show_form_raises(self) -> None:
        form = PDFormXObject()
        engine = _RecordingEngine(_Resources({_name("Fm0"): form}))

        def boom(_form: Any) -> None:
            raise ValueError("boom")

        engine.show_form = boom  # type: ignore[assignment]
        with pytest.raises(ValueError, match="boom"):
            InvokeNamedXObject(engine).process(_op(), [_name("Fm0")])
        # finally must still restore the level even on exception
        assert engine.level == 0

    def test_self_referencing_form_terminates_at_cap(self) -> None:
        """A form whose content invokes itself must terminate via the
        level cap instead of overflowing the Python stack. We model the
        self-reference by re-dispatching ``Do`` from inside ``show_form``."""
        form = PDFormXObject()
        res = _Resources({_name("Fm0"): form})
        engine = _RecordingEngine(res)
        handler = InvokeNamedXObject(engine)

        def recurse(_form: Any) -> None:
            engine.events.append(("show_form", _form, engine.level))
            handler.process(_op(), [_name("Fm0")])

        engine.show_form = recurse  # type: ignore[assignment]
        handler.process(_op(), [_name("Fm0")])
        # The guard caps the depth at 50; recursion unwinds cleanly.
        assert engine.max_level == 51  # 51 is the first level that bails
        assert engine.level == 0  # fully unwound
        # show_form fired for every level that passed the cap (1..50)
        assert len([e for e in engine.events if e[0] == "show_form"]) == 50


# ==========================================================================
# Text-extraction ``Do`` (DrawObject) — image short-circuit + guard
# ==========================================================================
class TestTextDrawObject:
    def test_empty_operands_raises(self) -> None:
        with pytest.raises(MissingOperandException):
            DrawObject(_RecordingEngine(_Resources())).process(_op(), [])

    def test_non_name_silently_skips(self) -> None:
        engine = _RecordingEngine(_Resources())
        DrawObject(engine).process(_op(), [COSInteger(1)])
        assert engine.events == []

    def test_image_xobject_short_circuited(self) -> None:
        # Text extraction never decodes images: the is_image_x_object
        # short-circuit returns before getXObject.
        img = PDImageXObject()
        res = _Resources({_name("Im0"): img})
        res.image_names.add(_name("Im0"))
        engine = _RecordingEngine(res)
        DrawObject(engine).process(_op(), [_name("Im0")])
        assert engine.events == []

    def test_form_xobject_shown(self) -> None:
        form = PDFormXObject()
        res = _Resources({_name("Fm0"): form})
        engine = _RecordingEngine(res)
        DrawObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == [("show_form", form, 1)]
        assert engine.level == 0

    def test_transparency_group_shown(self) -> None:
        group = PDTransparencyGroup()
        res = _Resources({_name("Gs0"): group})
        engine = _RecordingEngine(res)
        DrawObject(engine).process(_op(), [_name("Gs0")])
        assert engine.events == [("show_transparency_group", group, 1)]

    def test_form_over_cap_skipped(self) -> None:
        form = PDFormXObject()
        engine = _RecordingEngine(_Resources({_name("Fm0"): form}))
        engine.level = 50
        DrawObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == []
        assert engine.level == 50

    def test_none_resources_noop(self) -> None:
        engine = _RecordingEngine(resources=None)
        DrawObject(engine).process(_op(), [_name("Fm0")])
        assert engine.events == []

    def test_get_name(self) -> None:
        assert DrawObject(_RecordingEngine()).get_name() == "Do"


# ==========================================================================
# Both handlers share the same level discipline — parametric round-out
# ==========================================================================
@pytest.mark.parametrize("handler_cls", [InvokeNamedXObject, DrawObject])
class TestSharedLevelDiscipline:
    def test_level_balanced_after_nested_forms(self, handler_cls: type) -> None:
        """Form A invokes form B: each Do bumps/restores its own level, so
        after the whole walk the engine level returns to 0."""
        form_a = PDFormXObject()
        form_b = PDFormXObject()
        res = _Resources({_name("FmA"): form_a, _name("FmB"): form_b})
        engine = _RecordingEngine(res)
        handler = handler_cls(engine)

        def show_form(form: Any) -> None:
            engine.events.append(("show_form", form, engine.level))
            if form is form_a:
                handler.process(_op(), [_name("FmB")])  # nested Do

        engine.show_form = show_form  # type: ignore[assignment]
        handler.process(_op(), [_name("FmA")])
        # FmA at level 1, FmB nested at level 2, then fully unwound.
        levels = [e[2] for e in engine.events if e[0] == "show_form"]
        assert levels == [1, 2]
        assert engine.level == 0

    def test_missing_name_does_not_leak_level(self, handler_cls: type) -> None:
        # Graphics raises, text no-ops, but neither must bump the level.
        engine = _RecordingEngine(_Resources())
        handler = handler_cls(engine)
        with contextlib.suppress(MissingResourceException):
            handler.process(_op(), [_name("Gone")])
        assert engine.level == 0


# ==========================================================================
# Real PDFStreamEngine — resource-stack push/pop around process_stream
# (upstream ``PDFStreamEngine.processStream``: swap in the stream's
# ``/Resources``, restore the parent's in the ``finally``)
# ==========================================================================
class _FakeContentStream(PDContentStream):
    """Minimal PDContentStream backed by literal bytes + an opaque
    resources sentinel (the engine only stores/restores the reference)."""

    def __init__(self, data: bytes, resources: Any) -> None:
        self._data = data
        self._resources = resources

    def get_contents(self) -> Any:  # pragma: no cover - unused path
        raise NotImplementedError

    def get_contents_for_random_access(self) -> RandomAccessReadBuffer:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> Any:
        return self._resources

    def get_bbox(self) -> Any:  # pragma: no cover - unused path
        return None

    def get_matrix(self) -> Any:  # pragma: no cover - unused path
        return None


class _ResourceProbe(OperatorProcessor):
    """A custom operator that records the engine's current resources at
    dispatch time, so a test can prove the stream's resources were in
    effect during the inner walk."""

    OPERATOR_NAME = "PROBE"

    def __init__(self, sink: list[Any]) -> None:
        super().__init__()
        self._sink = sink

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        ctx = self._context
        self._sink.append(ctx.get_resources() if ctx is not None else None)


class TestEngineResourceStack:
    def _engine_with_probe(self, sink: list[Any]) -> PDFStreamEngine:
        engine = PDFStreamEngine()
        engine.add_operator(_ResourceProbe(sink))
        return engine

    def test_stream_resources_pushed_during_walk(self) -> None:
        sink: list[Any] = []
        engine = self._engine_with_probe(sink)
        parent = object()
        engine._resources = parent  # parent resources in effect
        child = object()
        stream = _FakeContentStream(b"PROBE\n", child)
        engine.process_stream(stream)
        # the probe saw the *stream's* resources, not the parent's
        assert sink == [child]

    def test_parent_resources_restored_after_walk(self) -> None:
        sink: list[Any] = []
        engine = self._engine_with_probe(sink)
        parent = object()
        engine._resources = parent
        stream = _FakeContentStream(b"PROBE\n", object())
        engine.process_stream(stream)
        # parent resources restored on the way out
        assert engine.get_resources() is parent

    def test_none_stream_resources_keep_parent(self) -> None:
        sink: list[Any] = []
        engine = self._engine_with_probe(sink)
        parent = object()
        engine._resources = parent
        stream = _FakeContentStream(b"PROBE\n", None)
        engine.process_stream(stream)
        # /Resources is None -> the parent's resources stay in effect
        assert sink == [parent]
        assert engine.get_resources() is parent

    def test_resources_restored_even_on_error(self) -> None:
        engine = PDFStreamEngine()

        class _Boom(OperatorProcessor):
            OPERATOR_NAME = "BOOM"

            def process(
                self, operator: Operator, operands: list[COSBase]
            ) -> None:
                raise ValueError("kaboom")

        engine.add_operator(_Boom())
        parent = object()
        engine._resources = parent
        stream = _FakeContentStream(b"BOOM\n", object())
        with pytest.raises(ValueError, match="kaboom"):
            engine.process_stream(stream)
        # finally-clause restores the parent resources even after a raise
        assert engine.get_resources() is parent

    def test_nested_streams_restore_each_level(self) -> None:
        # Stream A's content invokes a nested process_stream(B); after B
        # completes, A's resources are back in effect, and after A, the
        # original parent.
        sink: list[Any] = []
        engine = PDFStreamEngine()
        res_b = object()
        res_a = object()
        parent = object()
        engine._resources = parent
        # B carries an inert operator so descending into it does not re-fire
        # the nester (which is keyed on the "NEST" token only).
        stream_b = _FakeContentStream(b"PROBE\n", res_b)
        engine.add_operator(_ResourceProbe([]))  # inert PROBE sink

        class _Nester(OperatorProcessor):
            OPERATOR_NAME = "NEST"

            def process(
                self, operator: Operator, operands: list[COSBase]
            ) -> None:
                # record A's resources, then descend into B
                sink.append(engine.get_resources())
                engine.process_stream(stream_b)
                sink.append(engine.get_resources())  # back to A

        engine.add_operator(_Nester())
        stream_a = _FakeContentStream(b"NEST\n", res_a)
        engine.process_stream(stream_a)
        # saw A before descent, A again after B returned
        assert sink == [res_a, res_a]
        # but B's resources never leaked past its own walk
        assert engine.get_resources() is parent
