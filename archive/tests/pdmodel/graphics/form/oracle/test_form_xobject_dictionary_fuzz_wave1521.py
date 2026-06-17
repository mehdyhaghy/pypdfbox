"""Malformed PDFormXObject dictionary parity with PDFBox 3.0.7."""

from __future__ import annotations

from collections.abc import Callable

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
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.form.pd_transparency_group_attributes import (
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

CASE_IDS = (
    "base",
    "ft-i", "ft-f", "ft-w", "ft-z", "ft-ii", "ft-iz",
    "bb-v", "bb-s", "bb-n", "bb-w", "bb-z", "bb-ia", "bb-in", "bb-iz",
    "mx-v", "mx-s", "mx-n", "mx-w", "mx-z", "mx-ia", "mx-in", "mx-iz",
    "rs-v", "rs-w", "rs-z", "rs-id", "rs-iz",
    "gr-v", "gr-w", "gr-z", "gr-id", "gr-iz",
    "sp-i", "sp-f", "sp-w", "sp-z", "sp-ii", "sp-iz",
    "s1-i", "s1-f", "s1-w", "s1-z", "s1-ii", "s1-iz", "s1-both",
    "set", "clear",
)

FORM_TYPE = COSName.get_pdf_name("FormType")
BBOX = COSName.get_pdf_name("BBox")
MATRIX = COSName.get_pdf_name("Matrix")
RESOURCES = COSName.get_pdf_name("Resources")
GROUP = COSName.get_pdf_name("Group")
STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
STRUCT_PARENT = COSName.get_pdf_name("StructParent")
TAG = COSName.get_pdf_name("Tag")
KEYS = (FORM_TYPE, BBOX, MATRIX, RESOURCES, GROUP, STRUCT_PARENTS, STRUCT_PARENT)


def _indirect(value: COSBase | None, number: int = 100) -> COSObject:
    return COSObject(number, resolved=value)


def _numbers(*values: float) -> COSArray:
    return COSArray(COSFloat(value) for value in values)


def _tagged(value: str) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_name(TAG, value)
    return dictionary


def _build(case_id: str) -> PDFormXObject:
    stream = COSStream()
    if case_id == "base":
        pass
    elif case_id == "ft-i":
        stream.set_item(FORM_TYPE, COSInteger.get(7))
    elif case_id == "ft-f":
        stream.set_item(FORM_TYPE, COSFloat(7.75))
    elif case_id == "ft-w":
        stream.set_item(FORM_TYPE, COSName.get_pdf_name("Bad"))
    elif case_id == "ft-z":
        stream.set_item(FORM_TYPE, COSNull.NULL)
    elif case_id == "ft-ii":
        stream.set_item(FORM_TYPE, _indirect(COSInteger.get(8)))
    elif case_id == "ft-iz":
        stream.set_item(FORM_TYPE, _indirect(None))
    elif case_id == "bb-v":
        stream.set_item(BBOX, _numbers(4, 3, 1, 2))
    elif case_id == "bb-s":
        stream.set_item(BBOX, _numbers(1, 2, 3))
    elif case_id == "bb-n":
        array = _numbers(1, 2, 3, 4)
        array.set(2, COSName.get_pdf_name("Bad"))
        stream.set_item(BBOX, array)
    elif case_id == "bb-w":
        stream.set_item(BBOX, COSName.get_pdf_name("Bad"))
    elif case_id == "bb-z":
        stream.set_item(BBOX, COSNull.NULL)
    elif case_id == "bb-ia":
        stream.set_item(BBOX, _indirect(_numbers(0, 1, 2, 3)))
    elif case_id == "bb-in":
        array = _numbers(0, 1, 2, 3)
        array.set(2, _indirect(COSInteger.get(9)))
        stream.set_item(BBOX, array)
    elif case_id == "bb-iz":
        stream.set_item(BBOX, _indirect(None))
    elif case_id == "mx-v":
        stream.set_item(MATRIX, _numbers(2, 0, 0, 3, 4, 5))
    elif case_id == "mx-s":
        stream.set_item(MATRIX, _numbers(2, 0, 0, 3, 4))
    elif case_id == "mx-n":
        array = _numbers(2, 0, 0, 3, 4, 5)
        array.set(3, COSName.get_pdf_name("Bad"))
        stream.set_item(MATRIX, array)
    elif case_id == "mx-w":
        stream.set_item(MATRIX, COSInteger.ONE)
    elif case_id == "mx-z":
        stream.set_item(MATRIX, COSNull.NULL)
    elif case_id == "mx-ia":
        stream.set_item(MATRIX, _indirect(_numbers(2, 0, 0, 3, 4, 5)))
    elif case_id == "mx-in":
        array = _numbers(2, 0, 0, 3, 4, 5)
        array.set(4, _indirect(COSFloat(9)))
        stream.set_item(MATRIX, array)
    elif case_id == "mx-iz":
        stream.set_item(MATRIX, _indirect(None))
    elif case_id == "rs-v":
        stream.set_item(RESOURCES, _tagged("R"))
    elif case_id == "rs-w":
        stream.set_item(RESOURCES, COSInteger.ONE)
    elif case_id == "rs-z":
        stream.set_item(RESOURCES, COSNull.NULL)
    elif case_id == "rs-id":
        stream.set_item(RESOURCES, _indirect(_tagged("R")))
    elif case_id == "rs-iz":
        stream.set_item(RESOURCES, _indirect(None))
    elif case_id == "gr-v":
        stream.set_item(GROUP, _tagged("G"))
    elif case_id == "gr-w":
        stream.set_item(GROUP, COSInteger.ONE)
    elif case_id == "gr-z":
        stream.set_item(GROUP, COSNull.NULL)
    elif case_id == "gr-id":
        stream.set_item(GROUP, _indirect(_tagged("G")))
    elif case_id == "gr-iz":
        stream.set_item(GROUP, _indirect(None))
    elif case_id == "sp-i":
        stream.set_item(STRUCT_PARENTS, COSInteger.get(11))
    elif case_id == "sp-f":
        stream.set_item(STRUCT_PARENTS, COSFloat(11.75))
    elif case_id == "sp-w":
        stream.set_item(STRUCT_PARENTS, COSName.get_pdf_name("Bad"))
    elif case_id == "sp-z":
        stream.set_item(STRUCT_PARENTS, COSNull.NULL)
    elif case_id == "sp-ii":
        stream.set_item(STRUCT_PARENTS, _indirect(COSInteger.get(12)))
    elif case_id == "sp-iz":
        stream.set_item(STRUCT_PARENTS, _indirect(None))
    elif case_id == "s1-i":
        stream.set_item(STRUCT_PARENT, COSInteger.get(21))
    elif case_id == "s1-f":
        stream.set_item(STRUCT_PARENT, COSFloat(21.75))
    elif case_id == "s1-w":
        stream.set_item(STRUCT_PARENT, COSName.get_pdf_name("Bad"))
    elif case_id == "s1-z":
        stream.set_item(STRUCT_PARENT, COSNull.NULL)
    elif case_id == "s1-ii":
        stream.set_item(STRUCT_PARENT, _indirect(COSInteger.get(22)))
    elif case_id == "s1-iz":
        stream.set_item(STRUCT_PARENT, _indirect(None))
    elif case_id == "s1-both":
        stream.set_item(STRUCT_PARENT, COSInteger.get(21))
        stream.set_item(STRUCT_PARENTS, COSInteger.get(31))
    elif case_id in {"set", "clear"}:
        for key in KEYS[:-1]:
            stream.set_item(key, COSName.get_pdf_name("Bad"))
    else:
        raise AssertionError(case_id)

    form = PDFormXObject(stream)
    if case_id in {"set", "clear"}:
        form.set_form_type(6)
        form.set_b_box(PDRectangle.from_xywh(1, 2, 3, 4))
        form.set_matrix((2, 0, 0, 3, 4, 5))
        form.set_resources(PDResources(_tagged("R")))
        form.set_group_attributes(PDTransparencyGroupAttributes(_tagged("G")))
        form.set_struct_parents(14)
        if case_id == "clear":
            form.set_b_box(None)
            form.set_resources(None)
            form.set_group_attributes(None)
    return form


def _number(value: float) -> str:
    return f"{value:g}"


def _safe(function: Callable[[], str]) -> str:
    try:
        return function()
    except Exception:
        return "err"


def _bbox(form: PDFormXObject) -> str:
    def project() -> str:
        value = form.get_b_box()
        if value is None:
            return "none"
        return ",".join(
            _number(component)
            for component in (
                value.get_lower_left_x(),
                value.get_lower_left_y(),
                value.get_upper_right_x(),
                value.get_upper_right_y(),
            )
        )

    return _safe(project)


def _matrix(form: PDFormXObject) -> str:
    return _safe(lambda: ",".join(_number(value) for value in form.get_matrix()))


def _resources(form: PDFormXObject) -> str:
    def project() -> str:
        value = form.get_resources()
        if value is None:
            return "none"
        return value.get_cos_object().get_name(TAG) or "empty"

    return _safe(project)


def _group(form: PDFormXObject) -> str:
    def project() -> str:
        value = form.get_group_attributes()
        if value is None:
            return "none"
        return value.get_cos_object().get_name(TAG) or "dict"

    return _safe(project)


def _raw(dictionary: COSDictionary, key: COSName) -> str:
    value = dictionary.get_item(key)
    if value is None:
        return "absent"
    if isinstance(value, COSObject):
        return "indirect"
    if isinstance(value, COSArray):
        return "array:" + ":".join(type(item).__name__ for item in value)
    return type(value).__name__


def _project(case_id: str) -> str:
    form = _build(case_id)
    dictionary = form.get_cos_object()
    return (
        f"CASE {case_id} form={form.get_form_type()}"
        f" bbox={_bbox(form)} matrix={_matrix(form)}"
        f" resources={_resources(form)} group={_group(form)}"
        f" struct={form.get_struct_parents()}"
        f" raw={','.join(_raw(dictionary, key) for key in KEYS)}"
    )


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    return {
        line.split()[1]: line
        for line in run_probe_text("FormXObjectDictionaryFuzzProbe").splitlines()
    }


@requires_oracle
@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_form_xobject_dictionary_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _project(case_id) == java_lines[case_id]
