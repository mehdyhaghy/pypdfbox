"""Fuzz / branch-coverage for the remaining graphics-state content-stream
operators under ``pypdfbox.contentstream.operator.state``:

* ``SetFlatness`` (``i``) — flatness tolerance applied to the graphics state.
* ``SetRenderingIntent`` (``ri``) — colour rendering intent applied to the
  graphics state, with unknown names falling back to ``RelativeColorimetric``.
* ``SetGraphicsStateParameters`` (``gs``) — leading-``COSName`` validation +
  silent skip; the real ExtGState apply lands in the renderer's own ``gs``
  handler (registry stub deliberately defers — see the class docstring).

These hammer the operand-validation branches AND the context-bound apply path
(the latter was previously uncovered: existing tests never bound a context, so
``set_flatness`` / ``set_rendering_intent`` were never actually invoked on a
graphics state). Behaviour is cross-checked against PDFBox 3.0.7
``SetFlatness`` / ``SetRenderingIntent`` / ``SetGraphicsStateParameters``.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.state.set_flatness import SetFlatness
from pypdfbox.contentstream.operator.state.set_graphics_state_parameters import (
    SetGraphicsStateParameters,
)
from pypdfbox.contentstream.operator.state.set_rendering_intent import (
    SetRenderingIntent,
)
from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent

# --------------------------------------------------------------------------
# Test doubles — a minimal graphics state + context driving the apply path.
# --------------------------------------------------------------------------


class _RecordingGraphicsState:
    """Records ``set_flatness`` / ``set_rendering_intent`` invocations so the
    apply path can be asserted, mirroring the fields upstream's
    ``PDGraphicsState`` carries."""

    def __init__(self) -> None:
        self.flatness: float | None = None
        self.rendering_intent: RenderingIntent | None = None

    def set_flatness(self, value: float) -> None:
        self.flatness = value

    def set_rendering_intent(self, value: RenderingIntent) -> None:
        self.rendering_intent = value


class _FakeContext:
    def __init__(self, gs: object | None) -> None:
        self._gs = gs

    def get_graphics_state(self) -> object | None:
        return self._gs


def _flatness(context: object | None = None) -> SetFlatness:
    p = SetFlatness()
    if context is not None:
        p.set_context(context)
    return p


def _intent(context: object | None = None) -> SetRenderingIntent:
    p = SetRenderingIntent()
    if context is not None:
        p.set_context(context)
    return p


def _op(name: str) -> Operator:
    return Operator.get_operator(name)


# --------------------------------------------------------------------------
# SetFlatness (i)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0, 50.0, 100.0])
def test_flatness_applies_float_value_to_graphics_state(value: float) -> None:
    gs = _RecordingGraphicsState()
    _flatness(_FakeContext(gs)).process(_op("i"), [COSFloat(value)])
    assert gs.flatness == pytest.approx(value)


def test_flatness_applies_integer_operand_as_float() -> None:
    gs = _RecordingGraphicsState()
    _flatness(_FakeContext(gs)).process(_op("i"), [COSInteger.get(7)])
    assert gs.flatness == pytest.approx(7.0)
    assert isinstance(gs.flatness, float)


def test_flatness_uses_first_operand_when_all_numeric() -> None:
    # checkArrayTypesClass passes (all COSNumber) → operands[0] applied.
    gs = _RecordingGraphicsState()
    _flatness(_FakeContext(gs)).process(
        _op("i"), [COSFloat(3.0), COSInteger.get(9)]
    )
    assert gs.flatness == pytest.approx(3.0)


def test_flatness_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        _flatness().process(_op("i"), [])


@pytest.mark.parametrize(
    "operand",
    [
        COSName.get_pdf_name("Foo"),
        COSString("1"),
        COSBoolean.TRUE,
        COSNull.NULL,
        COSArray(),
    ],
    ids=["name", "string", "bool", "null", "array"],
)
def test_flatness_non_number_operand_silently_skips(operand: object) -> None:
    # checkArrayTypesClass(operands, COSNumber) fails → upstream returns
    # without touching the graphics state.
    gs = _RecordingGraphicsState()
    _flatness(_FakeContext(gs)).process(_op("i"), [operand])
    assert gs.flatness is None


def test_flatness_mixed_numeric_and_non_numeric_skips_entirely() -> None:
    # A trailing non-number poisons the WHOLE list under
    # checkArrayTypesClass → nothing applied (upstream parity).
    gs = _RecordingGraphicsState()
    _flatness(_FakeContext(gs)).process(
        _op("i"), [COSFloat(2.0), COSString("x")]
    )
    assert gs.flatness is None


def test_flatness_no_context_is_noop_not_crash() -> None:
    # Standalone registry use: get_context() is None → log + return.
    _flatness().process(_op("i"), [COSFloat(4.0)])


def test_flatness_context_without_graphics_state_is_noop() -> None:
    _flatness(_FakeContext(None)).process(_op("i"), [COSFloat(4.0)])


def test_flatness_graphics_state_without_setter_is_noop() -> None:
    # getattr(gs, "set_flatness", None) is not callable → skip silently.
    class _Bare:
        def get_graphics_state(self) -> object:
            return object()

    _flatness(_Bare()).process(_op("i"), [COSFloat(4.0)])


# --------------------------------------------------------------------------
# SetRenderingIntent (ri)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("AbsoluteColorimetric", RenderingIntent.ABSOLUTE_COLORIMETRIC),
        ("RelativeColorimetric", RenderingIntent.RELATIVE_COLORIMETRIC),
        ("Saturation", RenderingIntent.SATURATION),
        ("Perceptual", RenderingIntent.PERCEPTUAL),
    ],
)
def test_intent_applies_each_predefined_name(
    name: str, expected: RenderingIntent
) -> None:
    gs = _RecordingGraphicsState()
    _intent(_FakeContext(gs)).process(_op("ri"), [COSName.get_pdf_name(name)])
    assert gs.rendering_intent is expected


@pytest.mark.parametrize(
    "name",
    ["Unknown", "absolutecolorimetric", "", "RelativeColometric", "AC"],
    ids=["unknown", "lowercase", "empty", "typo", "abbrev"],
)
def test_intent_unknown_name_falls_back_to_relative(name: str) -> None:
    # PDF 32000-1 §8.6.5.8: unrecognised intent → RelativeColorimetric.
    gs = _RecordingGraphicsState()
    _intent(_FakeContext(gs)).process(_op("ri"), [COSName.get_pdf_name(name)])
    assert gs.rendering_intent is RenderingIntent.RELATIVE_COLORIMETRIC


def test_intent_uses_only_first_operand() -> None:
    gs = _RecordingGraphicsState()
    _intent(_FakeContext(gs)).process(
        _op("ri"),
        [COSName.get_pdf_name("Saturation"), COSName.get_pdf_name("Perceptual")],
    )
    assert gs.rendering_intent is RenderingIntent.SATURATION


def test_intent_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        _intent().process(_op("ri"), [])


@pytest.mark.parametrize(
    "operand",
    [
        COSString("Saturation"),
        COSInteger.get(0),
        COSFloat(1.0),
        COSBoolean.FALSE,
        COSNull.NULL,
        COSArray(),
    ],
    ids=["string", "int", "float", "bool", "null", "array"],
)
def test_intent_non_name_operand_silently_skips(operand: object) -> None:
    gs = _RecordingGraphicsState()
    _intent(_FakeContext(gs)).process(_op("ri"), [operand])
    assert gs.rendering_intent is None


def test_intent_no_context_is_noop_not_crash() -> None:
    _intent().process(_op("ri"), [COSName.get_pdf_name("Perceptual")])


def test_intent_context_without_graphics_state_is_noop() -> None:
    _intent(_FakeContext(None)).process(
        _op("ri"), [COSName.get_pdf_name("Perceptual")]
    )


def test_intent_graphics_state_without_setter_is_noop() -> None:
    class _Bare:
        def get_graphics_state(self) -> object:
            return object()

    _intent(_Bare()).process(_op("ri"), [COSName.get_pdf_name("Perceptual")])


# --------------------------------------------------------------------------
# SetGraphicsStateParameters (gs) — validation + typed accessor.
# --------------------------------------------------------------------------


def test_gs_name_operand_does_not_raise() -> None:
    SetGraphicsStateParameters().process(
        _op("gs"), [COSName.get_pdf_name("GS1")]
    )


def test_gs_empty_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException):
        SetGraphicsStateParameters().process(_op("gs"), [])


@pytest.mark.parametrize(
    "operand",
    [
        COSString("GS1"),
        COSInteger.get(1),
        COSFloat(1.0),
        COSBoolean.TRUE,
        COSNull.NULL,
        COSArray(),
    ],
    ids=["string", "int", "float", "bool", "null", "array"],
)
def test_gs_non_name_operand_silently_skips(operand: object) -> None:
    # Upstream returns after the instanceof COSName check.
    SetGraphicsStateParameters().process(_op("gs"), [operand])


def test_gs_get_state_name_extracts_leading_name() -> None:
    name = COSName.get_pdf_name("GS2")
    assert SetGraphicsStateParameters.get_state_name([name]) is name
    assert (
        SetGraphicsStateParameters.get_state_name([name, COSInteger.get(1)])
        is name
    )


def test_gs_get_state_name_guards_match_process() -> None:
    assert SetGraphicsStateParameters.get_state_name([]) is None
    assert SetGraphicsStateParameters.get_state_name([COSString("x")]) is None


def test_intent_get_intent_name_guards_match_process() -> None:
    name = COSName.get_pdf_name("Saturation")
    assert SetRenderingIntent.get_intent_name([name]) is name
    assert SetRenderingIntent.get_intent_name([]) is None
    assert SetRenderingIntent.get_intent_name([COSInteger.get(0)]) is None
