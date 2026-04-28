from __future__ import annotations

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.color.set_non_stroking_cmyk import (
    SetNonStrokingCMYK,
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
from pypdfbox.contentstream.operator.color.set_stroking_gray import (
    SetStrokingGray,
)
from pypdfbox.contentstream.operator.color.set_stroking_rgb import (
    SetStrokingRGB,
)
from pypdfbox.cos import COSFloat, COSString
from pypdfbox.pdmodel.graphics.color import PDColor


class _ColorSpy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.colors: list[tuple[str, PDColor]] = []

    def set_stroking_color(self, color: PDColor) -> None:
        self.colors.append(("stroking", color))

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.colors.append(("nonstroking", color))


def _floats(*values: float) -> list[COSFloat]:
    return [COSFloat(value) for value in values]


def test_device_color_operators_forward_pdcolor_to_engine_hooks() -> None:
    engine = _ColorSpy()
    cases = [
        (
            SetStrokingGray(),
            "G",
            _floats(0.25),
            "stroking",
            "DeviceGray",
            [0.25],
        ),
        (
            SetNonStrokingGray(),
            "g",
            _floats(0.5),
            "nonstroking",
            "DeviceGray",
            [0.5],
        ),
        (
            SetStrokingRGB(),
            "RG",
            _floats(0.125, 0.25, 0.5),
            "stroking",
            "DeviceRGB",
            [0.125, 0.25, 0.5],
        ),
        (
            SetNonStrokingRGB(),
            "rg",
            _floats(0.25, 0.5, 0.75),
            "nonstroking",
            "DeviceRGB",
            [0.25, 0.5, 0.75],
        ),
        (
            SetStrokingCMYK(),
            "K",
            _floats(0.125, 0.25, 0.5, 0.75),
            "stroking",
            "DeviceCMYK",
            [0.125, 0.25, 0.5, 0.75],
        ),
        (
            SetNonStrokingCMYK(),
            "k",
            _floats(0.0, 0.25, 0.5, 1.0),
            "nonstroking",
            "DeviceCMYK",
            [0.0, 0.25, 0.5, 1.0],
        ),
    ]
    for (
        processor,
        operator_name,
        operands,
        expected_kind,
        expected_space,
        expected_components,
    ) in cases:
        engine.add_operator(processor)
        processor.process(Operator.get_operator(operator_name), operands)
        kind, color = engine.colors[-1]
        assert kind == expected_kind
        assert color.get_color_space_name() == expected_space
        assert color.get_components() == expected_components


def test_device_color_operator_without_context_is_no_op() -> None:
    SetStrokingRGB().process(Operator.get_operator("RG"), _floats(1.0, 0.0, 0.0))


def test_device_color_operator_skips_malformed_operands() -> None:
    engine = _ColorSpy()
    processor = SetStrokingRGB()
    engine.add_operator(processor)

    processor.process(Operator.get_operator("RG"), _floats(1.0, 0.0))
    processor.process(
        Operator.get_operator("RG"),
        [COSFloat(1.0), COSString("bad"), COSFloat(0.0)],
    )

    assert engine.colors == []
