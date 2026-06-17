"""Malformed PDTilingPattern dictionary accessor parity with PDFBox 3.0.7."""

from __future__ import annotations

import struct

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
)
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_PAINT_TYPE = COSName.get_pdf_name("PaintType")
_TILING_TYPE = COSName.get_pdf_name("TilingType")
_BBOX = COSName.get_pdf_name("BBox")
_X_STEP = COSName.get_pdf_name("XStep")
_Y_STEP = COSName.get_pdf_name("YStep")
_MATRIX = COSName.get_pdf_name("Matrix")
_RESOURCES = COSName.get_pdf_name("Resources")


def _indirect(value: COSBase | None, number: int) -> COSObject:
    return COSObject(number, resolved=value)


def _numbers(*values: float) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


def _bits(value: float) -> str:
    return struct.pack(">f", value).hex()


def _bbox(pattern: PDTilingPattern) -> str:
    try:
        value = pattern.get_b_box()
        if value is None:
            return "none"
        return ",".join(
            _bits(component)
            for component in (
                value.get_lower_left_x(),
                value.get_lower_left_y(),
                value.get_upper_right_x(),
                value.get_upper_right_y(),
            )
        )
    except Exception as exception:
        return f"ERR:{type(exception).__name__}"


def _matrix(pattern: PDTilingPattern) -> str:
    try:
        return ",".join(_bits(value) for value in pattern.get_matrix())
    except Exception as exception:
        return f"ERR:{type(exception).__name__}"


def _resources(pattern: PDTilingPattern) -> str:
    try:
        value = pattern.get_resources()
        if value is None:
            return "none"
        return "stream" if isinstance(value.get_cos_object(), COSStream) else "dict"
    except Exception as exception:
        return f"ERR:{type(exception).__name__}"


def _emit(name: str, dictionary: COSDictionary) -> str:
    pattern = PDTilingPattern(dictionary)
    return (
        f"CASE {name} paint={pattern.get_paint_type()}"
        f" tiling={pattern.get_tiling_type()} bbox={_bbox(pattern)}"
        f" x={_bits(pattern.get_x_step())} y={_bits(pattern.get_y_step())}"
        f" matrix={_matrix(pattern)} resources={_resources(pattern)}"
    )


def _value_cases(key: COSName, prefix: str, start: int) -> dict[str, COSDictionary]:
    values: tuple[COSBase, ...] = (
        COSInteger.get(7),
        COSFloat(7.75),
        COSInteger.get(4294967297),
        COSName.get_pdf_name("Bad"),
        COSNull.NULL,
        _indirect(COSInteger.get(9), start),
        _indirect(None, start + 1),
    )
    ids = ("i", "f", "wide", "name", "null", "ii", "inull")
    cases: dict[str, COSDictionary] = {}
    for case_id, value in zip(ids, values, strict=True):
        dictionary = COSDictionary()
        dictionary.set_item(key, value)
        cases[f"{prefix}-{case_id}"] = dictionary
    return cases


def _array_cases(
    key: COSName, prefix: str, rectangle: bool, start: int
) -> dict[str, COSDictionary]:
    overflow = (
        COSArray([COSFloat(1.0e20), COSFloat(-1.0e20), COSFloat(-1.0e20), COSFloat(1.0e20)])
        if rectangle
        else COSArray(
            [
                COSInteger.get(16777217),
                COSInteger.ZERO,
                COSInteger.ZERO,
                COSInteger.ONE,
                COSInteger.get(16777217),
                COSInteger.get(-16777217),
            ]
        )
    )
    values: tuple[COSBase, ...] = (
        _numbers(),
        _numbers(1, 2),
        _numbers(4, 3, 2, 1),
        _numbers(1, 2, 3, 4, 5, 6, 7),
        COSArray(
            [
                COSInteger.ONE,
                COSName.get_pdf_name("Bad"),
                COSNull.NULL,
                COSFloat(4.5),
                COSInteger.get(5),
                COSInteger.get(6),
            ]
        ),
        _indirect(
            _numbers(4, 3, 2, 1) if rectangle else _numbers(1, 2, 3, 4, 5, 6),
            start,
        ),
        _indirect(COSName.get_pdf_name("Bad"), start + 1),
        _indirect(None, start + 2),
        COSArray(
            [
                _indirect(COSInteger.ONE, start + 3),
                _indirect(COSFloat(2.5), start + 4),
                COSInteger.get(3),
                COSInteger.get(4),
                COSInteger.get(5),
                COSInteger.get(6),
            ]
        ),
        overflow,
    )
    ids = (
        "empty",
        "short",
        "full",
        "long",
        "mixed",
        "ind",
        "iname",
        "inull",
        "ielems",
        "overflow",
    )
    cases: dict[str, COSDictionary] = {}
    for case_id, value in zip(ids, values, strict=True):
        dictionary = COSDictionary()
        dictionary.set_item(key, value)
        cases[f"{prefix}-{case_id}"] = dictionary
    return cases


def _build_cases() -> dict[str, COSDictionary]:
    cases = {
        "default": PDTilingPattern().get_cos_object(),
        "empty": COSDictionary(),
    }
    cases.update(_value_cases(_PAINT_TYPE, "paint", 10))
    cases.update(_value_cases(_TILING_TYPE, "tiling", 20))
    cases.update(_value_cases(_X_STEP, "x", 30))
    cases.update(_value_cases(_Y_STEP, "y", 40))
    for name, key in (("bbox", _BBOX), ("matrix", _MATRIX)):
        for suffix, value in (("name", COSName.get_pdf_name("Bad")), ("null", COSNull.NULL)):
            dictionary = COSDictionary()
            dictionary.set_item(key, value)
            cases[f"{name}-{suffix}"] = dictionary
    cases.update(_array_cases(_BBOX, "bbox", True, 50))
    cases.update(_array_cases(_MATRIX, "matrix", False, 60))
    resource_values: tuple[COSBase, ...] = (
        COSDictionary(),
        COSStream(),
        COSName.get_pdf_name("Bad"),
        COSNull.NULL,
        _indirect(COSDictionary(), 70),
        _indirect(COSStream(), 71),
        _indirect(None, 72),
    )
    for suffix, value in zip(
        ("dict", "stream", "name", "null", "idict", "istream", "inull"),
        resource_values,
        strict=True,
    ):
        dictionary = COSDictionary()
        dictionary.set_item(_RESOURCES, value)
        cases[f"res-{suffix}"] = dictionary
    return cases


_CASES = _build_cases()
_CASE_IDS = tuple(_CASES)
_SHORT_IDS = tuple(f"c{index:02d}" for index in range(len(_CASE_IDS)))
# Wave 1524 (PDRectangle agent) aligned ``PDRectangle.from_cos_array`` with the
# lenient upstream ``new PDRectangle(COSArray)`` constructor (zero-pad short
# arrays, coerce non-numeric/null slots to 0). ``PDTilingPattern.get_b_box`` now
# converges with PDFBox for ``bbox-mixed`` (a 4-entry array with mistyped slots),
# which previously diverged. ``bbox-empty`` and ``bbox-short`` remain pinned: they
# are gated earlier by ``_b_box_or_none``'s ``value.size() < 4`` guard (pypdfbox
# returns ``none`` where upstream ``getBBox`` has no size check and builds a
# zero-padded rectangle). Removing that guard would change ``has_b_box`` semantics
# and is a candidate for its own oracle-verified wave.
_PINNED_BBOX = {
    "bbox-empty": (
        "none",
        "00000000,00000000,00000000,00000000",
    ),
    "bbox-short": (
        "none",
        "00000000,00000000,3f800000,40000000",
    ),
}


def _raw(dictionary: COSDictionary, key: COSName) -> str:
    value = dictionary.get_item(key)
    if value is None:
        return "absent"
    if isinstance(value, COSObject):
        resolved = value.get_object()
        return f"indirect:{'null' if resolved is None else type(resolved).__name__}"
    return type(value).__name__


def _setter_lines() -> tuple[str, str]:
    pattern = PDTilingPattern(COSStream())
    pattern.set_paint_type(2)
    pattern.set_tiling_type(3)
    pattern.set_x_step(7.25)
    pattern.set_y_step(-8.5)
    pattern.set_b_box(PDRectangle.from_xywh(4, 3, 2, 1))
    pattern.set_matrix([1.5, 2.5, 3.5, 4.5, 5.5, 6.5])
    pattern.set_resources(PDResources())
    dictionary = pattern.get_cos_object()
    values = (
        "SET values"
        f" paint={_raw(dictionary, _PAINT_TYPE)}"
        f" tiling={_raw(dictionary, _TILING_TYPE)}"
        f" bbox={_raw(dictionary, _BBOX)}"
        f" x={_raw(dictionary, _X_STEP)}"
        f" y={_raw(dictionary, _Y_STEP)}"
        f" matrix={_raw(dictionary, _MATRIX)}"
        f" resources={_raw(dictionary, _RESOURCES)}"
        f" projection={_bbox(pattern)};{_matrix(pattern)}"
    )
    pattern.set_b_box(None)
    pattern.set_matrix(None)
    pattern.set_resources(None)
    clear = (
        f"SET clear action=ok bbox={_raw(dictionary, _BBOX)}"
        f" matrix={_raw(dictionary, _MATRIX)}"
        f" resources={_raw(dictionary, _RESOURCES)}"
    )
    return values, clear


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("TilingPatternDictionaryFuzzProbe").splitlines()
    return {" ".join(line.split(maxsplit=2)[:2]): line for line in lines}


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS, ids=_SHORT_IDS)
def test_dictionary_accessors_match_pdfbox(
    case_id: str, java_lines: dict[str, str]
) -> None:
    python_line = _emit(case_id, _CASES[case_id])
    java_line = java_lines[f"CASE {case_id}"]
    if case_id in _PINNED_BBOX:
        python_bbox, java_bbox = _PINNED_BBOX[case_id]
        assert python_line.split(" bbox=", 1)[1].split(" ", 1)[0] == python_bbox
        assert java_line.split(" bbox=", 1)[1].split(" ", 1)[0] == java_bbox
        assert python_line.replace(f"bbox={python_bbox}", f"bbox={java_bbox}") == java_line
        return
    assert python_line == java_line


@requires_oracle
def test_setter_storage_matches_pdfbox(java_lines: dict[str, str]) -> None:
    python_line = _setter_lines()[0]
    assert python_line == java_lines[" ".join(python_line.split(maxsplit=2)[:2])]


@requires_oracle
def test_none_matrix_setter_divergence_is_pinned(
    java_lines: dict[str, str]
) -> None:
    python_line = _setter_lines()[1]
    assert python_line == (
        "SET clear action=ok bbox=absent matrix=absent resources=absent"
    )
    assert java_lines["SET clear"] == (
        "SET clear action=ERR:NullPointerException bbox=absent"
        " matrix=COSArray resources=absent"
    )
