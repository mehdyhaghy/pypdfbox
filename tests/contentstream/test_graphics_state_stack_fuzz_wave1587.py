"""Fuzz/parity tests for the ``q`` / ``Q`` graphics-state save/restore
stack and the ``cm`` matrix-concatenation operator.

Surface mirrored:

* ``org.apache.pdfbox.contentstream.operator.state.Save`` (``q``)
* ``org.apache.pdfbox.contentstream.operator.state.Restore`` (``Q``)
* ``org.apache.pdfbox.contentstream.operator.state.Concatenate`` (``cm``)
* ``PDFStreamEngine``'s graphics-state stack (``saveGraphicsState`` /
  ``restoreGraphicsState`` / ``getGraphicsStackSize`` / ``transform``).

Upstream behaviour being pinned:

* ``q`` pushes a **clone** of the current graphics state, so mutating the
  current state after ``q`` leaves the saved frame untouched.
* ``Q`` pops the top frame and restores the previous one (CTM, line width,
  colour, etc.).
* ``Q`` on a stack of depth 1 (or empty) does **not** crash — ``Restore``
  raises ``EmptyGraphicsStackException`` (an ``IOException`` subclass) which
  ``PDFStreamEngine.operatorException`` catches and logs.
* ``cm`` concatenates the new matrix onto the CTM such that
  ``CTM = newMatrix.multiply(oldCTM)`` (``Matrix.concatenate`` semantics:
  ``self = matrix * self``).

The tests drive the *real* operator classes through a recording
``PDFStreamEngine`` subclass that carries a concrete ``PDGraphicsState``
stack — the same contract the rendering subclass fulfils.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.state.concatenate import Concatenate
from pypdfbox.contentstream.operator.state.empty_graphics_stack_exception import (
    EmptyGraphicsStackException,
)
from pypdfbox.contentstream.operator.state.restore import Restore
from pypdfbox.contentstream.operator.state.save import Save
from pypdfbox.cos import COSBase, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState
from pypdfbox.util.matrix import Matrix


class GraphicsStateEngine(PDFStreamEngine):
    """A ``PDFStreamEngine`` that owns a concrete ``PDGraphicsState``
    stack, mirroring upstream's rendering subclass contract.

    The base engine ships ``save_graphics_state`` / ``restore_graphics_state``
    / ``transform`` as no-ops (cluster #2 has no concrete state); a real
    subclass overrides them exactly like this. Seeding the stack with one
    frame matches upstream ``initPage`` pushing a single initial
    ``PDGraphicsState``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._graphics_stack = [PDGraphicsState()]
        self.save_count = 0
        self.restore_count = 0

    def get_graphics_state(self) -> PDGraphicsState:
        return self._graphics_stack[-1]

    def save_graphics_state(self) -> None:
        self.save_count += 1
        self._graphics_stack.append(self._graphics_stack[-1].clone())

    def restore_graphics_state(self) -> None:
        self.restore_count += 1
        self._graphics_stack.pop()

    def transform(self, matrix: Any) -> None:
        # matrix is a 6-tuple (a b c d e f); upstream Concatenate routes
        # context.transform(matrix) -> CTM.concatenate(matrix).
        new_matrix = Matrix(*matrix)
        self.get_graphics_state().get_current_transformation_matrix().concatenate(
            new_matrix
        )


def make_engine() -> GraphicsStateEngine:
    engine = GraphicsStateEngine()
    engine.add_operator(Save())
    engine.add_operator(Restore())
    engine.add_operator(Concatenate())
    return engine


def num(value: float) -> COSFloat:
    return COSFloat(value)


def op(name: str) -> Operator:
    return Operator.get_operator(name)


def run(engine: GraphicsStateEngine, name: str, *operands: COSBase) -> None:
    """Dispatch via the engine so EmptyGraphicsStackException is routed
    through operatorException exactly like the real parse loop."""
    engine.process_operator(op(name), list(operands))


def ctm(engine: GraphicsStateEngine) -> Matrix:
    return engine.get_graphics_state().get_current_transformation_matrix()


# --------------------------------------------------------------------------
# q pushes a clone, not a shared reference
# --------------------------------------------------------------------------


def test_save_pushes_and_grows_stack() -> None:
    engine = make_engine()
    assert engine.get_graphics_stack_size() == 1
    run(engine, "q")
    assert engine.get_graphics_stack_size() == 2
    assert engine.save_count == 1


def test_save_pushes_clone_not_same_object() -> None:
    engine = make_engine()
    before = engine.get_graphics_state()
    run(engine, "q")
    after = engine.get_graphics_state()
    assert after is not before


def test_mutating_line_width_after_save_does_not_touch_saved() -> None:
    engine = make_engine()
    engine.get_graphics_state().set_line_width(3.0)
    run(engine, "q")
    # mutate the current (top) frame
    engine.get_graphics_state().set_line_width(9.0)
    assert engine.get_graphics_state().get_line_width() == 9.0
    run(engine, "Q")
    # restored frame keeps the pre-q width
    assert engine.get_graphics_state().get_line_width() == 3.0


def test_mutating_color_after_save_does_not_touch_saved() -> None:
    engine = make_engine()
    engine.get_graphics_state().set_non_stroking_color("RED")
    run(engine, "q")
    engine.get_graphics_state().set_non_stroking_color("BLUE")
    run(engine, "Q")
    assert engine.get_graphics_state().get_non_stroking_color() == "RED"


def test_save_clones_ctm_independently() -> None:
    engine = make_engine()
    run(engine, "q")
    # mutate the cloned CTM on the top frame
    ctm(engine).concatenate(Matrix.get_scale_instance(2.0, 2.0))
    saved = engine._graphics_stack[-2]
    # the saved (lower) frame's CTM is still identity
    assert saved.get_current_transformation_matrix() == Matrix()


def test_save_clone_ctm_is_distinct_object() -> None:
    engine = make_engine()
    before_ctm = ctm(engine)
    run(engine, "q")
    after_ctm = ctm(engine)
    assert after_ctm is not before_ctm


def test_save_clones_text_state_independently() -> None:
    engine = make_engine()
    engine.get_graphics_state().get_text_state().set_font_size(11.0)
    run(engine, "q")
    engine.get_graphics_state().get_text_state().set_font_size(22.0)
    run(engine, "Q")
    assert engine.get_graphics_state().get_text_state().get_font_size() == 11.0


# --------------------------------------------------------------------------
# Q restores the saved state
# --------------------------------------------------------------------------


def test_restore_pops_stack() -> None:
    engine = make_engine()
    run(engine, "q")
    run(engine, "Q")
    assert engine.get_graphics_stack_size() == 1
    assert engine.restore_count == 1


def test_restore_returns_saved_frame_object() -> None:
    engine = make_engine()
    original = engine.get_graphics_state()
    run(engine, "q")
    run(engine, "Q")
    assert engine.get_graphics_state() is original


@pytest.mark.parametrize("width", [0.5, 1.0, 2.75, 12.0, 100.0])
def test_restore_restores_line_width(width: float) -> None:
    engine = make_engine()
    engine.get_graphics_state().set_line_width(width)
    run(engine, "q")
    engine.get_graphics_state().set_line_width(width + 5.0)
    run(engine, "Q")
    assert engine.get_graphics_state().get_line_width() == width


def test_restore_restores_full_ctm() -> None:
    engine = make_engine()
    ctm(engine).concatenate(Matrix.get_translate_instance(10.0, 20.0))
    expected = ctm(engine).clone()
    run(engine, "q")
    ctm(engine).concatenate(Matrix.get_scale_instance(3.0, 3.0))
    run(engine, "Q")
    assert ctm(engine) == expected


# --------------------------------------------------------------------------
# nested q/q/Q/Q
# --------------------------------------------------------------------------


def test_nested_save_restore_depth() -> None:
    engine = make_engine()
    run(engine, "q")
    run(engine, "q")
    run(engine, "q")
    assert engine.get_graphics_stack_size() == 4
    run(engine, "Q")
    run(engine, "Q")
    run(engine, "Q")
    assert engine.get_graphics_stack_size() == 1


def test_nested_save_restore_round_trips_state() -> None:
    engine = make_engine()
    engine.get_graphics_state().set_line_width(1.0)
    run(engine, "q")
    engine.get_graphics_state().set_line_width(2.0)
    run(engine, "q")
    engine.get_graphics_state().set_line_width(3.0)
    assert engine.get_graphics_state().get_line_width() == 3.0
    run(engine, "Q")
    assert engine.get_graphics_state().get_line_width() == 2.0
    run(engine, "Q")
    assert engine.get_graphics_state().get_line_width() == 1.0


def test_interleaved_save_concat_restore() -> None:
    engine = make_engine()
    run(engine, "q")
    run(engine, "cm", num(2.0), num(0.0), num(0.0), num(2.0), num(0.0), num(0.0))
    run(engine, "q")
    run(engine, "cm", num(1.0), num(0.0), num(0.0), num(1.0), num(5.0), num(5.0))
    run(engine, "Q")
    # back to just the scale frame
    assert ctm(engine) == Matrix.get_scale_instance(2.0, 2.0)
    run(engine, "Q")
    assert ctm(engine) == Matrix()


# --------------------------------------------------------------------------
# unbalanced Q (empty / depth-1 stack) does not crash
# --------------------------------------------------------------------------


def test_restore_on_depth_one_does_not_crash() -> None:
    engine = make_engine()
    assert engine.get_graphics_stack_size() == 1
    # routed through operatorException -> logged, swallowed
    run(engine, "Q")
    assert engine.get_graphics_stack_size() == 1
    assert engine.restore_count == 0


def test_many_unbalanced_restores_do_not_underflow() -> None:
    engine = make_engine()
    for _ in range(10):
        run(engine, "Q")
    assert engine.get_graphics_stack_size() == 1


def test_restore_operator_raises_when_called_directly_on_depth_one() -> None:
    engine = make_engine()
    restore = Restore()
    restore.set_context(engine)
    with pytest.raises(EmptyGraphicsStackException):
        restore.process(op("Q"), [])


def test_excess_restores_after_saves_clamp_at_one() -> None:
    engine = make_engine()
    run(engine, "q")
    run(engine, "q")
    # three Q for two q — the third is unbalanced and ignored
    run(engine, "Q")
    run(engine, "Q")
    run(engine, "Q")
    assert engine.get_graphics_stack_size() == 1


# --------------------------------------------------------------------------
# cm concatenation order: CTM = newMatrix.multiply(oldCTM)
# --------------------------------------------------------------------------


def test_concat_translate_onto_identity() -> None:
    engine = make_engine()
    run(engine, "cm", num(1.0), num(0.0), num(0.0), num(1.0), num(7.0), num(13.0))
    assert ctm(engine) == Matrix.get_translate_instance(7.0, 13.0)


def test_concat_scale_onto_identity() -> None:
    engine = make_engine()
    run(engine, "cm", num(3.0), num(0.0), num(0.0), num(4.0), num(0.0), num(0.0))
    assert ctm(engine) == Matrix.get_scale_instance(3.0, 4.0)


def test_concat_translate_then_scale_order() -> None:
    """``cm T`` then ``cm S`` must compose as ``S * (T * I)`` so that a
    point first scales then translates in the resulting CTM. Pin the exact
    upstream order ``CTM = newMatrix.multiply(oldCTM)``."""
    engine = make_engine()
    translate = (1.0, 0.0, 0.0, 1.0, 10.0, 0.0)
    scale = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    run(engine, "cm", *[num(v) for v in translate])
    run(engine, "cm", *[num(v) for v in scale])
    # Reference: apply concatenate twice in the same order on a fresh CTM.
    ref = Matrix()
    ref.concatenate(Matrix(*translate))
    ref.concatenate(Matrix(*scale))
    assert ctm(engine) == ref


def test_concat_order_matches_multiply_new_old() -> None:
    engine = make_engine()
    old = (1.0, 0.0, 0.0, 1.0, 5.0, 5.0)
    new = (0.5, 0.0, 0.0, 0.5, 1.0, 2.0)
    run(engine, "cm", *[num(v) for v in old])
    run(engine, "cm", *[num(v) for v in new])
    expected = Matrix(*new).multiply(Matrix(*old))
    assert ctm(engine) == expected


def test_concat_order_is_not_commutative() -> None:
    engine_a = make_engine()
    engine_b = make_engine()
    t = (1.0, 0.0, 0.0, 1.0, 10.0, 0.0)
    s = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    run(engine_a, "cm", *[num(v) for v in t])
    run(engine_a, "cm", *[num(v) for v in s])
    run(engine_b, "cm", *[num(v) for v in s])
    run(engine_b, "cm", *[num(v) for v in t])
    assert ctm(engine_a) != ctm(engine_b)


def test_concat_applies_to_point_transform() -> None:
    engine = make_engine()
    # scale by 2 then translate by (3, 4)
    run(engine, "cm", num(2.0), num(0.0), num(0.0), num(2.0), num(0.0), num(0.0))
    run(engine, "cm", num(1.0), num(0.0), num(0.0), num(1.0), num(3.0), num(4.0))
    # A point at (1, 1): translate happens in the just-scaled frame, so
    # the composite maps (1,1) -> first translate in inner space then scale.
    point = ctm(engine).transform_point(1.0, 1.0)
    # Reference via the same concatenation order.
    ref = Matrix()
    ref.concatenate(Matrix(2.0, 0.0, 0.0, 2.0, 0.0, 0.0))
    ref.concatenate(Matrix(1.0, 0.0, 0.0, 1.0, 3.0, 4.0))
    assert point == ref.transform_point(1.0, 1.0)


@pytest.mark.parametrize(
    ("a", "b", "c", "d", "e", "f"),
    [
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0, 2.0, 0.0, 0.0),
        (1.0, 0.0, 0.0, 1.0, -5.0, 8.0),
        (0.0, 1.0, -1.0, 0.0, 0.0, 0.0),
        (1.5, 0.25, -0.25, 1.5, 3.0, -3.0),
    ],
)
def test_concat_single_matches_concatenate(
    a: float, b: float, c: float, d: float, e: float, f: float
) -> None:
    engine = make_engine()
    run(engine, "cm", num(a), num(b), num(c), num(d), num(e), num(f))
    ref = Matrix()
    ref.concatenate(Matrix(a, b, c, d, e, f))
    assert ctm(engine) == ref


# --------------------------------------------------------------------------
# q then cm then Q restores the pre-cm CTM
# --------------------------------------------------------------------------


def test_save_concat_restore_restores_pre_cm_ctm() -> None:
    engine = make_engine()
    ctm(engine).concatenate(Matrix.get_translate_instance(1.0, 1.0))
    pre = ctm(engine).clone()
    run(engine, "q")
    run(engine, "cm", num(9.0), num(0.0), num(0.0), num(9.0), num(0.0), num(0.0))
    assert ctm(engine) != pre
    run(engine, "Q")
    assert ctm(engine) == pre


def test_save_concat_restore_keeps_outer_concat() -> None:
    engine = make_engine()
    run(engine, "cm", num(2.0), num(0.0), num(0.0), num(2.0), num(0.0), num(0.0))
    run(engine, "q")
    run(engine, "cm", num(1.0), num(0.0), num(0.0), num(1.0), num(100.0), num(0.0))
    run(engine, "Q")
    assert ctm(engine) == Matrix.get_scale_instance(2.0, 2.0)


# --------------------------------------------------------------------------
# cm operand validation (parity with upstream Concatenate)
# --------------------------------------------------------------------------


def test_concat_too_few_operands_raises_missing_operand() -> None:
    from pypdfbox.contentstream import MissingOperandException

    engine = make_engine()
    concat = Concatenate()
    concat.set_context(engine)
    with pytest.raises(MissingOperandException):
        concat.process(op("cm"), [num(1.0), num(0.0), num(0.0)])


def test_concat_non_number_operand_is_silently_skipped() -> None:
    engine = make_engine()
    run(
        engine,
        "cm",
        num(2.0),
        num(0.0),
        num(0.0),
        num(2.0),
        num(0.0),
        COSName.get_pdf_name("Bogus"),
    )
    # malformed -> CTM untouched (still identity)
    assert ctm(engine) == Matrix()


def test_concat_accepts_integer_operands() -> None:
    engine = make_engine()
    run(
        engine,
        "cm",
        COSInteger.get(1),
        COSInteger.get(0),
        COSInteger.get(0),
        COSInteger.get(1),
        COSInteger.get(4),
        COSInteger.get(6),
    )
    assert ctm(engine) == Matrix.get_translate_instance(4.0, 6.0)


# --------------------------------------------------------------------------
# operator identity / names
# --------------------------------------------------------------------------


def test_operator_names() -> None:
    assert Save().get_name() == "q"
    assert Restore().get_name() == "Q"
    assert Concatenate().get_name() == "cm"


def test_concat_fallback_path_builds_matrix_from_tuple() -> None:
    """When the context has no ``transform`` hook, ``Concatenate`` falls
    back to ``CTM.concatenate(...)``. Upstream concatenates a *Matrix*, not
    the raw six floats; passing the tuple straight through would crash
    ``Matrix.concatenate`` (which reads ``matrix._single``). Regression for
    the fallback path of ``state.Concatenate``."""

    class _NoTransformCtx:
        def __init__(self) -> None:
            self._gs = PDGraphicsState()

        def get_graphics_state(self) -> PDGraphicsState:
            return self._gs

    concat = Concatenate()
    concat.set_context(_NoTransformCtx())
    concat.process(
        op("cm"),
        [num(2.0), num(0.0), num(0.0), num(2.0), num(3.0), num(4.0)],
    )
    result = concat._context.get_graphics_state().get_current_transformation_matrix()
    assert result == Matrix(2.0, 0.0, 0.0, 2.0, 3.0, 4.0)


def test_save_restore_with_no_context_is_noop() -> None:
    save = Save()
    restore = Restore()
    # no context bound -> _context is None -> nothing happens, no crash
    save.process(op("q"), [])
    # Restore with no context returns early (does not raise)
    restore.process(op("Q"), [])
