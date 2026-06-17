"""Malformed /MK appearance-characteristics parity with PDFBox 3.0.7.

Differential oracle for ``PDAppearanceCharacteristicsDictionary`` against the
live PDFBox 3.0.7 jar: malformed ``/R`` rotation, ``/BC`` // ``/BG`` colour
arrays of every arity (including the transparent 0-length and invalid 2/5),
non-numeric colour components, wrong-typed captions, and icon entries that are
non-stream / indirect.

Upstream 3.0.7 ``PDAppearanceCharacteristicsDictionary`` exposes the three
icon getters as ``PDFormXObject`` (``getNormalIcon`` // ``getRolloverIcon`` //
``getAlternateIcon``); the pypdfbox ``get_*_icon_form`` companions are the
parity surface for those. The probe therefore projects the typed form getters.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
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


def _color_array(size: int) -> COSArray:
    return COSArray([COSFloat(0.25 * (index + 1)) for index in range(size)])


def _mk(dictionary: COSDictionary) -> PDAppearanceCharacteristicsDictionary:
    return PDAppearanceCharacteristicsDictionary(dictionary)


def _case(case_id: str) -> PDAppearanceCharacteristicsDictionary:
    d = COSDictionary()
    if case_id == "empty":
        return _mk(d)
    if case_id.startswith("r_"):
        rotations = {
            "r_0": COSInteger.get(0),
            "r_90": COSInteger.get(90),
            "r_180": COSInteger.get(180),
            "r_270": COSInteger.get(270),
            "r_45": COSInteger.get(45),
            "r_360": COSInteger.get(360),
            "r_neg90": COSInteger.get(-90),
            "r_12345": COSInteger.get(12345),
            "r_float": COSFloat(90.5),
            "r_name": COSName.get_pdf_name("Bad"),
            "r_string": COSString("90"),
        }
        d.set_item(_R, rotations[case_id])
        return _mk(d)
    if case_id.startswith("color_"):
        size = int(case_id.split("_", 1)[1])
        d.set_item(_BC, _color_array(size))
        d.set_item(_BG, _color_array(size))
        return _mk(d)
    if case_id == "bc_mixed":
        d.set_item(
            _BC,
            COSArray([COSFloat(0.1), COSName.get_pdf_name("X"), COSFloat(0.3)]),
        )
        return _mk(d)
    if case_id == "bc_name":
        d.set_item(_BC, COSName.get_pdf_name("Bad"))
        return _mk(d)
    if case_id == "bc_null":
        d.set_item(_BC, COSNull.NULL)
        return _mk(d)
    if case_id == "bc_dict":
        d.set_item(_BC, COSDictionary())
        return _mk(d)
    if case_id == "bc_indirect":
        d.set_item(_BC, _indirect(_color_array(3)))
        return _mk(d)
    if case_id == "cap_ok":
        d.set_item(_CA, COSString("Submit"))
        d.set_item(_RC, COSString("Roll Over"))
        d.set_item(_AC, COSString("Alt"))
        return _mk(d)
    if case_id == "cap_name":
        d.set_item(_CA, COSName.get_pdf_name("NotString"))
        return _mk(d)
    if case_id == "cap_int":
        d.set_item(_CA, COSInteger.get(5))
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
    "r_neg90",
    "r_12345",
    "r_float",
    "r_name",
    "r_string",
    "color_0",
    "color_1",
    "color_2",
    "color_3",
    "color_4",
    "color_5",
    "bc_mixed",
    "bc_name",
    "bc_null",
    "bc_dict",
    "bc_indirect",
    "cap_ok",
    "cap_name",
    "cap_int",
    "icon_stream",
    "icon_dict",
    "icon_name",
    "icon_null",
    "icon_indirect",
)


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("AppearanceCharacteristicsFuzzProbe").splitlines()
    return {line.split(maxsplit=2)[1]: line for line in lines}


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_appearance_characteristics_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit(case_id, _case(case_id)) == java_lines[case_id]
