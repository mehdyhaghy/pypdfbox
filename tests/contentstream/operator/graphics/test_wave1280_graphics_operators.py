"""Hand-written tests for Wave 1280 graphics operators ported from
``org.apache.pdfbox.contentstream.operator.graphics`` upstream classes."""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
    OperatorName,
)
from pypdfbox.contentstream.operator.graphics.append_rectangle_to_path import (
    AppendRectangleToPath,
)
from pypdfbox.contentstream.operator.graphics.clip_even_odd_rule import (
    ClipEvenOddRule,
)
from pypdfbox.contentstream.operator.graphics.clip_non_zero_rule import (
    ClipNonZeroRule,
)
from pypdfbox.contentstream.operator.graphics.close_fill_even_odd_and_stroke_path import (  # noqa: E501
    CloseFillEvenOddAndStrokePath,
)
from pypdfbox.contentstream.operator.graphics.close_fill_non_zero_and_stroke_path import (  # noqa: E501
    CloseFillNonZeroAndStrokePath,
)
from pypdfbox.contentstream.operator.graphics.end_path import EndPath
from pypdfbox.contentstream.operator.graphics.fill_even_odd_and_stroke_path import (  # noqa: E501
    FillEvenOddAndStrokePath,
)
from pypdfbox.contentstream.operator.graphics.fill_even_odd_rule import (
    FillEvenOddRule,
)
from pypdfbox.contentstream.operator.graphics.fill_non_zero_and_stroke_path import (  # noqa: E501
    FillNonZeroAndStrokePath,
)
from pypdfbox.contentstream.operator.graphics.fill_non_zero_rule import (
    FillNonZeroRule,
)
from pypdfbox.contentstream.operator.graphics.graphics_operator_processor import (  # noqa: E501
    GraphicsOperatorProcessor,
)
from pypdfbox.contentstream.operator.graphics.legacy_fill_non_zero_rule import (
    LegacyFillNonZeroRule,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.cos import COSFloat, COSName


def _op(name: str) -> Operator:
    return Operator.get_operator(name)


# ---------- GraphicsOperatorProcessor base ----------


def test_graphics_operator_processor_is_abstract_subclass_of_operator_processor() -> (
    None
):
    assert issubclass(GraphicsOperatorProcessor, OperatorProcessor)


def test_graphics_context_returns_bound_context_or_none() -> None:
    class _Concrete(GraphicsOperatorProcessor):
        OPERATOR_NAME = "x"

        def process(self, operator, operands):  # noqa: ANN001
            return None

    handler = _Concrete()
    assert handler.get_graphics_context() is None
    sentinel = object()
    handler.set_context(sentinel)  # type: ignore[arg-type]
    assert handler.get_graphics_context() is sentinel


# ---------- AppendRectangleToPath (re) ----------


def test_append_rectangle_to_path_operator_name_is_re() -> None:
    h = AppendRectangleToPath()
    assert h.OPERATOR_NAME == OperatorName.APPEND_RECT == "re"
    assert h.get_name() == "re"


def test_append_rectangle_to_path_raises_when_fewer_than_four_operands() -> (
    None
):
    handler = AppendRectangleToPath()
    with pytest.raises(MissingOperandException):
        handler.process(_op("re"), [COSFloat(1.0), COSFloat(2.0)])


def test_append_rectangle_to_path_silently_skips_non_number_operand() -> None:
    handler = AppendRectangleToPath()
    handler.process(
        _op("re"),
        [COSFloat(0.0), COSFloat(0.0), COSName("nope"), COSFloat(10.0)],
    )  # no exception


def test_append_rectangle_to_path_accepts_four_numbers() -> None:
    handler = AppendRectangleToPath()
    handler.process(
        _op("re"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(10.0), COSFloat(10.0)],
    )


# ---------- Clip / Fill / EndPath single-token operators ----------


@pytest.mark.parametrize(
    ("cls", "name"),
    [
        (ClipEvenOddRule, "W*"),
        (ClipNonZeroRule, "W"),
        (EndPath, "n"),
        (FillEvenOddRule, "f*"),
        (FillNonZeroRule, "f"),
        (FillEvenOddAndStrokePath, "B*"),
        (FillNonZeroAndStrokePath, "B"),
    ],
)
def test_single_token_operator_name(cls, name) -> None:
    h = cls()
    assert name == h.OPERATOR_NAME
    assert h.get_name() == name


@pytest.mark.parametrize(
    "cls",
    [
        ClipEvenOddRule,
        ClipNonZeroRule,
        EndPath,
        FillEvenOddRule,
        FillNonZeroRule,
        FillEvenOddAndStrokePath,
        FillNonZeroAndStrokePath,
    ],
)
def test_single_token_operator_process_no_op(cls) -> None:
    h = cls()
    # No operands required; must not raise.
    h.process(_op(cls.OPERATOR_NAME), [])


# ---------- Close-Fill-And-Stroke combinators ----------


def test_close_fill_non_zero_and_stroke_path_operator_name_is_b() -> None:
    h = CloseFillNonZeroAndStrokePath()
    assert h.OPERATOR_NAME == "b"
    assert h.get_name() == "b"


def test_close_fill_even_odd_and_stroke_path_operator_name_is_b_star() -> None:
    h = CloseFillEvenOddAndStrokePath()
    assert h.OPERATOR_NAME == "b*"
    assert h.get_name() == "b*"


def test_close_fill_non_zero_and_stroke_dispatches_via_bound_engine() -> None:
    calls: list[tuple[str, list]] = []

    class _Engine:
        def process_operator(self, name, operands):  # noqa: ANN001
            calls.append((name, operands))

    handler = CloseFillNonZeroAndStrokePath()
    handler.set_context(_Engine())  # type: ignore[arg-type]
    handler.process(_op("b"), [])
    assert calls == [
        (OperatorName.CLOSE_PATH, []),
        (OperatorName.FILL_NON_ZERO_AND_STROKE, []),
    ]


def test_close_fill_even_odd_and_stroke_dispatches_via_bound_engine() -> None:
    calls: list[tuple[str, list]] = []

    class _Engine:
        def process_operator(self, name, operands):  # noqa: ANN001
            calls.append((name, operands))

    handler = CloseFillEvenOddAndStrokePath()
    handler.set_context(_Engine())  # type: ignore[arg-type]
    handler.process(_op("b*"), [])
    assert calls == [
        (OperatorName.CLOSE_PATH, []),
        (OperatorName.FILL_EVEN_ODD_AND_STROKE, []),
    ]


def test_close_fill_non_zero_without_engine_does_not_raise() -> None:
    handler = CloseFillNonZeroAndStrokePath()
    handler.process(_op("b"), [])  # logs only


# ---------- LegacyFillNonZeroRule (F) ----------


def test_legacy_fill_non_zero_rule_subclasses_fill_non_zero_rule() -> None:
    assert issubclass(LegacyFillNonZeroRule, FillNonZeroRule)


def test_legacy_fill_non_zero_rule_operator_name_is_capital_f() -> None:
    h = LegacyFillNonZeroRule()
    assert h.OPERATOR_NAME == "F"
    assert h.get_name() == "F"


def test_legacy_fill_non_zero_rule_process_inherits_no_op() -> None:
    LegacyFillNonZeroRule().process(_op("F"), [])
