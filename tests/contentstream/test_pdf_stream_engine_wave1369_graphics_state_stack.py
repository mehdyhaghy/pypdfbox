"""Wave 1369 — PDFStreamEngine graphics-state stack + recursion-guard parity.

Exercises:

- ``save_graphics_stack`` / ``restore_graphics_stack`` fence semantics
  (snapshot returns the previous stack, replaces the live one with a
  one-frame stack seeded by a copy of the previously top frame).
- Recursion-guard via ``increase_level`` / ``decrease_level`` and the
  defensive zero-floor on ``decrease_level`` (mirrors upstream's
  ``decreaseLevel`` "level is below 0" branch — should *not* throw).
- ``set_context`` rebind invariant on every registered processor (the
  engine-bound :class:`OperatorProcessor` always sees the engine that
  owns its registry entry).
- ``set_resources`` push semantics so nested form/pattern handlers can
  swap a frame without re-implementing the dispatch surface.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import (
    Operator,
    OperatorProcessor,
    PDFStreamEngine,
)
from pypdfbox.cos import COSBase
from pypdfbox.pdmodel import PDResources


class _NameOnly(OperatorProcessor):
    """Minimal processor used to assert the ``set_context`` rebind path."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator, operands

    def get_name(self) -> str:
        return self._name


# ---------- save_graphics_stack / restore_graphics_stack ----------


def test_save_graphics_stack_returns_snapshot_and_seeds_inner_stack() -> None:
    """Inner stream must see a fresh stack whose sole frame is a copy of
    the previously top frame (so a child save/restore can't corrupt the
    parent's state). The outer caller gets the full snapshot back so it
    can restore later."""
    engine = PDFStreamEngine()
    # Push two distinct frames.
    frame_a: dict[str, Any] = {"id": "A"}
    frame_b: dict[str, Any] = {"id": "B"}
    engine._graphics_stack = [frame_a, frame_b]

    snapshot = engine.save_graphics_stack()

    # Snapshot returns the *outer* (previous) stack reference.
    assert snapshot == [frame_a, frame_b]
    # Engine is now seeded with a one-frame stack — a *copy* of the
    # previously top frame, not the same instance.
    assert engine.get_graphics_stack_size() == 1
    top = engine.get_graphics_state()
    assert top == {"id": "B"}
    assert top is not frame_b  # copy.copy made a fresh instance


def test_save_graphics_stack_empty_yields_empty_snapshot() -> None:
    """An empty stack stays empty after save — nothing to seed from."""
    engine = PDFStreamEngine()
    snapshot = engine.save_graphics_stack()
    assert snapshot == []
    assert engine.get_graphics_stack_size() == 0


def test_save_graphics_stack_uncopyable_frame_falls_back_to_reference() -> None:
    """When ``copy.copy`` raises ``TypeError`` (un-copyable object), the
    seeded inner frame falls back to the same reference. Mirrors the
    engine's defensive ``try/except`` around ``copy.copy``."""

    class _NoCopy:
        def __copy__(self) -> Any:
            raise TypeError("not copyable")

    frame = _NoCopy()
    engine = PDFStreamEngine()
    engine._graphics_stack = [frame]
    engine.save_graphics_stack()
    assert engine.get_graphics_state() is frame  # fallback to ref


def test_restore_graphics_stack_replaces_live_stack_wholesale() -> None:
    """``restore_graphics_stack`` replaces the engine's live stack with
    the snapshot — no merging, no append."""
    engine = PDFStreamEngine()
    engine._graphics_stack = [{"id": "outer"}]
    snapshot = engine.save_graphics_stack()
    # Mutate the inner stack so we can prove the restore wipes it.
    engine._graphics_stack = [{"id": "inner-1"}, {"id": "inner-2"}]
    engine.restore_graphics_stack(snapshot)
    assert engine._graphics_stack is snapshot
    assert engine.get_graphics_state() == {"id": "outer"}


def test_save_then_restore_round_trip_preserves_outer_state() -> None:
    """End-to-end fence: an outer save, an inner mutation, then restore
    must leave the outer state identical to before."""
    engine = PDFStreamEngine()
    before = [{"depth": 0}, {"depth": 1}]
    engine._graphics_stack = list(before)
    snapshot = engine.save_graphics_stack()
    # Inner stream pushes/pops freely on the seeded one-frame stack.
    engine._graphics_stack.append({"depth": 99})
    engine._graphics_stack.pop()
    engine.restore_graphics_stack(snapshot)
    assert engine._graphics_stack == before


# ---------- level / recursion guard ----------


def test_get_level_starts_at_zero() -> None:
    engine = PDFStreamEngine()
    assert engine.get_level() == 0


def test_increase_level_and_decrease_level_round_trip() -> None:
    engine = PDFStreamEngine()
    engine.increase_level()
    engine.increase_level()
    assert engine.get_level() == 2
    engine.decrease_level()
    engine.decrease_level()
    assert engine.get_level() == 0


def test_decrease_level_floors_at_zero_does_not_raise() -> None:
    """Mirrors upstream's defensive ``decreaseLevel`` branch — when the
    counter is already at 0 the engine logs an error and pins the level
    at 0 rather than going negative (or raising)."""
    engine = PDFStreamEngine()
    # No prior increase — should silently floor.
    engine.decrease_level()
    engine.decrease_level()
    assert engine.get_level() == 0


# ---------- set_context rebind across registry entries ----------


def test_add_operator_rebinds_processor_context_to_engine() -> None:
    """Every ``add_operator`` call must re-bind the processor's context
    so ``processor.get_context()`` is the engine that owns the entry —
    even when the processor was previously bound to a different engine."""
    engine_a = PDFStreamEngine()
    engine_b = PDFStreamEngine()
    proc = _NameOnly("Tj")
    engine_a.add_operator(proc)
    assert proc.get_context() is engine_a
    engine_b.add_operator(proc)
    assert proc.get_context() is engine_b


def test_register_operator_processor_also_rebinds_context() -> None:
    """``register_operator_processor`` uses an explicit key but must
    still re-bind the context — same invariant as ``add_operator``."""
    engine = PDFStreamEngine()
    proc = _NameOnly("Tj")
    engine.register_operator_processor("alias", proc)
    assert engine.get_operators()["alias"] is proc
    assert proc.get_context() is engine


def test_processor_get_context_raises_when_unbound() -> None:
    """The engine-bound :class:`OperatorProcessor` ABC raises when
    ``get_context`` is called without a prior bind — fail-fast for
    accidental misuse, matching upstream's ``final`` field invariant."""
    proc = _NameOnly("Tj")
    import pytest

    with pytest.raises(RuntimeError, match="no PDFStreamEngine context"):
        proc.get_context()


# ---------- set_resources push semantics ----------


def test_set_resources_pushes_new_active_frame_and_preserves_prior() -> None:
    """``set_resources`` saves the prior frame on ``_resources_stack``
    so a nested form-XObject handler can restore later."""
    engine = PDFStreamEngine()
    outer = PDResources()
    inner = PDResources()
    engine._resources = outer
    engine.set_resources(inner)
    assert engine.get_resources() is inner
    assert engine._resources_stack[-1] is outer


# ---------- transform_width / set_initial_matrix base surface ----------


def test_transform_width_default_returns_input_unchanged() -> None:
    """Base engine has no CTM — ``transform_width`` is the identity."""
    engine = PDFStreamEngine()
    assert engine.transform_width(7.5) == 7.5
    assert engine.transform_width(0) == 0.0


def test_set_and_get_initial_matrix_round_trip() -> None:
    """The initial-matrix slot is opaque on the base engine — anything
    passed in comes back out unchanged."""
    engine = PDFStreamEngine()
    assert engine.get_initial_matrix() is None
    sentinel = object()
    engine.set_initial_matrix(sentinel)
    assert engine.get_initial_matrix() is sentinel


# ---------- should_process_color_operators flag ----------


def test_should_process_color_operators_default_true() -> None:
    """Colour-operator gating defaults to ``True``; the Type3 / tiling-
    pattern code paths flip it via the private setter."""
    engine = PDFStreamEngine()
    assert engine.is_should_process_color_operators() is True


def test_should_process_color_operators_setter_round_trip() -> None:
    engine = PDFStreamEngine()
    engine._set_should_process_color_operators(False)
    assert engine.is_should_process_color_operators() is False
    engine._set_should_process_color_operators(True)
    assert engine.is_should_process_color_operators() is True
