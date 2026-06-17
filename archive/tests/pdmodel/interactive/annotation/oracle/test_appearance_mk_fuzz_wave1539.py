"""Malformed /MK widget appearance-characteristics parity with PDFBox 3.0.7.

Differential oracle for ``PDAppearanceCharacteristicsDictionary`` against the
live PDFBox 3.0.7 jar (``oracle/probes/AppearanceMkFuzzProbe.java``), wave 1539.

This widens ``AppearanceCharacteristicsFuzzProbe`` (wave 1529) on the READ
surface of every accessor PDFBox 3.0.7 actually ships — verified with
``javap``:

    getRotation, getBorderColour, getBackground, getNormalCaption,
    getRolloverCaption, getAlternateCaption, getNormalIcon, getRolloverIcon,
    getAlternateIcon.

New ground here: ``/R`` rotation read as the raw int over negative-non-90,
multi-turn (720), float-truncation (positive and negative) and ``COSNull``;
``/BC`` integer components and a non-numeric (name) component; an empty caption
string; an indirect caption; and asymmetric ``/BC``-empty / ``/BG``-gray.

DIVERGENCE — pypdfbox extensions with no 3.0.7 oracle counterpart:
``get_text_position`` (``/TP``), ``get_icon_fit`` (``/IF``) and the
``PDIconFit`` class do NOT exist on upstream 3.0.7's
``PDAppearanceCharacteristicsDictionary`` (it has only the nine getters above).
They are forward-looking pypdfbox additions, so they are pinned Python-side in
``test_text_position_and_icon_fit_pinned`` below (no probe projection).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (  # noqa: E501
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_icon_fit import PDIconFit
from tests.oracle.harness import requires_oracle, run_probe_text

_R = COSName.get_pdf_name("R")
_BC = COSName.get_pdf_name("BC")
_BG = COSName.get_pdf_name("BG")
_CA = COSName.get_pdf_name("CA")
_RC = COSName.get_pdf_name("RC")
_AC = COSName.get_pdf_name("AC")
_I = COSName.get_pdf_name("I")
_RI = COSName.get_pdf_name("RI")
_IX = COSName.get_pdf_name("IX")
_IF = COSName.get_pdf_name("IF")
_TP = COSName.get_pdf_name("TP")


def _indirect(value: COSBase) -> COSObject:
    return COSObject(99, resolved=value)


def _num(value: float) -> str:
    return str(int(value)) if value == int(value) else repr(value)


def _color(color: object) -> str:
    if color is None:
        return "none"
    name = color.get_color_space().get_name()
    components = ",".join(_num(component) for component in color.get_components())
    return f"{name}[{components}]"


def _text(value: str | None) -> str:
    return "none" if value is None else value.replace(" ", "_")


def _icon(icon: object) -> str:
    return "none" if icon is None else "form"


def _emit(name: str, mk: PDAppearanceCharacteristicsDictionary) -> str:
    return (
        f"CASE {name} rot={mk.get_rotation()}"
        f" bc={_color(mk.get_border_colour())}"
        f" bg={_color(mk.get_background())}"
        f" ca={_text(mk.get_normal_caption())}"
        f" rc={_text(mk.get_rollover_caption())}"
        f" ac={_text(mk.get_alternate_caption())}"
        f" ni={_icon(mk.get_normal_icon_form())}"
        f" ri={_icon(mk.get_rollover_icon_form())}"
        f" ai={_icon(mk.get_alternate_icon_form())}"
    )


def _color_array(*values: float) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


def _mk(dictionary: COSDictionary) -> PDAppearanceCharacteristicsDictionary:
    return PDAppearanceCharacteristicsDictionary(dictionary)


def _case(case_id: str) -> PDAppearanceCharacteristicsDictionary:
    d = COSDictionary()
    if case_id == "empty":
        return _mk(d)

    rotations = {
        "r_0": COSInteger.get(0),
        "r_90": COSInteger.get(90),
        "r_180": COSInteger.get(180),
        "r_270": COSInteger.get(270),
        "r_45": COSInteger.get(45),
        "r_360": COSInteger.get(360),
        "r_720": COSInteger.get(720),
        "r_neg90": COSInteger.get(-90),
        "r_neg180": COSInteger.get(-180),
        "r_neg270": COSInteger.get(-270),
        "r_neg45": COSInteger.get(-45),
        "r_12345": COSInteger.get(12345),
        "r_99999": COSInteger.get(99999),
        "r_float_pos": COSFloat(90.9),
        "r_float_neg": COSFloat(-90.9),
        "r_name": COSName.get_pdf_name("Bad"),
        "r_string": COSString("90"),
        "r_null": COSNull.NULL,
    }
    if case_id in rotations:
        d.set_item(_R, rotations[case_id])
        return _mk(d)

    if case_id.startswith("color_"):
        size = int(case_id.split("_", 1)[1])
        arr = _color_array(*[0.2 * (i + 1) for i in range(size)])
        d.set_item(_BC, COSArray(list(arr)))
        d.set_item(_BG, COSArray(list(arr)))
        return _mk(d)
    if case_id == "asym":
        d.set_item(_BC, _color_array())
        d.set_item(_BG, _color_array(0.5))
        return _mk(d)
    if case_id == "bc_mixed":
        d.set_item(
            _BC,
            COSArray([COSFloat(0.1), COSName.get_pdf_name("X"), COSFloat(0.3)]),
        )
        return _mk(d)
    if case_id == "bc_int":
        d.set_item(
            _BC,
            COSArray([COSInteger.get(0), COSInteger.get(1), COSInteger.get(0)]),
        )
        return _mk(d)
    if case_id == "bc_name":
        d.set_item(_BC, COSName.get_pdf_name("Bad"))
        return _mk(d)
    if case_id == "bc_dict":
        d.set_item(_BC, COSDictionary())
        return _mk(d)
    if case_id == "bc_indirect":
        d.set_item(_BC, _indirect(_color_array(0.1, 0.2, 0.3)))
        return _mk(d)

    if case_id == "cap_ok":
        d.set_item(_CA, COSString("Submit Now"))
        d.set_item(_RC, COSString("Roll"))
        d.set_item(_AC, COSString("Alt"))
        return _mk(d)
    if case_id == "cap_empty":
        d.set_item(_CA, COSString(""))
        return _mk(d)
    if case_id == "cap_name":
        d.set_item(_CA, COSName.get_pdf_name("NotString"))
        return _mk(d)
    if case_id == "cap_int":
        d.set_item(_CA, COSInteger.get(5))
        return _mk(d)
    if case_id == "cap_indirect":
        d.set_item(_CA, _indirect(COSString("Ind")))
        return _mk(d)

    if case_id == "icon_stream":
        d.set_item(_I, COSStream())
        d.set_item(_RI, COSStream())
        d.set_item(_IX, COSStream())
        return _mk(d)
    if case_id == "icon_dict":
        d.set_item(_I, COSDictionary())
        return _mk(d)
    if case_id == "icon_name":
        d.set_item(_I, COSName.get_pdf_name("Bad"))
        return _mk(d)
    if case_id == "icon_null":
        d.set_item(_I, COSNull.NULL)
        return _mk(d)
    if case_id == "icon_indirect":
        d.set_item(_I, _indirect(COSStream()))
        return _mk(d)

    raise AssertionError(f"unknown case {case_id}")


_CASE_IDS = (
    "empty",
    "r_0",
    "r_90",
    "r_180",
    "r_270",
    "r_45",
    "r_360",
    "r_720",
    "r_neg90",
    "r_neg180",
    "r_neg270",
    "r_neg45",
    "r_12345",
    "r_99999",
    "r_float_pos",
    "r_float_neg",
    "r_name",
    "r_string",
    "r_null",
    "color_0",
    "color_1",
    "color_2",
    "color_3",
    "color_4",
    "color_5",
    "asym",
    "bc_mixed",
    "bc_int",
    "bc_name",
    "bc_dict",
    "bc_indirect",
    "cap_ok",
    "cap_empty",
    "cap_name",
    "cap_int",
    "cap_indirect",
    "icon_stream",
    "icon_dict",
    "icon_name",
    "icon_null",
    "icon_indirect",
)


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("AppearanceMkFuzzProbe").splitlines()
    return {line.split(maxsplit=2)[1]: line for line in lines}


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_appearance_mk_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit(case_id, _case(case_id)) == java_lines[case_id]


# ---------------------------------------------------------------------------
# pypdfbox-only surfaces: /TP text-position + /IF icon-fit.
#
# PDFBox 3.0.7 has NO getTextPosition / getIconFit / PDIconFit; these are
# forward-looking pypdfbox extensions, so there is no live oracle to diff
# against. The expected values below are pinned to pypdfbox's documented
# semantics (PDF 32000-1 §12.5.6.19 Table 189 + the icon-fit sub-dict).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (COSInteger.get(0), 0),
        (COSInteger.get(1), 1),
        (COSInteger.get(6), 6),
        (COSInteger.get(7), 7),
        (COSInteger.get(-1), -1),
        (COSInteger.get(99), 99),
        (COSFloat(2.5), 2),  # get_int truncates toward zero
        (COSName.get_pdf_name("Bad"), 0),  # wrong type -> default
        (COSString("3"), 0),  # string is not numeric -> default
        (COSNull.NULL, 0),
    ],
)
def test_text_position_pinned(value: COSBase, expected: int) -> None:
    d = COSDictionary()
    d.set_item(_TP, value)
    assert PDAppearanceCharacteristicsDictionary(d).get_text_position() == expected


def test_text_position_default_absent() -> None:
    assert PDAppearanceCharacteristicsDictionary(COSDictionary()).get_text_position() == 0


def _icon_fit_dict(
    sw: COSBase | None = None,
    s: COSBase | None = None,
    a: COSArray | None = None,
    fb: COSBase | None = None,
) -> COSDictionary:
    d = COSDictionary()
    if sw is not None:
        d.set_item(COSName.get_pdf_name("SW"), sw)
    if s is not None:
        d.set_item(COSName.get_pdf_name("S"), s)
    if a is not None:
        d.set_item(COSName.get_pdf_name("A"), a)
    if fb is not None:
        d.set_item(COSName.get_pdf_name("FB"), fb)
    return d


def test_icon_fit_absent() -> None:
    assert PDAppearanceCharacteristicsDictionary(COSDictionary()).get_icon_fit() is None


def test_icon_fit_empty_defaults() -> None:
    d = COSDictionary()
    d.set_item(_IF, COSDictionary())
    fit = PDAppearanceCharacteristicsDictionary(d).get_icon_fit()
    assert isinstance(fit, PDIconFit)
    # Spec defaults for an empty icon-fit dict.
    assert fit.get_scale_option() == "A"
    assert fit.get_scale_type() == "P"
    assert fit.get_fractional_space() == (0.5, 0.5)
    assert fit.is_fit_to_bounds() is False


def test_icon_fit_full() -> None:
    d = COSDictionary()
    d.set_item(
        _IF,
        _icon_fit_dict(
            sw=COSName.get_pdf_name("S"),
            s=COSName.get_pdf_name("A"),
            a=COSArray([COSFloat(0.25), COSFloat(0.75)]),
            fb=COSBoolean.TRUE,
        ),
    )
    fit = PDAppearanceCharacteristicsDictionary(d).get_icon_fit()
    assert fit is not None
    assert fit.get_scale_option() == "S"
    assert fit.get_scale_type() == "A"
    assert fit.get_fractional_space() == (0.25, 0.75)
    assert fit.is_fit_to_bounds() is True


@pytest.mark.parametrize(
    ("array", "expected"),
    [
        (COSArray(), (0.5, 0.5)),  # arity 0 -> default
        (COSArray([COSFloat(0.3)]), (0.5, 0.5)),  # arity 1 -> default
        (COSArray([COSFloat(0.1), COSFloat(0.2)]), (0.1, 0.2)),
        (
            COSArray([COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)]),
            (0.1, 0.2),
        ),  # arity 3 -> first two
    ],
)
def test_icon_fit_fractional_space_arity(
    array: COSArray, expected: tuple[float, float]
) -> None:
    d = COSDictionary()
    d.set_item(_IF, _icon_fit_dict(a=array))
    fit = PDAppearanceCharacteristicsDictionary(d).get_icon_fit()
    assert fit is not None
    got = fit.get_fractional_space()
    assert got == pytest.approx(expected)


@pytest.mark.parametrize(
    "value",
    [
        COSName.get_pdf_name("Bad"),
        COSArray([COSFloat(0.5), COSFloat(0.5)]),
        COSNull.NULL,
    ],
)
def test_icon_fit_wrong_type_is_none(value: COSBase) -> None:
    d = COSDictionary()
    d.set_item(_IF, value)
    assert PDAppearanceCharacteristicsDictionary(d).get_icon_fit() is None
