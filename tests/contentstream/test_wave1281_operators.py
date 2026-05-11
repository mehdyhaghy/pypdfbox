"""Wave 1281 — parity ports for content-stream operators."""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream.operator import (
    DrawObject,
    MissingOperandException,
    Operator,
    OperatorName,
)
from pypdfbox.contentstream.operator.color.set_color import SetColor
from pypdfbox.contentstream.operator.color.set_non_stroking_device_cmyk_color import (
    SetNonStrokingDeviceCMYKColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_device_gray_color import (
    SetNonStrokingDeviceGrayColor,
)
from pypdfbox.contentstream.operator.color.set_non_stroking_device_rgb_color import (
    SetNonStrokingDeviceRGBColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_cmyk_color import (
    SetStrokingDeviceCMYKColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_gray_color import (
    SetStrokingDeviceGrayColor,
)
from pypdfbox.contentstream.operator.color.set_stroking_device_rgb_color import (
    SetStrokingDeviceRGBColor,
)
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_sequence import (
    BeginMarkedContentSequence,
)
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_sequence_with_properties import (  # noqa: E501
    BeginMarkedContentSequenceWithProperties,
)
from pypdfbox.contentstream.operator.markedcontent.end_marked_content_sequence import (
    EndMarkedContentSequence,
)
from pypdfbox.contentstream.operator.markedcontent.marked_content_point import (
    MarkedContentPoint,
)
from pypdfbox.contentstream.operator.markedcontent.marked_content_point_with_properties import (
    MarkedContentPointWithProperties,
)
from pypdfbox.contentstream.operator.state.concatenate import Concatenate
from pypdfbox.contentstream.operator.state.empty_graphics_stack_exception import (
    EmptyGraphicsStackException,
)
from pypdfbox.contentstream.operator.state.restore import Restore
from pypdfbox.contentstream.operator.state.save import Save
from pypdfbox.contentstream.operator.state.set_line_dash_pattern import (
    SetLineDashPattern,
)
from pypdfbox.contentstream.operator.text.set_text_horizontal_scaling import (
    SetTextHorizontalScaling,
)
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger

# --- helpers ---------------------------------------------------------------


class _StubGraphicsState:
    def __init__(self) -> None:
        self.stroking_color: Any = None
        self.stroking_color_space: Any = None
        self.non_stroking_color: Any = None
        self.non_stroking_color_space: Any = None
        self.text_state = _StubTextState()
        self.ctm_concatenated: tuple[float, ...] | None = None

    def get_text_state(self) -> _StubTextState:
        return self.text_state

    def get_stroking_color(self) -> Any:
        return self.stroking_color

    def set_stroking_color(self, color: Any) -> None:
        self.stroking_color = color

    def get_stroking_color_space(self) -> Any:
        return self.stroking_color_space

    def set_stroking_color_space(self, cs: Any) -> None:
        self.stroking_color_space = cs

    def get_non_stroking_color(self) -> Any:
        return self.non_stroking_color

    def set_non_stroking_color(self, color: Any) -> None:
        self.non_stroking_color = color

    def get_non_stroking_color_space(self) -> Any:
        return self.non_stroking_color_space

    def set_non_stroking_color_space(self, cs: Any) -> None:
        self.non_stroking_color_space = cs


class _StubTextState:
    def __init__(self) -> None:
        self.horizontal_scaling: float | None = None

    def set_horizontal_scaling(self, value: float) -> None:
        self.horizontal_scaling = value


class _StubResources:
    def __init__(self) -> None:
        self._x_objects: dict[Any, Any] = {}
        self._properties: dict[Any, Any] = {}

    def is_image_x_object(self, _name: COSName) -> bool:
        return False

    def get_x_object(self, name: COSName) -> Any:
        return self._x_objects.get(name)

    def get_color_space(self, _name: COSName) -> Any:
        return None

    def get_properties(self, name: COSName) -> Any:
        return self._properties.get(name)


class _StubEngine:
    def __init__(self) -> None:
        self.graphics_state = _StubGraphicsState()
        self.graphics_stack_size = 1
        self.saved_count = 0
        self.restored_count = 0
        self.transform_calls: list[tuple[float, ...]] = []
        self.resources = _StubResources()
        self.events: list[tuple[str, Any]] = []
        self.dash_pattern: tuple[Any, int] | None = None
        self.level = 0

    def is_should_process_color_operators(self) -> bool:
        return True

    def get_graphics_state(self) -> _StubGraphicsState:
        return self.graphics_state

    def get_graphics_stack_size(self) -> int:
        return self.graphics_stack_size

    def save_graphics_state(self) -> None:
        self.saved_count += 1

    def restore_graphics_state(self) -> None:
        self.restored_count += 1

    def transform(self, matrix: tuple[float, ...]) -> None:
        self.transform_calls.append(matrix)

    def set_stroking_color(self, color: Any) -> None:
        self.graphics_state.set_stroking_color(color)

    def set_non_stroking_color(self, color: Any) -> None:
        self.graphics_state.set_non_stroking_color(color)

    def get_resources(self) -> _StubResources:
        return self.resources

    def begin_marked_content_sequence(self, tag: Any, properties: Any) -> None:
        self.events.append(("begin", (tag, properties)))

    def end_marked_content_sequence(self) -> None:
        self.events.append(("end", None))

    def marked_content_point(self, tag: Any, properties: Any) -> None:
        self.events.append(("point", (tag, properties)))

    def set_line_dash_pattern(self, dash_array: Any, dash_phase: int) -> None:
        self.dash_pattern = (dash_array, dash_phase)

    def increase_level(self) -> None:
        self.level += 1

    def decrease_level(self) -> None:
        self.level -= 1

    def get_level(self) -> int:
        return self.level


def _op(name: str) -> Operator:
    return Operator(name)


# --- DrawObject ------------------------------------------------------------


class TestDrawObject:
    def test_empty_operand_raises(self) -> None:
        handler = DrawObject(_StubEngine())
        with pytest.raises(MissingOperandException):
            handler.process(_op("Do"), [])

    def test_non_name_silently_skips(self) -> None:
        handler = DrawObject(_StubEngine())
        handler.process(_op("Do"), [COSInteger(1)])  # no exception

    def test_get_name(self) -> None:
        assert DrawObject(_StubEngine()).get_name() == OperatorName.DRAW_OBJECT


# --- color operators -------------------------------------------------------


class TestSetColorBase:
    def test_set_color_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            SetColor(_StubEngine())  # type: ignore[abstract]


class TestSetDeviceColorOperators:
    @pytest.mark.parametrize(
        ("handler_cls", "stroking", "components"),
        [
            (SetStrokingDeviceGrayColor, True, [0.5]),
            (SetStrokingDeviceRGBColor, True, [0.1, 0.2, 0.3]),
            (SetStrokingDeviceCMYKColor, True, [0.1, 0.2, 0.3, 0.4]),
            (SetNonStrokingDeviceGrayColor, False, [0.5]),
            (SetNonStrokingDeviceRGBColor, False, [0.1, 0.2, 0.3]),
            (SetNonStrokingDeviceCMYKColor, False, [0.1, 0.2, 0.3, 0.4]),
        ],
    )
    def test_processing_does_not_raise(
        self,
        handler_cls: type,
        stroking: bool,
        components: list[float],
    ) -> None:
        engine = _StubEngine()
        handler = handler_cls(engine)
        operands = [COSFloat(c) for c in components]
        handler.process(_op(handler.OPERATOR_NAME), operands)


# --- marked-content operators ---------------------------------------------


class TestBeginMarkedContentSequence:
    def test_forwards_tag(self) -> None:
        engine = _StubEngine()
        handler = BeginMarkedContentSequence(engine)
        handler.process(_op("BMC"), [COSName.get_pdf_name("Span")])
        assert engine.events == [
            ("begin", (COSName.get_pdf_name("Span"), None))
        ]

    def test_no_name_means_none(self) -> None:
        engine = _StubEngine()
        BeginMarkedContentSequence(engine).process(_op("BMC"), [])
        assert engine.events == [("begin", (None, None))]


class TestBeginMarkedContentSequenceWithProperties:
    def test_inline_dictionary(self) -> None:
        engine = _StubEngine()
        handler = BeginMarkedContentSequenceWithProperties(engine)
        props = COSDictionary()
        handler.process(
            _op("BDC"),
            [COSName.get_pdf_name("Span"), props],
        )
        assert engine.events == [
            ("begin", (COSName.get_pdf_name("Span"), props))
        ]

    def test_missing_operand_raises(self) -> None:
        engine = _StubEngine()
        with pytest.raises(MissingOperandException):
            BeginMarkedContentSequenceWithProperties(engine).process(
                _op("BDC"), []
            )


class TestEndMarkedContentSequence:
    def test_forwards_end(self) -> None:
        engine = _StubEngine()
        EndMarkedContentSequence(engine).process(_op("EMC"), [])
        assert engine.events == [("end", None)]


class TestMarkedContentPoint:
    def test_forwards_tag(self) -> None:
        engine = _StubEngine()
        MarkedContentPoint(engine).process(
            _op("MP"), [COSName.get_pdf_name("Span")]
        )
        assert engine.events == [
            ("point", (COSName.get_pdf_name("Span"), None))
        ]

    def test_missing_operand_raises(self) -> None:
        with pytest.raises(MissingOperandException):
            MarkedContentPoint(_StubEngine()).process(_op("MP"), [])


class TestMarkedContentPointWithProperties:
    def test_inline_dict_forwarded(self) -> None:
        engine = _StubEngine()
        props = COSDictionary()
        MarkedContentPointWithProperties(engine).process(
            _op("DP"), [COSName.get_pdf_name("Span"), props]
        )
        assert engine.events == [
            ("point", (COSName.get_pdf_name("Span"), props))
        ]


# --- state operators -------------------------------------------------------


class TestConcatenate:
    def test_six_numbers_transforms(self) -> None:
        engine = _StubEngine()
        Concatenate(engine).process(
            _op("cm"),
            [COSFloat(1), COSFloat(0), COSFloat(0), COSFloat(1), COSFloat(0), COSFloat(0)],
        )
        assert engine.transform_calls == [(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)]

    def test_short_operand_raises(self) -> None:
        with pytest.raises(MissingOperandException):
            Concatenate(_StubEngine()).process(_op("cm"), [COSFloat(1)])


class TestSaveRestore:
    def test_save_invokes_engine(self) -> None:
        engine = _StubEngine()
        Save(engine).process(_op("q"), [])
        assert engine.saved_count == 1

    def test_restore_invokes_engine(self) -> None:
        engine = _StubEngine()
        engine.graphics_stack_size = 2
        Restore(engine).process(_op("Q"), [])
        assert engine.restored_count == 1

    def test_restore_too_many_raises(self) -> None:
        engine = _StubEngine()
        engine.graphics_stack_size = 1
        with pytest.raises(EmptyGraphicsStackException):
            Restore(engine).process(_op("Q"), [])


class TestSetLineDashPattern:
    def test_valid_operands_forwarded(self) -> None:
        engine = _StubEngine()
        dash = COSArray()
        dash.add(COSInteger(3))
        SetLineDashPattern(engine).process(_op("d"), [dash, COSInteger(0)])
        assert engine.dash_pattern is not None

    def test_short_operand_raises(self) -> None:
        with pytest.raises(MissingOperandException):
            SetLineDashPattern(_StubEngine()).process(_op("d"), [COSArray()])


# --- text operator --------------------------------------------------------


class TestSetTextHorizontalScaling:
    def test_sets_horizontal_scaling(self) -> None:
        engine = _StubEngine()
        SetTextHorizontalScaling(engine).process(_op("Tz"), [COSFloat(120.0)])
        assert engine.graphics_state.text_state.horizontal_scaling == 120.0

    def test_missing_operand_raises(self) -> None:
        with pytest.raises(MissingOperandException):
            SetTextHorizontalScaling(_StubEngine()).process(_op("Tz"), [])

    def test_non_number_silently_skips(self) -> None:
        engine = _StubEngine()
        SetTextHorizontalScaling(engine).process(
            _op("Tz"), [COSName.get_pdf_name("foo")]
        )
        assert engine.graphics_state.text_state.horizontal_scaling is None
