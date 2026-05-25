"""Branch coverage for ``SetStrokingColorSpace`` / ``SetNonStrokingColorSpace`` — wave 1400.

Closes residual partial branches in:

* ``pypdfbox/contentstream/operator/color/set_stroking_color_space.py``:
  - color space lacking ``get_initial_color`` attribute (89 → 67).
  - context lacking ``set_stroking_color`` attribute (97 → 67).
  - ``_set_attr`` invoked with ``target=None`` (102 → 100).

* ``pypdfbox/contentstream/operator/color/set_non_stroking_color_space.py``:
  the symmetric three branches (78 → 54, 88 → 54, 93 → 91).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_space import (
    SetStrokingColorSpace,
)
from pypdfbox.cos import COSName

# ----------------------------------------------------------------------
# Shared scaffolding
# ----------------------------------------------------------------------


class _MinimalColorSpace:
    """Colour space stub without ``get_initial_color`` — exercises the
    ``getattr(..., None) is None`` short-circuit."""


class _ColorSpaceWithInitial:
    """Colour space stub with a ``get_initial_color`` that returns a
    sentinel — used to drive the engine_setter / color_setter branches."""

    def __init__(self, sentinel: object) -> None:
        self._sentinel = sentinel

    def get_initial_color(self) -> object:
        return self._sentinel


class _FakeResources:
    def __init__(self, color_space: object) -> None:
        self._cs = color_space

    def get_color_space(self, name: COSName, was_default: bool = False) -> object:
        del name, was_default
        return self._cs


class _BareGraphicsState:
    """Graphics state object that lacks the setter pair — forces the
    ``_set_attr`` fallback (setattr path) for both color-space and
    color writes."""

    def __init__(self) -> None:
        self.stroking_color_space: object | None = None
        self.non_stroking_color_space: object | None = None
        self.stroking_color: object | None = None
        self.non_stroking_color: object | None = None


class _BareEngine:
    """Plain stand-in context — NOT a PDFStreamEngine subclass — so the
    inherited ``set_stroking_color`` / ``set_non_stroking_color``
    methods aren't present and ``getattr(ctx, ..., None)`` returns None.

    Implements the ducktyped surface SetStrokingColorSpace consults.
    """

    def __init__(self, resources: object) -> None:
        self._resources_obj = resources
        self._gs = _BareGraphicsState()

    def get_resources(self) -> Any:
        return self._resources_obj

    def get_graphics_state(self) -> _BareGraphicsState:
        return self._gs

    def is_should_process_color_operators(self) -> bool:
        return True

    # Deliberately NO set_stroking_color / set_non_stroking_color
    # methods — keeps the engine-setter branch unreachable.


# ----------------------------------------------------------------------
# Stroking — three branches
# ----------------------------------------------------------------------


def test_set_stroking_color_space_skips_get_initial_when_attr_missing() -> None:
    """When the resolved colour space lacks ``get_initial_color`` the
    helper must skip the initial-colour reset block.

    Closes branch (89 → 67)."""
    cs = _MinimalColorSpace()
    engine = _BareEngine(_FakeResources(cs))
    processor = SetStrokingColorSpace()
    processor.set_context(engine)  # type: ignore[arg-type]
    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS1")],
    )
    # Colour space did get installed via the setattr fallback path.
    assert engine._gs.stroking_color_space is cs  # noqa: SLF001


def test_set_stroking_color_space_skips_engine_setter_when_missing() -> None:
    """Even when the colour space exposes ``get_initial_color``, if the
    bound context lacks ``set_stroking_color`` the engine-side
    notification is skipped.

    Closes branch (97 → 67)."""
    sentinel = object()
    cs = _ColorSpaceWithInitial(sentinel)
    engine = _BareEngine(_FakeResources(cs))
    processor = SetStrokingColorSpace()
    processor.set_context(engine)  # type: ignore[arg-type]
    processor.process(
        Operator.get_operator("CS"),
        [COSName.get_pdf_name("CS1")],
    )
    # Initial colour landed on the graphics state via the setattr
    # fallback (graphics state also lacks the setter pair).
    assert engine._gs.stroking_color is sentinel  # noqa: SLF001


def test_set_stroking_color_space_set_attr_with_none_target_is_noop() -> None:
    """``_set_attr(None, ..., ...)`` must silently return.

    Closes branch (102 → 100)."""
    # No exception when target is None.
    SetStrokingColorSpace._set_attr(None, "stroking_color_space", object())  # noqa: SLF001


# ----------------------------------------------------------------------
# Non-stroking — symmetric three branches
# ----------------------------------------------------------------------


def test_set_non_stroking_color_space_skips_get_initial_when_attr_missing() -> None:
    """Closes branch (78 → 54) in set_non_stroking_color_space."""
    cs = _MinimalColorSpace()
    engine = _BareEngine(_FakeResources(cs))
    processor = SetNonStrokingColorSpace()
    processor.set_context(engine)  # type: ignore[arg-type]
    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS1")],
    )
    assert engine._gs.non_stroking_color_space is cs  # noqa: SLF001


def test_set_non_stroking_color_space_skips_engine_setter_when_missing() -> None:
    """Closes branch (88 → 54)."""
    sentinel = object()
    cs = _ColorSpaceWithInitial(sentinel)
    engine = _BareEngine(_FakeResources(cs))
    processor = SetNonStrokingColorSpace()
    processor.set_context(engine)  # type: ignore[arg-type]
    processor.process(
        Operator.get_operator("cs"),
        [COSName.get_pdf_name("CS1")],
    )
    assert engine._gs.non_stroking_color is sentinel  # noqa: SLF001


def test_set_non_stroking_color_space_set_attr_with_none_target_is_noop() -> None:
    """Closes branch (93 → 91)."""
    SetNonStrokingColorSpace._set_attr(None, "non_stroking_color_space", object())  # noqa: SLF001
