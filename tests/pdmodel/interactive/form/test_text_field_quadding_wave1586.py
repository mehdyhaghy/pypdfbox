"""Wave 1586 — per-widget text-field quadding (``/Q``) resolution.

Verifies that :class:`PDAppearanceGenerator` resolves text alignment
(quadding) *per widget*, matching upstream
``AppearanceGeneratorHelper.getTextAlign(widget)``:

    cos = widget.getCOSObject();
    return cos.getInt(COSName.Q, field.getQ());

i.e. a widget's own ``/Q`` (if present) wins, otherwise the field's
(inheritable) ``/Q`` is used as the fallback. ``/Q`` values: ``0`` =
left, ``1`` = centered, ``2`` = right.

Before wave 1586 the worker hoisted ``quadding = field.get_q()`` out of
the widget loop and applied that single value to every widget, so a
widget carrying its own ``/Q`` different from the field-level ``/Q`` was
ignored (the wave-1585 DEFERRED item). These tests exercise the real
API — set a value, regenerate the ``/AP /N`` appearance, then read the
``Td`` x-offset / alignment from the generated content stream.

Parity reference: upstream
``org.apache.pdfbox.pdmodel.interactive.form.AppearanceGeneratorHelper.getTextAlign``
+ ``PlainTextFormatter`` quadding offsets. Assertions check the
content-stream ``Td`` x-position relationship between left / centre /
right alignment, not byte-identical output (the lite port uses a
height-based auto-size heuristic, a documented divergence).
"""

from __future__ import annotations

import re

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT = COSName.get_pdf_name("Rect")
_DA = COSName.get_pdf_name("DA")
_AP = COSName.get_pdf_name("AP")
_N = COSName.get_pdf_name("N")
_Q = COSName.get_pdf_name("Q")
_KIDS = COSName.get_pdf_name("Kids")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_WIDGET = COSName.get_pdf_name("Widget")

# Wide rect so left / centre / right x-offsets are clearly separated.
_WIDTH = 200.0
_HEIGHT = 20.0
_DEFAULT_DA = "/Helv 10 Tf 0 g"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _single_widget_field(
    *, da: str | None = _DEFAULT_DA, field_q: int | None = None
) -> PDTextField:
    """A text field that acts as its own (single) widget — ``/Q`` set on
    the field dictionary is both the field-level and widget-level ``/Q``.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, _WIDTH, _HEIGHT))
    if da is not None:
        cos.set_string(_DA, da)
    if field_q is not None:
        tf.set_q(field_q)
    return tf


def _multi_widget_field(
    *,
    widget_qs: list[int | None],
    field_q: int | None = None,
    da: str | None = _DEFAULT_DA,
) -> PDTextField:
    """Build a text field with one ``/Kids`` widget per entry in
    ``widget_qs``. ``None`` means the widget carries no ``/Q`` (so it
    falls back to the field's ``/Q``); an int sets that widget's own
    ``/Q``. ``field_q`` sets the field-level (inheritable) ``/Q``.
    """
    form = PDAcroForm()
    tf = PDTextField(form)
    field_cos = tf.get_cos_object()
    if da is not None:
        field_cos.set_string(_DA, da)
    if field_q is not None:
        tf.set_q(field_q)

    widgets: list[PDAnnotationWidget] = []
    for wq in widget_qs:
        wcos = COSDictionary()
        wcos.set_item(_SUBTYPE, _WIDGET)
        wcos.set_item(_RECT, _rect(0, 0, _WIDTH, _HEIGHT))
        if wq is not None:
            wcos.set_item(_Q, COSInteger.get(wq))
        widgets.append(PDAnnotationWidget(wcos))
    tf.set_widgets(widgets)
    return tf


def _set_value(tf: PDTextField, value: str) -> None:
    PDAppearanceGenerator().set_appearance_value(tf, value)


def _widget_body(tf: PDTextField, index: int = 0) -> str:
    widget_cos = tf.get_widgets()[index].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    return n.create_input_stream().read().decode("latin-1")


def _td_x(body: str) -> float:
    """Return the x operand of the first ``Td`` operator (the text
    insertion x-offset, which encodes the quadding alignment)."""
    m = re.search(r"(-?[\d.]+) (-?[\d.]+) Td", body)
    assert m is not None, f"no Td found in:\n{body}"
    return float(m.group(1))


def _td_x_for(tf: PDTextField, value: str, index: int = 0) -> float:
    _set_value(tf, value)
    return _td_x(_widget_body(tf, index))


# A short value so centre / right alignment shifts x noticeably within
# the wide rect.
_VALUE = "Hi"


# ---------------------------------------------------------------------------
# single-widget field — field /Q applies to that widget
# ---------------------------------------------------------------------------


def test_single_widget_default_left_when_no_q() -> None:
    # No /Q anywhere → default left (0). Left alignment puts text near the
    # left edge (small x, ~2pt margin).
    tf = _single_widget_field()
    x = _td_x_for(tf, _VALUE)
    assert x < _WIDTH / 4.0


@pytest.mark.parametrize("q", [0, 1, 2], ids=["left", "center", "right"])
def test_single_widget_honours_field_q(q: int) -> None:
    tf = _single_widget_field(field_q=q)
    _set_value(tf, _VALUE)
    assert _AP in tf.get_widgets()[0].get_cos_object().key_set()


def test_single_widget_q_orders_left_center_right() -> None:
    # The same value at left / centre / right must have a strictly
    # increasing x-offset (left < centre < right) inside a wide rect.
    x_left = _td_x_for(_single_widget_field(field_q=0), _VALUE)
    x_center = _td_x_for(_single_widget_field(field_q=1), _VALUE)
    x_right = _td_x_for(_single_widget_field(field_q=2), _VALUE)
    assert x_left < x_center < x_right


def test_single_widget_center_is_roughly_middle() -> None:
    # Centre alignment of a short string lands near the rect midpoint.
    x_center = _td_x_for(_single_widget_field(field_q=1), _VALUE)
    assert _WIDTH / 4.0 < x_center < _WIDTH * 3.0 / 4.0


# ---------------------------------------------------------------------------
# multi-widget field — per-widget /Q wins, else field /Q fallback
# ---------------------------------------------------------------------------


def test_multi_widget_all_inherit_field_q() -> None:
    # Field /Q=2 (right), neither widget carries its own /Q → both
    # widgets render right-aligned (same x).
    tf = _multi_widget_field(widget_qs=[None, None], field_q=2)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    assert x0 == x1
    # Right-aligned → x well past the midpoint.
    assert x0 > _WIDTH / 2.0


def test_multi_widget_one_overrides_q_right() -> None:
    # Field /Q=0 (left); widget 0 keeps the field default (left), widget 1
    # overrides /Q=2 (right). The two widgets must diverge.
    tf = _multi_widget_field(widget_qs=[None, 2], field_q=0)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    assert x0 < x1
    assert x0 < _WIDTH / 4.0  # widget 0: field-default left
    assert x1 > _WIDTH / 2.0  # widget 1: own /Q=2 right


def test_multi_widget_one_overrides_q_center() -> None:
    # Field /Q=0 (left); widget 1 overrides /Q=1 (center).
    tf = _multi_widget_field(widget_qs=[None, 1], field_q=0)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    assert x0 < x1
    assert x1 > _WIDTH / 4.0  # widget 1 centred → past the left quarter


def test_multi_widget_widget_q_overrides_field_q() -> None:
    # Field /Q=2 (right); widget 0 overrides /Q=0 (left). Widget 0's own
    # /Q must beat the inheritable field /Q.
    tf = _multi_widget_field(widget_qs=[0, None], field_q=2)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    assert x0 < x1  # widget 0 forced left, widget 1 inherits right
    assert x0 < _WIDTH / 4.0
    assert x1 > _WIDTH / 2.0


def test_multi_widget_no_q_anywhere_both_left() -> None:
    tf = _multi_widget_field(widget_qs=[None, None], field_q=None)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    assert x0 == x1
    assert x0 < _WIDTH / 4.0  # both default left


@pytest.mark.parametrize(
    ("w0_q", "w1_q", "field_q"),
    [
        (0, 1, 2),
        (0, 2, 1),
        (1, 0, 2),
        (1, 2, 0),
        (2, 0, 1),
        (2, 1, 0),
    ],
    ids=[
        "w0L-w1C-fR",
        "w0L-w1R-fC",
        "w0C-w1L-fR",
        "w0C-w1R-fL",
        "w0R-w1L-fC",
        "w0R-w1C-fL",
    ],
)
def test_multi_widget_each_widget_own_q(
    w0_q: int, w1_q: int, field_q: int
) -> None:
    # Both widgets carry their own /Q; the field /Q must be ignored. The
    # relative x-ordering must follow the widgets' own quadding values.
    tf = _multi_widget_field(widget_qs=[w0_q, w1_q], field_q=field_q)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    # Higher /Q (more rightward) ⇒ larger x.
    if w0_q < w1_q:
        assert x0 < x1
    elif w0_q > w1_q:
        assert x0 > x1
    else:  # pragma: no cover - params never give equal qs
        assert x0 == x1


def test_multi_widget_three_widgets_mixed() -> None:
    # Three widgets: own-left, inherit (field centre), own-right.
    tf = _multi_widget_field(widget_qs=[0, None, 2], field_q=1)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    x2 = _td_x(_widget_body(tf, 2))
    assert x0 < x1 < x2


def test_multi_widget_field_q_zero_widget_overrides() -> None:
    # Field /Q absent (defaults left); a single widget overrides /Q=2.
    tf = _multi_widget_field(widget_qs=[None, 2], field_q=None)
    _set_value(tf, _VALUE)
    x0 = _td_x(_widget_body(tf, 0))
    x1 = _td_x(_widget_body(tf, 1))
    assert x0 < x1
    assert x0 < _WIDTH / 4.0
    assert x1 > _WIDTH / 2.0


# ---------------------------------------------------------------------------
# direct unit test of the resolver helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("widget_q", "field_q", "expected"),
    [
        (None, 0, 0),
        (None, 1, 1),
        (None, 2, 2),
        (0, 2, 0),
        (1, 0, 1),
        (2, 0, 2),
        (2, 1, 2),
    ],
    ids=[
        "inherit-left",
        "inherit-center",
        "inherit-right",
        "override-left-over-right",
        "override-center-over-left",
        "override-right-over-left",
        "override-right-over-center",
    ],
)
def test_resolve_text_align(
    widget_q: int | None, field_q: int, expected: int
) -> None:
    wcos = COSDictionary()
    if widget_q is not None:
        wcos.set_item(_Q, COSInteger.get(widget_q))
    widget = PDAnnotationWidget(wcos)
    assert (
        PDAppearanceGenerator._resolve_text_align(widget, field_q) == expected
    )


def test_resolve_text_align_default_fallback() -> None:
    # No widget /Q, field fallback 0 → 0.
    widget = PDAnnotationWidget(COSDictionary())
    assert PDAppearanceGenerator._resolve_text_align(widget, 0) == 0
