"""Differential malformed-dictionary audit for the signature /Prop_Build
build-properties dictionaries — PDPropBuild + PDPropBuildDataDict (wave 1538).

Mirrors ``oracle/probes/PropBuildFuzzProbe.java`` against the live Apache
PDFBox 3.0.7 jar. Two surfaces:

* ``build`` — PDPropBuild.get_filter / get_pub_sec / get_app sub-dictionary
  presence over absent / dict / wrong-type / null / indirect entries.
* ``data`` — each PDPropBuildDataDict accessor over a malformed entry.
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
    COSString,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build import PDPropBuild
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build_data_dict import (
    PDPropBuildDataDict,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _indirect(value: COSBase) -> COSObject:
    return COSObject(1, resolved=value)


def _array(*values: COSBase) -> COSArray:
    result = COSArray()
    for value in values:
        result.add(value)
    return result


def _nz(value: str | None) -> str:
    return "null" if value is None else value


# ---------------------------------------------------------------------------
# build surface: /Filter //PubSec //App sub-dict presence
# ---------------------------------------------------------------------------

_BUILD_CASES = (
    "absent",
    "dict",
    "wrong_int",
    "wrong_name",
    "wrong_array",
    "null",
    "ind_dict",
    "ind_null",
)


def _sub_dict_value(case_name: str) -> COSBase | None:
    return {
        "absent": None,
        "dict": COSDictionary(),
        "wrong_int": COSInteger.ONE,
        "wrong_name": _N("Filter"),
        "wrong_array": _array(COSInteger.ONE),
        "null": COSNull.NULL,
        "ind_dict": _indirect(COSDictionary()),
        "ind_null": _indirect(COSNull.NULL),
    }[case_name]


def _python_build(case_name: str) -> str:
    dictionary = COSDictionary()
    value = _sub_dict_value(case_name)
    if value is not None:
        dictionary.set_item(_N("Filter"), value)
        dictionary.set_item(_N("PubSec"), value)
        dictionary.set_item(_N("App"), value)
    build = PDPropBuild(dictionary)

    def present(wrapper: PDPropBuildDataDict | None) -> str:
        return "null" if wrapper is None else "dict"

    return (
        f"filter={present(build.get_filter())}"
        f" pubsec={present(build.get_pub_sec())}"
        f" app={present(build.get_app())}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "case_name",
    _BUILD_CASES,
    ids=("abs", "dict", "wint", "wname", "warr", "null", "idict", "inull"),
)
def test_build_subdict_presence_matches(case_name: str) -> None:
    assert _python_build(case_name) + "\n" == run_probe_text(
        "PropBuildFuzzProbe", "build", case_name
    )


# ---------------------------------------------------------------------------
# data surface: PDPropBuildDataDict accessors over malformed entries
# ---------------------------------------------------------------------------

_DATA_FIELDS = (
    "name",
    "date",
    "version",
    "revision",
    "minrev",
    "prerelease",
    "os",
    "noefont",
    "trusted",
)

_DATA_CASES = (
    "absent",
    "name",
    "string",
    "empty_string",
    "int",
    "neg_int",
    "float",
    "bool_true",
    "bool_false",
    "name_arr",
    "empty_arr",
    "str_arr",
    "null",
    "ind_string",
    "ind_int",
    "ind_name_arr",
)

_CASE_IDS = (
    "abs",
    "name",
    "str",
    "estr",
    "int",
    "nint",
    "float",
    "bt",
    "bf",
    "narr",
    "earr",
    "sarr",
    "null",
    "istr",
    "iint",
    "inarr",
)


def _field_value(case_name: str) -> COSBase | None:
    return {
        "absent": None,
        "name": _N("Acrobat"),
        "string": COSString("Acrobat"),
        "empty_string": COSString(""),
        "int": COSInteger.get(7),
        "neg_int": COSInteger.get(-5),
        "float": COSFloat(2.5),
        "bool_true": COSBoolean.TRUE,
        "bool_false": COSBoolean.FALSE,
        "name_arr": _array(_N("Win"), _N("Mac")),
        "empty_arr": _array(),
        "str_arr": _array(COSString("Win")),
        "null": COSNull.NULL,
        "ind_string": _indirect(COSString("Acrobat")),
        "ind_int": _indirect(COSInteger.get(7)),
        "ind_name_arr": _indirect(_array(_N("Win"))),
    }[case_name]


_KEY_FOR_FIELD = {
    "name": "Name",
    "date": "Date",
    "version": "REx",
    "revision": "R",
    "minrev": "V",
    "prerelease": "PreRelease",
    "os": "OS",
    "noefont": "NonEFontNoWarn",
    "trusted": "TrustedMode",
}


def _project_field(d: PDPropBuildDataDict, field: str) -> str:
    if field == "name":
        return _nz(d.get_name())
    if field == "date":
        return _nz(d.get_date())
    if field == "version":
        return _nz(d.get_version())
    if field == "revision":
        return str(d.get_revision())
    if field == "minrev":
        return str(d.get_minimum_revision())
    if field == "prerelease":
        return str(d.get_pre_release()).lower()
    if field == "os":
        return _nz(d.get_os())
    if field == "noefont":
        return str(d.get_non_e_font_no_warn()).lower()
    if field == "trusted":
        return str(d.get_trusted_mode()).lower()
    raise ValueError(field)


def _python_data(field: str, case_name: str) -> str:
    dictionary = COSDictionary()
    value = _field_value(case_name)
    if value is not None:
        dictionary.set_item(_N(_KEY_FOR_FIELD[field]), value)
    d = PDPropBuildDataDict(dictionary)
    try:
        result = _project_field(d, field)
    except Exception as exc:  # noqa: BLE001 - mirror probe's generic catch
        result = f"ERR:{type(exc).__name__}"
    return f"value={result}"


@requires_oracle
@pytest.mark.parametrize("field", _DATA_FIELDS)
@pytest.mark.parametrize("case_name", _DATA_CASES, ids=_CASE_IDS)
def test_data_accessor_matches(field: str, case_name: str) -> None:
    assert _python_data(field, case_name) + "\n" == run_probe_text(
        "PropBuildFuzzProbe", "data", field, case_name
    )
