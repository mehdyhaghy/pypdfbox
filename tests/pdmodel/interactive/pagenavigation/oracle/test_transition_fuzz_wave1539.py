"""Malformed page-transition (``/Trans``) dictionary differential fuzzing.

Mirrors ``oracle/probes/TransitionFuzzProbe.java``: builds the same ~50 edge
cases, wraps each in :class:`PDTransition`, and projects every typed accessor
PDFBox exposes (style / duration / dimension / motion / direction / fly-scale /
opaque flag). The Java oracle is the source of truth; when java/javac/the jar
are present the differential test asserts byte-for-byte equality, and a handful
of value-pinned tests document the contract even when the oracle is offline.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.interactive.pagenavigation import PDTransition
from tests.oracle.harness import requires_oracle, run_probe_text

_S = COSName.get_pdf_name("S")
_D = COSName.get_pdf_name("D")
_DM = COSName.get_pdf_name("Dm")
_M = COSName.get_pdf_name("M")
_DI = COSName.get_pdf_name("Di")
_SS = COSName.get_pdf_name("SS")
_B = COSName.get_pdf_name("B")


def _result(accessor: Callable[[], str]) -> str:
    try:
        return accessor()
    except Exception as exc:  # noqa: BLE001 - mirrors the Java Throwable arm
        return f"ERR:{type(exc).__name__}"


def _fmt(value: float) -> str:
    """Canonical float rendering matching TransitionFuzzProbe.fmt."""
    if value != value:  # NaN
        return "NaN"
    if value == float("inf"):
        return "Inf"
    if value == float("-inf"):
        return "-Inf"
    if value == int(value):
        return str(int(value))
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    return s


def _direction(value: COSBase | None) -> str:
    if isinstance(value, COSInteger):
        return str(value.long_value())
    if isinstance(value, COSName):
        return value.name
    if value is None:
        return "null"
    return type(value).__name__


def _project(trans: PDTransition) -> str:
    style = _result(trans.get_style)
    dur = _result(lambda: _fmt(trans.get_duration()))
    dim = _result(trans.get_dimension)
    motion = _result(trans.get_motion)
    direction = _result(lambda: _direction(trans.get_direction_cos()))
    scale = _result(lambda: _fmt(trans.get_fly_scale()))
    flag = _result(lambda: str(trans.is_fly_area_opaque()).lower())
    return (
        f"S={style} D={dur} Dm={dim} M={motion} "
        f"Di={direction} SS={scale} B={flag}"
    )


def _base() -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.TYPE, "Trans")  # type: ignore[attr-defined]
    return d


def _name_dict(key: COSName, name: str) -> COSDictionary:
    d = _base()
    d.set_name(key, name)
    return d


def _item_dict(key: COSName, value: COSBase) -> COSDictionary:
    d = _base()
    d.set_item(key, value)
    return d


_STYLES = (
    "Split",
    "Blinds",
    "Box",
    "Wipe",
    "Dissolve",
    "Glitter",
    "R",
    "Fly",
    "Push",
    "Cover",
    "Uncover",
    "Fade",
    "Bogus",
)


def _python_cases() -> dict[str, str]:
    cases: dict[str, COSDictionary] = {}

    cases["empty"] = _base()

    for style in _STYLES:
        cases[f"style_{style}"] = _name_dict(_S, style)
    cases["style_string"] = _item_dict(_S, COSString("Wipe"))
    cases["style_int"] = _item_dict(_S, COSInteger.get(5))
    cases["style_null"] = _item_dict(_S, COSNull.NULL)

    cases["dur_zero"] = _item_dict(_D, COSInteger.get(0))
    cases["dur_neg"] = _item_dict(_D, COSFloat(-2.5))
    cases["dur_huge"] = _item_dict(_D, COSFloat(1.0e9))
    cases["dur_frac"] = _item_dict(_D, COSFloat(0.25))
    cases["dur_int"] = _item_dict(_D, COSInteger.get(3))
    cases["dur_name"] = _name_dict(_D, "fast")
    cases["dur_string"] = _item_dict(_D, COSString("3"))

    cases["dim_h"] = _name_dict(_DM, "H")
    cases["dim_v"] = _name_dict(_DM, "V")
    cases["dim_bogus"] = _name_dict(_DM, "X")
    cases["dim_string"] = _item_dict(_DM, COSString("V"))

    cases["motion_i"] = _name_dict(_M, "I")
    cases["motion_o"] = _name_dict(_M, "O")
    cases["motion_bogus"] = _name_dict(_M, "Q")
    cases["motion_string"] = _item_dict(_M, COSString("O"))

    cases["dir_0"] = _item_dict(_DI, COSInteger.get(0))
    cases["dir_90"] = _item_dict(_DI, COSInteger.get(90))
    cases["dir_180"] = _item_dict(_DI, COSInteger.get(180))
    cases["dir_270"] = _item_dict(_DI, COSInteger.get(270))
    cases["dir_315"] = _item_dict(_DI, COSInteger.get(315))
    cases["dir_999"] = _item_dict(_DI, COSInteger.get(999))
    cases["dir_none"] = _item_dict(_DI, COSName.get_pdf_name("None"))
    cases["dir_badname"] = _item_dict(_DI, COSName.get_pdf_name("Left"))
    cases["dir_string"] = _item_dict(_DI, COSString("90"))
    cases["dir_float"] = _item_dict(_DI, COSFloat(90.0))

    cases["ss_unit"] = _item_dict(_SS, COSFloat(1.0))
    cases["ss_half"] = _item_dict(_SS, COSFloat(0.5))
    cases["ss_neg"] = _item_dict(_SS, COSFloat(-1.0))
    cases["ss_name"] = _name_dict(_SS, "big")

    b_true = _base()
    b_true.set_boolean(_B, True)
    cases["b_true"] = b_true
    b_false = _base()
    b_false.set_boolean(_B, False)
    cases["b_false"] = b_false
    cases["b_int"] = _item_dict(_B, COSInteger.ONE)
    cases["b_name"] = _name_dict(_B, "true")

    fly = _base()
    fly.set_name(_S, "Fly")
    fly.set_float(_D, 2)
    fly.set_name(_DM, "V")
    fly.set_name(_M, "O")
    fly.set_item(_DI, COSName.get_pdf_name("None"))
    fly.set_float(_SS, 0.7)
    fly.set_boolean(_B, True)
    cases["fly_full"] = fly

    return {name: _result(lambda d=d: _project(PDTransition(d))) for name, d in cases.items()}


def _java_cases() -> dict[str, str]:
    output = run_probe_text("TransitionFuzzProbe")
    result: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            continue
        _, name, value = line.split(" ", 2)
        result[name] = value
    return result


@requires_oracle
def test_transition_malformed_shapes_match_pdfbox() -> None:
    assert _python_cases() == _java_cases()


def test_case_count() -> None:
    # 51 cases: 1 empty + 13 styles + 3 style-shapes + 7 dur + 4 dim + 4 motion
    # + 10 dir + 4 ss + 4 b + 1 fly_full.
    assert len(_python_cases()) == 51


@pytest.mark.parametrize(
    ("case_id", "expected"),
    (
        ("empty", "S=R D=1 Dm=H M=I Di=0 SS=1 B=false"),
        ("style_string", "S=Wipe D=1 Dm=H M=I Di=0 SS=1 B=false"),
        ("style_null", "S=R D=1 Dm=H M=I Di=0 SS=1 B=false"),
        ("dur_neg", "S=R D=-2.5 Dm=H M=I Di=0 SS=1 B=false"),
        ("dur_name", "S=R D=1 Dm=H M=I Di=0 SS=1 B=false"),
        ("dim_bogus", "S=R D=1 Dm=X M=I Di=0 SS=1 B=false"),
        ("dim_string", "S=R D=1 Dm=V M=I Di=0 SS=1 B=false"),
        ("motion_string", "S=R D=1 Dm=H M=O Di=0 SS=1 B=false"),
        ("dir_none", "S=R D=1 Dm=H M=I Di=None SS=1 B=false"),
        ("dir_badname", "S=R D=1 Dm=H M=I Di=Left SS=1 B=false"),
        ("dir_string", "S=R D=1 Dm=H M=I Di=COSString SS=1 B=false"),
        ("dir_float", "S=R D=1 Dm=H M=I Di=COSFloat SS=1 B=false"),
        ("b_int", "S=R D=1 Dm=H M=I Di=0 SS=1 B=false"),
        ("b_name", "S=R D=1 Dm=H M=I Di=0 SS=1 B=false"),
        ("fly_full", "S=Fly D=2 Dm=V M=O Di=None SS=0.7 B=true"),
    ),
    ids=(
        "empty",
        "style_string",
        "style_null",
        "dur_neg",
        "dur_name",
        "dim_bogus",
        "dim_string",
        "motion_string",
        "dir_none",
        "dir_badname",
        "dir_string",
        "dir_float",
        "b_int",
        "b_name",
        "fly_full",
    ),
)
def test_transition_pinned_values(case_id: str, expected: str) -> None:
    # PDFBox-3.0.7-derived expected values, pinned so the contract holds even
    # when the live oracle is offline. Defensive defaults: a non-name /S, /Dm,
    # /M falls back to the spec default; a non-name /Di renders its raw COSBase
    # (PDFBox getDirection() returns the entry verbatim); a non-boolean /B is
    # ignored.
    assert _python_cases()[case_id] == expected
