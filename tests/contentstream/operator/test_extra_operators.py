from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_cmyk import (
    SetNonStrokingCMYK,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color import (
    SetNonStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_n import (
    SetNonStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_color_space import (
    SetNonStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_gray import (
    SetNonStrokingGray,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_rgb import (
    SetNonStrokingRGB,
)
from pypdfbox.contentstream.operator.color.set_stroking_cmyk import (
    SetStrokingCMYK,
)
from pypdfbox.contentstream.operator.color.set_stroking_color import (
    SetStrokingColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_n import (
    SetStrokingColorN,
)
from pypdfbox.contentstream.operator.color.set_stroking_color_space import (
    SetStrokingColorSpace,
)
from pypdfbox.contentstream.operator.color.set_stroking_gray import (
    SetStrokingGray,
)
from pypdfbox.contentstream.operator.color.set_stroking_rgb import (
    SetStrokingRGB,
)
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content import (
    BeginMarkedContent,
)
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_with_props import (
    BeginMarkedContentWithProps,
)
from pypdfbox.contentstream.operator.markedcontent.define_marked_content_point import (
    DefineMarkedContentPoint,
)
from pypdfbox.contentstream.operator.markedcontent.define_marked_content_point_with_props import (
    DefineMarkedContentPointWithProps,
)
from pypdfbox.contentstream.operator.markedcontent.end_marked_content import (
    EndMarkedContent,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.path.append_rectangle import (
    AppendRectangle,
)
from pypdfbox.contentstream.operator.path.clip_even_odd import ClipEvenOdd
from pypdfbox.contentstream.operator.path.clip_non_zero_winding import (
    ClipNonZeroWinding,
)
from pypdfbox.contentstream.operator.path.close_and_stroke_path import (
    CloseAndStrokePath,
)
from pypdfbox.contentstream.operator.path.close_fill_then_stroke_even_odd import (
    CloseFillThenStrokeEvenOdd,
)
from pypdfbox.contentstream.operator.path.close_fill_then_stroke_non_zero_winding import (
    CloseFillThenStrokeNonZeroWinding,
)
from pypdfbox.contentstream.operator.path.close_path import ClosePath
from pypdfbox.contentstream.operator.path.curve_to import CurveTo
from pypdfbox.contentstream.operator.path.curve_to_replicate_final_point import (
    CurveToReplicateFinalPoint,
)
from pypdfbox.contentstream.operator.path.curve_to_replicate_initial_point import (
    CurveToReplicateInitialPoint,
)
from pypdfbox.contentstream.operator.path.end_path_no_op import EndPathNoOp
from pypdfbox.contentstream.operator.path.fill_path_even_odd import (
    FillPathEvenOdd,
)
from pypdfbox.contentstream.operator.path.fill_path_non_zero_winding import (
    FillPathNonZeroWinding,
)
from pypdfbox.contentstream.operator.path.fill_then_stroke_even_odd import (
    FillThenStrokeEvenOdd,
)
from pypdfbox.contentstream.operator.path.fill_then_stroke_non_zero_winding import (
    FillThenStrokeNonZeroWinding,
)
from pypdfbox.contentstream.operator.path.legacy_fill_path import (
    LegacyFillPath,
)
from pypdfbox.contentstream.operator.path.stroke_path import StrokePath
from pypdfbox.contentstream.operator.text.next_line import NextLine
from pypdfbox.contentstream.operator.text.set_character_spacing import (
    SetCharacterSpacing,
)
from pypdfbox.contentstream.operator.text.set_horizontal_scaling import (
    SetHorizontalScaling,
)
from pypdfbox.contentstream.operator.text.set_text_leading import (
    SetTextLeading,
)
from pypdfbox.contentstream.operator.text.set_text_rendering_mode import (
    SetTextRenderingMode,
)
from pypdfbox.contentstream.operator.text.set_text_rise import SetTextRise
from pypdfbox.contentstream.operator.text.set_word_spacing import (
    SetWordSpacing,
)


# (operator-name, expected handler class) for every new stub we ship.
_NEW_OPERATORS: list[tuple[str, type[OperatorProcessor]]] = [
    # path construction
    ("c", CurveTo),
    ("v", CurveToReplicateInitialPoint),
    ("y", CurveToReplicateFinalPoint),
    ("h", ClosePath),
    ("re", AppendRectangle),
    # path painting
    ("S", StrokePath),
    ("s", CloseAndStrokePath),
    ("f", FillPathNonZeroWinding),
    ("f*", FillPathEvenOdd),
    ("F", LegacyFillPath),
    ("B", FillThenStrokeNonZeroWinding),
    ("b", CloseFillThenStrokeNonZeroWinding),
    ("B*", FillThenStrokeEvenOdd),
    ("b*", CloseFillThenStrokeEvenOdd),
    ("n", EndPathNoOp),
    # clipping
    ("W", ClipNonZeroWinding),
    ("W*", ClipEvenOdd),
    # text state
    ("Tr", SetTextRenderingMode),
    ("Ts", SetTextRise),
    ("Tc", SetCharacterSpacing),
    ("Tw", SetWordSpacing),
    ("Tz", SetHorizontalScaling),
    ("TL", SetTextLeading),
    # text positioning
    ("T*", NextLine),
    # color
    ("CS", SetStrokingColorSpace),
    ("cs", SetNonStrokingColorSpace),
    ("SC", SetStrokingColor),
    ("SCN", SetStrokingColorN),
    ("sc", SetNonStrokingColor),
    ("scn", SetNonStrokingColorN),
    ("G", SetStrokingGray),
    ("g", SetNonStrokingGray),
    ("RG", SetStrokingRGB),
    ("rg", SetNonStrokingRGB),
    ("K", SetStrokingCMYK),
    ("k", SetNonStrokingCMYK),
    # marked content
    ("BMC", BeginMarkedContent),
    ("BDC", BeginMarkedContentWithProps),
    ("EMC", EndMarkedContent),
    ("MP", DefineMarkedContentPoint),
    ("DP", DefineMarkedContentPointWithProps),
]


# ---------- per-operator class metadata ----------


def test_each_handler_class_advertises_correct_operator_name() -> None:
    """Every new stub class must set ``OPERATOR_NAME`` to the token it
    handles. The registry depends on this contract for default wiring."""
    for name, cls in _NEW_OPERATORS:
        assert cls.OPERATOR_NAME == name, (
            f"{cls.__name__}.OPERATOR_NAME={cls.OPERATOR_NAME!r}, "
            f"expected {name!r}"
        )
        # ``get_name`` is the upstream-facing accessor; it must agree
        # with the class attribute.
        assert cls().get_name() == name


# ---------- registry lookup ----------


def test_registry_lookup_returns_correct_instance_per_new_operator() -> None:
    registry = OperatorRegistry()
    for name, cls in _NEW_OPERATORS:
        handler = registry.lookup(name)
        assert isinstance(handler, cls), (
            f"lookup({name!r}) returned {type(handler).__name__}, "
            f"expected {cls.__name__}"
        )
        # Sanity: the round-trip name on the instance matches.
        assert handler.get_name() == name


# ---------- registry dispatch ----------


# Operators with upstream-faithful arity validation: ``process()`` raises
# ``MissingOperandException`` when invoked with too few operands. The
# blanket "every stub accepts empty operands" smoke test below skips
# these — see the dedicated arity-validation test that follows.
_OPERATORS_WITH_ARITY_VALIDATION: frozenset[str] = frozenset(
    {"m", "l", "c", "re"}
)


def test_registry_process_each_new_operator_does_not_raise() -> None:
    """Every pure no-op stub must accept its operator without raising.
    Operands are deliberately empty — the lite scaffold only logs.

    Operators that ported upstream's ``MissingOperandException`` arity
    check are exercised separately in
    :func:`test_registry_process_arity_validating_operators_raise`.
    """
    registry = OperatorRegistry()
    for name, _cls in _NEW_OPERATORS:
        if name in _OPERATORS_WITH_ARITY_VALIDATION:
            continue
        registry.process(Operator(name), [])


def test_registry_process_arity_validating_operators_raise() -> None:
    """Operators that mirror upstream's arity check must raise
    ``MissingOperandException`` when invoked with no operands.

    Iterates the intersection with ``_NEW_OPERATORS`` so the test only
    covers operators that this fixture file is responsible for; per-
    operator tests in ``tests/contentstream/operator/path/`` cover the
    rest in isolation.
    """
    registry = OperatorRegistry()
    new_op_names = {name for name, _ in _NEW_OPERATORS}
    for name in _OPERATORS_WITH_ARITY_VALIDATION & new_op_names:
        with pytest.raises(MissingOperandException):
            registry.process(Operator(name), [])


# ---------- integration: total registry size ----------


def test_default_registry_has_at_least_forty_operators() -> None:
    """After this cluster the default registry should expose at least
    the originally-wired 12 operators plus the ~41 new stubs."""
    registry = OperatorRegistry()
    handler_map = registry._handlers  # noqa: SLF001 — test-only introspection
    assert len(handler_map) >= 40, (
        f"default registry only exposes {len(handler_map)} handlers"
    )


def test_default_registry_includes_every_new_operator() -> None:
    """Each new operator name must be wired into the default registry,
    not just importable as a class."""
    registry = OperatorRegistry()
    for name, _cls in _NEW_OPERATORS:
        assert registry.lookup(name) is not None, (
            f"default registry has no handler for {name!r}"
        )
