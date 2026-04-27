from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_registry import (
    OperatorRegistry,
)
from pypdfbox.contentstream.operator.state.set_rendering_intent import (
    SetRenderingIntent,
)
from pypdfbox.cos import COSName


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


def test_process_with_zero_operands_does_not_raise() -> None:
    p = SetRenderingIntent()
    p.process(Operator.get_operator("ri"), [])


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
