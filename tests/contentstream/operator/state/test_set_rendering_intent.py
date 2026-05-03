from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_rendering_intent import (
    SetRenderingIntent,
)
from pypdfbox.cos import COSInteger, COSName, COSString


def test_class_advertises_ri_operator_name() -> None:
    assert SetRenderingIntent.OPERATOR_NAME == "ri"
    assert SetRenderingIntent().get_name() == "ri"


def test_is_operator_processor_subclass() -> None:
    assert issubclass(SetRenderingIntent, OperatorProcessor)


def test_process_with_each_predefined_intent_does_not_raise() -> None:
    # Per ISO 32000-1 §8.6.5.8 the four predefined intent names.
    p = SetRenderingIntent()
    for intent in (
        "AbsoluteColorimetric",
        "RelativeColorimetric",
        "Saturation",
        "Perceptual",
    ):
        p.process(
            Operator.get_operator("ri"), [COSName.get_pdf_name(intent)]
        )


def test_process_with_zero_operands_raises_missing_operand() -> None:
    # Upstream throws ``MissingOperandException`` when no operand is
    # supplied; we mirror that.
    p = SetRenderingIntent()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("ri"), [])


def test_process_with_non_name_operand_silently_returns() -> None:
    # Upstream ``return``s after the ``instanceof COSName`` check when
    # the operand is some other COS type.
    p = SetRenderingIntent()
    p.process(
        Operator.get_operator("ri"),
        [COSString("RelativeColorimetric")],
    )
    p.process(Operator.get_operator("ri"), [COSInteger.get(0)])


def test_default_registry_routes_ri_to_set_rendering_intent() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("ri")
    assert isinstance(handler, SetRenderingIntent)
    assert handler.get_name() == "ri"


def test_default_registry_dispatch_through_process() -> None:
    registry = OperatorRegistry()
    registry.process(
        Operator.get_operator("ri"),
        [COSName.get_pdf_name("RelativeColorimetric")],
    )


def test_get_intent_name_returns_leading_name() -> None:
    name = COSName.get_pdf_name("Saturation")
    assert SetRenderingIntent.get_intent_name([name]) is name


def test_get_intent_name_returns_none_for_empty_operands() -> None:
    assert SetRenderingIntent.get_intent_name([]) is None


def test_get_intent_name_returns_none_when_first_operand_not_a_name() -> None:
    # Non-COSName lead operand: silent-skip — accessor reports ``None``.
    assert (
        SetRenderingIntent.get_intent_name([COSString("Perceptual")]) is None
    )
    assert SetRenderingIntent.get_intent_name([COSInteger.get(0)]) is None


def test_get_intent_name_round_trips_each_predefined_intent() -> None:
    # Per ISO 32000-1 §8.6.5.8 the four predefined intent names must
    # round-trip cleanly through the typed accessor.
    for intent in (
        "AbsoluteColorimetric",
        "RelativeColorimetric",
        "Saturation",
        "Perceptual",
    ):
        name = COSName.get_pdf_name(intent)
        assert SetRenderingIntent.get_intent_name([name]) is name
        assert SetRenderingIntent.get_intent_name([name]).get_name() == intent
