"""Wave 1316 — coverage boost for under-tested content-stream operators.

Targets five operators that sat below 80% line coverage prior to this wave:

* ``DrawObject`` (``Do``)                              — 39% → ~95%
* ``SetColor`` (abstract ``sc / scn / SC / SCN`` base) — 52% → ~95%
* ``MarkedContentPointWithProperties`` (``DP``)        — 65% → ~95%
* ``BeginMarkedContentSequenceWithProperties`` (``BDC``) — 68% → ~95%
* ``Concatenate`` (``cm``)                             — 76% → ~100%

Tests instantiate each operator against a minimal stub engine and assert
the observable state mutation / hook invocation, matching the helper
shape established by ``tests/contentstream/test_wave1281_operators.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream.operator import (
    DrawObject,
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.color.set_color import SetColor
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_sequence_with_properties import (  # noqa: E501
    BeginMarkedContentSequenceWithProperties,
)
from pypdfbox.contentstream.operator.markedcontent.marked_content_point_with_properties import (  # noqa: E501
    MarkedContentPointWithProperties,
)
from pypdfbox.contentstream.operator.state.concatenate import Concatenate
from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger


# --- helpers ---------------------------------------------------------------


class _StubResources:
    def __init__(self) -> None:
        self._x_objects: dict[Any, Any] = {}
        self._properties: dict[Any, Any] = {}
        self._is_image_returns: bool = False

    def is_image_x_object(self, _name: COSName) -> bool:
        return self._is_image_returns

    def get_x_object(self, name: COSName) -> Any:
        return self._x_objects.get(name)

    def get_properties(self, name: COSName) -> Any:
        return self._properties.get(name)


class _StubGraphicsState:
    def __init__(self) -> None:
        self.ctm = _StubCtm()

    def get_current_transformation_matrix(self) -> _StubCtm:
        return self.ctm


class _StubCtm:
    def __init__(self) -> None:
        self.concatenations: list[tuple[float, ...]] = []

    def concatenate(self, matrix: tuple[float, ...]) -> None:
        self.concatenations.append(matrix)


class _StubEngine:
    """A minimal duck-typed stand-in for :class:`PDFStreamEngine`.

    Covers exactly the methods the five operators under test reach for —
    avoids the cost of constructing a real engine plus its rendering
    side-effects.
    """

    def __init__(
        self,
        *,
        resources: _StubResources | None = None,
        with_graphics_state: bool = False,
    ) -> None:
        self.resources: _StubResources | None = resources
        self.events: list[tuple[str, Any]] = []
        self.transform_calls: list[tuple[float, ...]] = []
        self.level = 0
        self.shown_forms: list[Any] = []
        self.shown_transparency_groups: list[Any] = []
        if with_graphics_state:
            self._graphics_state: _StubGraphicsState | None = (
                _StubGraphicsState()
            )
        else:
            self._graphics_state = None

    def get_resources(self) -> _StubResources | None:
        return self.resources

    def get_graphics_state(self) -> _StubGraphicsState | None:
        return self._graphics_state

    def transform(self, matrix: tuple[float, ...]) -> None:
        self.transform_calls.append(matrix)

    # ---- DrawObject hooks ----
    def increase_level(self) -> None:
        self.level += 1

    def decrease_level(self) -> None:
        self.level -= 1

    def get_level(self) -> int:
        return self.level

    def show_form(self, xobject: Any) -> None:
        self.shown_forms.append(xobject)

    def show_transparency_group(self, xobject: Any) -> None:
        self.shown_transparency_groups.append(xobject)

    # ---- marked-content hooks ----
    def begin_marked_content_sequence(
        self, tag: COSName, properties: COSDictionary
    ) -> None:
        self.events.append(("begin", (tag, properties)))

    def marked_content_point(
        self, tag: COSName, properties: COSDictionary
    ) -> None:
        self.events.append(("point", (tag, properties)))


class _NoTransformEngine:
    """Engine variant without a ``transform`` method — exercises the
    Concatenate fallback path that pokes the graphics-state CTM directly.
    """

    def __init__(self) -> None:
        self._graphics_state: _StubGraphicsState = _StubGraphicsState()

    def get_graphics_state(self) -> _StubGraphicsState:
        return self._graphics_state


def _op(name: str) -> Operator:
    return Operator(name)


# --- DrawObject ------------------------------------------------------------


class _FormXObject:
    """Duck-typed PDFormXObject — matches DrawObject's name-based sniff."""

    def __init__(self, label: str = "form") -> None:
        self.label = label
        # Surface the class-name-based discriminator used by
        # ``_is_form_xobject`` without needing the real class.

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"_FormXObject(label={self.label!r})"


# Rename so type(obj).__name__ matches the sniff in draw_object.
_FormXObject.__name__ = "PDFormXObject"


class _TransparencyGroup:
    pass


_TransparencyGroup.__name__ = "PDTransparencyGroup"


class _MarkedFormXObject:
    """Form xobject whose class name doesn't match, but exposes the
    ``is_form_xobject`` attribute — exercises the fallback branch in
    :func:`_is_form_xobject`."""

    is_form_xobject = True


class TestDrawObjectCoverage:
    def test_missing_operand_raises(self) -> None:
        handler = DrawObject(_StubEngine())
        with pytest.raises(MissingOperandException):
            handler.process(_op("Do"), [])

    def test_non_name_operand_silently_returns(self) -> None:
        engine = _StubEngine()
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSInteger(42)])
        assert engine.shown_forms == []

    def test_no_context_returns_early(self) -> None:
        handler = DrawObject(None)
        # Must not raise even when context is unset.
        handler.process(_op("Do"), [COSName.get_pdf_name("Im1")])

    def test_no_resources_returns_early(self) -> None:
        engine = _StubEngine(resources=None)
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSName.get_pdf_name("Im1")])
        assert engine.shown_forms == []

    def test_image_xobject_short_circuits(self) -> None:
        resources = _StubResources()
        resources._is_image_returns = True
        engine = _StubEngine(resources=resources)
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSName.get_pdf_name("Im1")])
        # Image branch must not call show_form / show_transparency_group.
        assert engine.shown_forms == []
        assert engine.shown_transparency_groups == []

    def test_unknown_xobject_returns_silently(self) -> None:
        resources = _StubResources()
        engine = _StubEngine(resources=resources)
        handler = DrawObject(engine)
        # No XObject registered for /Frm1 → get_x_object returns None.
        handler.process(_op("Do"), [COSName.get_pdf_name("Frm1")])
        assert engine.shown_forms == []

    def test_form_xobject_invokes_show_form(self) -> None:
        resources = _StubResources()
        form = _FormXObject("hello")
        resources._x_objects[COSName.get_pdf_name("Frm1")] = form
        engine = _StubEngine(resources=resources)
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSName.get_pdf_name("Frm1")])
        assert engine.shown_forms == [form]
        assert engine.shown_transparency_groups == []
        # increase_level / decrease_level must balance.
        assert engine.level == 0

    def test_form_xobject_via_attribute_fallback(self) -> None:
        resources = _StubResources()
        marked = _MarkedFormXObject()
        resources._x_objects[COSName.get_pdf_name("Frm2")] = marked
        engine = _StubEngine(resources=resources)
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSName.get_pdf_name("Frm2")])
        assert engine.shown_forms == [marked]

    def test_transparency_group_invokes_show_transparency_group(self) -> None:
        resources = _StubResources()
        group = _TransparencyGroup()
        resources._x_objects[COSName.get_pdf_name("Grp1")] = group
        engine = _StubEngine(resources=resources)
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSName.get_pdf_name("Grp1")])
        assert engine.shown_transparency_groups == [group]
        assert engine.shown_forms == []
        assert engine.level == 0

    def test_recursion_guard_at_depth_50(self) -> None:
        resources = _StubResources()
        form = _FormXObject()
        resources._x_objects[COSName.get_pdf_name("Frm1")] = form
        engine = _StubEngine(resources=resources)
        engine.level = 50  # next call will push to 51 → guard trips.
        handler = DrawObject(engine)
        handler.process(_op("Do"), [COSName.get_pdf_name("Frm1")])
        assert engine.shown_forms == []
        # The finally block in DrawObject must still decrement.
        assert engine.level == 50


# --- SetColor (abstract base) ----------------------------------------------


class _StubColorSpace:
    def __init__(self, components: int = 3) -> None:
        self._components = components

    def get_number_of_components(self) -> int:
        return self._components

    def get_name(self) -> str:
        return "DeviceRGB"


class _StubPatternColorSpace:
    """Sniff target for :func:`_is_pattern_colorspace` (class-name match)."""

    def get_number_of_components(self) -> int:
        return 0

    def get_name(self) -> str:
        return "Pattern"


_StubPatternColorSpace.__name__ = "PDPattern"


class _ConcreteSetColor(SetColor):
    """Concrete subclass plumbing the four abstract hooks to in-memory
    state so we can exercise the base ``process`` method."""

    def __init__(self, color_space: Any) -> None:
        super().__init__(None)
        self._color_space = color_space
        self._color: Any = None

    def get_color(self) -> Any:
        return self._color

    def set_color(self, color: Any) -> None:
        self._color = color

    def get_color_space(self) -> Any:
        return self._color_space


class TestSetColorCoverage:
    def test_no_color_space_silently_returns(self) -> None:
        handler = _ConcreteSetColor(color_space=None)
        handler.process(_op("sc"), [COSFloat(0.5)])
        assert handler.get_color() is None

    def test_missing_operand_raises(self) -> None:
        handler = _ConcreteSetColor(color_space=_StubColorSpace(3))
        with pytest.raises(MissingOperandException):
            handler.process(_op("sc"), [COSFloat(0.5)])  # need 3 components

    def test_non_number_operand_yields_empty_color(self) -> None:
        # PDFBOX-5851 — when an operand isn't a number, set the color
        # to an empty-components / no-space PDColor rather than raising.
        handler = _ConcreteSetColor(color_space=_StubColorSpace(3))
        handler.process(
            _op("sc"),
            [COSFloat(0.1), COSName.get_pdf_name("Bad"), COSFloat(0.3)],
        )
        color = handler.get_color()
        assert color is not None
        assert list(color.get_components()) == []
        assert color.get_color_space() is None

    def test_valid_components_build_pd_color(self) -> None:
        cs = _StubColorSpace(3)
        handler = _ConcreteSetColor(color_space=cs)
        handler.process(
            _op("sc"),
            [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
        )
        color = handler.get_color()
        assert color is not None
        assert color.get_color_space() is cs
        assert [round(c, 3) for c in color.get_components()] == [0.1, 0.2, 0.3]

    def test_pattern_colorspace_short_circuits_operand_check(self) -> None:
        # Pattern color space → skip the operand-count guard and pass the
        # operand list straight through; even a single COSName operand
        # must succeed without raising MissingOperandException.
        handler = _ConcreteSetColor(color_space=_StubPatternColorSpace())
        handler.process(_op("scn"), [COSName.get_pdf_name("P1")])
        color = handler.get_color()
        assert color is not None


# --- MarkedContentPointWithProperties (DP) ---------------------------------


class TestMarkedContentPointWithPropertiesCoverage:
    def test_missing_operand_raises(self) -> None:
        engine = _StubEngine()
        handler = MarkedContentPointWithProperties(engine)
        with pytest.raises(MissingOperandException):
            handler.process(_op("DP"), [COSName.get_pdf_name("Span")])

    def test_first_operand_not_name_silently_skips(self) -> None:
        engine = _StubEngine()
        handler = MarkedContentPointWithProperties(engine)
        handler.process(_op("DP"), [COSInteger(1), COSDictionary()])
        assert engine.events == []

    def test_no_context_silently_returns(self) -> None:
        handler = MarkedContentPointWithProperties(None)
        # Must not raise even when context is unset.
        handler.process(_op("DP"), [COSName.get_pdf_name("Span"), COSDictionary()])

    def test_inline_dictionary_is_forwarded(self) -> None:
        engine = _StubEngine()
        handler = MarkedContentPointWithProperties(engine)
        tag = COSName.get_pdf_name("Span")
        props = COSDictionary()
        handler.process(_op("DP"), [tag, props])
        assert engine.events == [("point", (tag, props))]

    def test_named_property_dict_resolved_via_resources(self) -> None:
        resources = _StubResources()
        prop_dict = COSDictionary()

        class _PropertyList:
            def get_cos_object(self) -> COSDictionary:
                return prop_dict

        resources._properties[COSName.get_pdf_name("PL1")] = _PropertyList()
        engine = _StubEngine(resources=resources)
        handler = MarkedContentPointWithProperties(engine)
        tag = COSName.get_pdf_name("Span")
        handler.process(_op("DP"), [tag, COSName.get_pdf_name("PL1")])
        assert engine.events == [("point", (tag, prop_dict))]

    def test_unresolvable_named_property_silently_drops(self) -> None:
        # No /PL1 in resources → prop_dict stays None → no hook call.
        engine = _StubEngine(resources=_StubResources())
        handler = MarkedContentPointWithProperties(engine)
        handler.process(
            _op("DP"),
            [COSName.get_pdf_name("Span"), COSName.get_pdf_name("PL1")],
        )
        assert engine.events == []


# --- BeginMarkedContentSequenceWithProperties (BDC) ------------------------


class TestBeginMarkedContentSequenceWithPropertiesCoverage:
    def test_missing_operand_raises(self) -> None:
        engine = _StubEngine()
        handler = BeginMarkedContentSequenceWithProperties(engine)
        with pytest.raises(MissingOperandException):
            handler.process(_op("BDC"), [COSName.get_pdf_name("Span")])

    def test_first_operand_not_name_silently_skips(self) -> None:
        engine = _StubEngine()
        handler = BeginMarkedContentSequenceWithProperties(engine)
        handler.process(_op("BDC"), [COSInteger(1), COSDictionary()])
        assert engine.events == []

    def test_no_context_silently_returns(self) -> None:
        handler = BeginMarkedContentSequenceWithProperties(None)
        handler.process(
            _op("BDC"), [COSName.get_pdf_name("Span"), COSDictionary()]
        )

    def test_inline_dictionary_is_forwarded(self) -> None:
        engine = _StubEngine()
        handler = BeginMarkedContentSequenceWithProperties(engine)
        tag = COSName.get_pdf_name("Span")
        props = COSDictionary()
        handler.process(_op("BDC"), [tag, props])
        assert engine.events == [("begin", (tag, props))]

    def test_named_property_dict_resolved_via_resources(self) -> None:
        resources = _StubResources()
        prop_dict = COSDictionary()

        class _PropertyList:
            def get_cos_object(self) -> COSDictionary:
                return prop_dict

        resources._properties[COSName.get_pdf_name("PL1")] = _PropertyList()
        engine = _StubEngine(resources=resources)
        handler = BeginMarkedContentSequenceWithProperties(engine)
        tag = COSName.get_pdf_name("Span")
        handler.process(_op("BDC"), [tag, COSName.get_pdf_name("PL1")])
        assert engine.events == [("begin", (tag, prop_dict))]

    def test_unresolvable_named_property_silently_drops(self) -> None:
        engine = _StubEngine(resources=_StubResources())
        handler = BeginMarkedContentSequenceWithProperties(engine)
        handler.process(
            _op("BDC"),
            [COSName.get_pdf_name("Span"), COSName.get_pdf_name("PL1")],
        )
        assert engine.events == []

    def test_no_resources_silently_drops_named(self) -> None:
        engine = _StubEngine(resources=None)
        handler = BeginMarkedContentSequenceWithProperties(engine)
        handler.process(
            _op("BDC"),
            [COSName.get_pdf_name("Span"), COSName.get_pdf_name("PL1")],
        )
        assert engine.events == []


# --- Concatenate (cm) ------------------------------------------------------


class TestConcatenateCoverage:
    def test_missing_operand_raises(self) -> None:
        engine = _StubEngine()
        handler = Concatenate(engine)
        with pytest.raises(MissingOperandException):
            handler.process(_op("cm"), [COSFloat(1.0)] * 3)

    def test_non_number_operand_silently_skips(self) -> None:
        engine = _StubEngine()
        handler = Concatenate(engine)
        ops = [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0),
               COSFloat(1.0), COSName.get_pdf_name("Bad"), COSFloat(0.0)]
        handler.process(_op("cm"), ops)
        assert engine.transform_calls == []

    def test_transform_hook_called_with_six_floats(self) -> None:
        engine = _StubEngine()
        handler = Concatenate(engine)
        ops = [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0),
               COSFloat(1.0), COSFloat(10.0), COSFloat(20.0)]
        handler.process(_op("cm"), ops)
        assert engine.transform_calls == [(1.0, 0.0, 0.0, 1.0, 10.0, 20.0)]

    def test_integer_operands_are_accepted(self) -> None:
        # COSInteger is a COSNumber subclass — the type check must allow it.
        engine = _StubEngine()
        handler = Concatenate(engine)
        ops = [COSInteger(2), COSInteger(0), COSInteger(0),
               COSInteger(2), COSInteger(5), COSInteger(7)]
        handler.process(_op("cm"), ops)
        assert engine.transform_calls == [(2.0, 0.0, 0.0, 2.0, 5.0, 7.0)]

    def test_fallback_to_graphics_state_when_no_transform(self) -> None:
        # When the engine lacks a ``transform`` method the operator
        # falls through to ``graphics_state.get_current_transformation_matrix()``
        # and calls ``.concatenate(matrix)`` directly.
        engine = _NoTransformEngine()
        handler = Concatenate(engine)
        ops = [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0),
               COSFloat(1.0), COSFloat(3.0), COSFloat(4.0)]
        handler.process(_op("cm"), ops)
        graphics_state = engine.get_graphics_state()
        assert graphics_state.ctm.concatenations == [
            (1.0, 0.0, 0.0, 1.0, 3.0, 4.0),
        ]

    def test_no_context_silently_returns(self) -> None:
        handler = Concatenate(None)
        ops = [COSFloat(1.0)] * 6
        handler.process(_op("cm"), ops)  # must not raise

    def test_get_name_returns_cm(self) -> None:
        assert Concatenate(None).get_name() == "cm"
