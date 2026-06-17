"""Differential malformed-dictionary audit for viewer preferences (wave 1521)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name

_BOOLEAN_KEYS = (
    "HideToolbar",
    "HideMenubar",
    "HideWindowUI",
    "FitWindow",
    "CenterWindow",
    "DisplayDocTitle",
)
_NAME_KEYS = (
    "NonFullScreenPageMode",
    "Direction",
    "ViewArea",
    "ViewClip",
    "PrintArea",
    "PrintClip",
    "Duplex",
    "PrintScaling",
)
_VALID_NAMES = (
    "UseOutlines",
    "R2L",
    "MediaBox",
    "BleedBox",
    "TrimBox",
    "ArtBox",
    "Simplex",
    "None",
)


def _indirect(value: COSBase) -> COSObject:
    return COSObject(1, resolved=value)


def _array(*values: COSBase) -> COSArray:
    result = COSArray()
    for value in values:
        result.add(value)
    return result


def _raw(dictionary: COSDictionary, key: str) -> str:
    value = dictionary.get_dictionary_object(_N(key))
    if value is None:
        return "null"
    if isinstance(value, COSBoolean):
        return f"bool:{str(value.value).lower()}"
    if isinstance(value, COSName):
        return f"name:{value.name}"
    if isinstance(value, COSString):
        return f"string:{value.get_string()}"
    if isinstance(value, COSInteger):
        return f"int:{value.value}"
    if isinstance(value, COSArray):
        return f"array:{value.size()}"
    if isinstance(value, COSDictionary):
        return "dict"
    return type(value).__name__


def _boolean_value(case_name: str) -> COSBase:
    return {
        "true": COSBoolean.TRUE,
        "false": COSBoolean.FALSE,
        "null": COSNull.NULL,
        "int": COSInteger.ONE,
        "name": _N("true"),
        "string": COSString("true"),
        "ind_true": _indirect(COSBoolean.TRUE),
        "ind_null": _indirect(COSNull.NULL),
    }[case_name]


def _python_booleans(case_name: str) -> str:
    dictionary = COSDictionary()
    if case_name != "absent":
        value = _boolean_value(case_name)
        for key in _BOOLEAN_KEYS:
            dictionary.set_item(_N(key), value)
    prefs = PDViewerPreferences(dictionary)
    values = (
        prefs.hide_toolbar(),
        prefs.hide_menubar(),
        prefs.hide_window_ui(),
        prefs.fit_window(),
        prefs.center_window(),
        prefs.display_doc_title(),
    )
    labels = ("ht", "hm", "hw", "fw", "cw", "dd")
    return " ".join(
        f"{label}={str(value).lower()}"
        for label, value in zip(labels, values, strict=True)
    )


@requires_oracle
@pytest.mark.parametrize(
    "case_name",
    ("absent", "true", "false", "null", "int", "name", "string", "ind_true", "ind_null"),
    ids=("abs", "t", "f", "null", "int", "name", "str", "it", "inull"),
)
def test_upstream_boolean_getters_match(case_name: str) -> None:
    assert _python_booleans(case_name) + "\n" == run_probe_text(
        "ViewerPreferencesFuzzProbe", "bool", case_name
    )


def _name_value(case_name: str, valid_value: str) -> COSBase:
    if case_name == "valid":
        return _N(valid_value)
    if case_name == "bogus":
        return _N("Bogus")
    if case_name == "string":
        return COSString("Text")
    if case_name == "empty":
        return COSString("")
    if case_name == "wrong":
        return COSInteger.ONE
    if case_name == "null":
        return COSNull.NULL
    if case_name == "ind_valid":
        return _indirect(_N(valid_value))
    if case_name == "ind_string":
        return _indirect(COSString("Text"))
    if case_name == "ind_null":
        return _indirect(COSNull.NULL)
    raise ValueError(case_name)


def _cell(value: str | None) -> str:
    return "null" if value is None else value


def _python_names(case_name: str) -> str:
    dictionary = COSDictionary()
    if case_name != "absent":
        for key, valid_value in zip(_NAME_KEYS, _VALID_NAMES, strict=True):
            dictionary.set_item(_N(key), _name_value(case_name, valid_value))
    prefs = PDViewerPreferences(dictionary)
    values = (
        prefs.get_non_full_screen_page_mode(),
        prefs.get_reading_direction(),
        prefs.get_view_area(),
        prefs.get_view_clip(),
        prefs.get_print_area(),
        prefs.get_print_clip(),
        prefs.get_duplex(),
        prefs.get_print_scaling(),
    )
    labels = ("nfs", "dir", "va", "vc", "pa", "pc", "dup", "ps")
    return " ".join(
        f"{label}={_cell(value)}"
        for label, value in zip(labels, values, strict=True)
    )


@requires_oracle
@pytest.mark.parametrize(
    "case_name",
    (
        "absent",
        "valid",
        "bogus",
        "string",
        "empty",
        "wrong",
        "null",
        "ind_valid",
        "ind_string",
        "ind_null",
    ),
    ids=("abs", "valid", "bogus", "str", "empty", "wrong", "null", "iv", "is", "inull"),
)
def test_upstream_name_getters_match(case_name: str) -> None:
    assert _python_names(case_name) + "\n" == run_probe_text(
        "ViewerPreferencesFuzzProbe", "name", case_name
    )


def _set_hide_toolbar(prefs: PDViewerPreferences) -> str:
    prefs.set_hide_toolbar(True)
    return "HideToolbar"


def _set_hide_menubar(prefs: PDViewerPreferences) -> str:
    prefs.set_hide_menubar(True)
    return "HideMenubar"


def _set_hide_window_ui(prefs: PDViewerPreferences) -> str:
    prefs.set_hide_window_ui(True)
    return "HideWindowUI"


def _set_fit_window(prefs: PDViewerPreferences) -> str:
    prefs.set_fit_window(True)
    return "FitWindow"


def _set_center_window(prefs: PDViewerPreferences) -> str:
    prefs.set_center_window(True)
    return "CenterWindow"


def _set_display_doc_title(prefs: PDViewerPreferences) -> str:
    prefs.set_display_doc_title(True)
    return "DisplayDocTitle"


def _set_nfs(prefs: PDViewerPreferences) -> str:
    prefs.set_non_full_screen_page_mode(
        PDViewerPreferences.NON_FULL_SCREEN_PAGE_MODE.UseOutlines
    )
    return "NonFullScreenPageMode"


def _set_direction(prefs: PDViewerPreferences) -> str:
    prefs.set_reading_direction(PDViewerPreferences.READING_DIRECTION.R2L)
    return "Direction"


def _set_view_area(prefs: PDViewerPreferences) -> str:
    prefs.set_view_area(PDViewerPreferences.BOUNDARY.MediaBox)
    return "ViewArea"


def _set_view_clip(prefs: PDViewerPreferences) -> str:
    prefs.set_view_clip(PDViewerPreferences.BOUNDARY.BleedBox)
    return "ViewClip"


def _set_print_area(prefs: PDViewerPreferences) -> str:
    prefs.set_print_area(PDViewerPreferences.BOUNDARY.TrimBox)
    return "PrintArea"


def _set_print_clip(prefs: PDViewerPreferences) -> str:
    prefs.set_print_clip(PDViewerPreferences.BOUNDARY.ArtBox)
    return "PrintClip"


def _set_duplex(prefs: PDViewerPreferences) -> str:
    prefs.set_duplex(PDViewerPreferences.DUPLEX.Simplex)
    return "Duplex"


def _set_print_scaling(prefs: PDViewerPreferences) -> str:
    prefs.set_print_scaling(PDViewerPreferences.PRINT_SCALING.None_)
    return "PrintScaling"


_SETTERS: tuple[tuple[str, Callable[[PDViewerPreferences], str]], ...] = (
    ("ht", _set_hide_toolbar),
    ("hm", _set_hide_menubar),
    ("hw", _set_hide_window_ui),
    ("fw", _set_fit_window),
    ("cw", _set_center_window),
    ("dd", _set_display_doc_title),
    ("nfs", _set_nfs),
    ("dir", _set_direction),
    ("va", _set_view_area),
    ("vc", _set_view_clip),
    ("pa", _set_print_area),
    ("pc", _set_print_clip),
    ("dup", _set_duplex),
    ("ps", _set_print_scaling),
)


@requires_oracle
@pytest.mark.parametrize(("setter", "apply"), _SETTERS, ids=[row[0] for row in _SETTERS])
def test_upstream_setter_storage_matches(
    setter: str, apply: Callable[[PDViewerPreferences], str]
) -> None:
    prefs = PDViewerPreferences()
    key = apply(prefs)
    assert _raw(prefs.get_cos_object(), key) + "\n" == run_probe_text(
        "ViewerPreferencesFuzzProbe", "setter", setter
    )


def _enrichment_value(surface: str, case_name: str) -> COSBase:
    values: dict[tuple[str, str], COSBase] = {
        ("pick", "true"): COSBoolean.TRUE,
        ("pick", "wrong"): COSInteger.ONE,
        ("pick", "null"): COSNull.NULL,
        ("pick", "ind_false"): _indirect(COSBoolean.FALSE),
        ("num", "pos"): COSInteger.get(3),
        ("num", "wrong"): _N("Three"),
        ("num", "null"): COSNull.NULL,
        ("num", "ind_zero"): _indirect(COSInteger.ZERO),
        ("range", "array"): _array(COSInteger.ONE, COSInteger.get(3)),
        ("range", "wrong"): COSDictionary(),
        ("range", "null"): COSNull.NULL,
        ("range", "ind_array"): _indirect(
            _array(COSInteger.TWO, COSInteger.get(4))
        ),
        ("enforce", "array"): _array(_N("PrintScaling"), _N("Duplex")),
        ("enforce", "wrong"): _N("PrintScaling"),
        ("enforce", "null"): COSNull.NULL,
        ("enforce", "ind_array"): _indirect(
            _array(_N("Direction"), COSInteger.ONE)
        ),
    }
    return values[(surface, case_name)]


def _enrichment_key(surface: str) -> str:
    return {
        "pick": "PickTrayByPDFSize",
        "num": "NumCopies",
        "range": "PrintPageRange",
        "enforce": "Enforce",
    }[surface]


def _python_enrichment(surface: str, case_name: str) -> str:
    dictionary = COSDictionary()
    key = _enrichment_key(surface)
    if case_name != "absent":
        dictionary.set_item(_N(key), _enrichment_value(surface, case_name))
    prefs = PDViewerPreferences(dictionary)
    raw = _raw(dictionary, key)
    if surface == "pick":
        value = str(prefs.pick_tray_by_pdf_size()).lower()
        return f"value={value} raw={raw}"
    if surface == "num":
        value = prefs.get_num_copies()
        raw_value = prefs.get_num_copies_raw()
        raw_cell = "null" if raw_value is None else str(raw_value)
        return f"value={value} raw_value={raw_cell} raw={raw}"
    if surface == "range":
        value = prefs.get_print_page_range()
        pairs = prefs.get_print_page_range_pairs()
        pair_cell = ",".join(f"{start}-{end}" for start, end in pairs) or "-"
        return (
            f"value={'null' if value is None else 'array'} "
            f"pairs={pair_cell} valid={str(prefs.is_valid_print_page_range()).lower()} "
            f"raw={raw}"
        )
    value = prefs.get_enforce()
    names = ",".join(prefs.get_enforce_names()) or "-"
    return (
        f"value={'null' if value is None else 'array'} names={names} "
        f"count={prefs.enforce_count()} raw={raw}"
    )


_ENRICHMENT_CASES = (
    ("pick", "absent"),
    ("pick", "true"),
    ("pick", "wrong"),
    ("pick", "null"),
    ("pick", "ind_false"),
    ("num", "absent"),
    ("num", "pos"),
    ("num", "wrong"),
    ("num", "null"),
    ("num", "ind_zero"),
    ("range", "absent"),
    ("range", "array"),
    ("range", "wrong"),
    ("range", "null"),
    ("range", "ind_array"),
    ("enforce", "absent"),
    ("enforce", "array"),
    ("enforce", "wrong"),
    ("enforce", "null"),
    ("enforce", "ind_array"),
)

# PDFBox 3.0.7 has no accessors for these PDF 1.7/2.0 entries. Pin both the
# enrichment result and PDFBox's live API/raw-dictionary projection explicitly;
# these are intentional extensions, not upstream parity claims.
_ENRICHMENT_PINS: dict[tuple[str, str], tuple[str, str]] = {
    ("pick", "absent"): (
        "value=false raw=null",
        "api=unsupported raw=null",
    ),
    ("pick", "true"): (
        "value=true raw=bool:true",
        "api=unsupported raw=bool:true",
    ),
    ("pick", "wrong"): (
        "value=false raw=int:1",
        "api=unsupported raw=int:1",
    ),
    ("pick", "null"): (
        "value=false raw=null",
        "api=unsupported raw=null",
    ),
    ("pick", "ind_false"): (
        "value=false raw=bool:false",
        "api=unsupported raw=bool:false",
    ),
    ("num", "absent"): (
        "value=1 raw_value=null raw=null",
        "api=unsupported raw=null",
    ),
    ("num", "pos"): (
        "value=3 raw_value=3 raw=int:3",
        "api=unsupported raw=int:3",
    ),
    ("num", "wrong"): (
        "value=1 raw_value=1 raw=name:Three",
        "api=unsupported raw=name:Three",
    ),
    ("num", "null"): (
        "value=1 raw_value=1 raw=null",
        "api=unsupported raw=null",
    ),
    ("num", "ind_zero"): (
        "value=1 raw_value=0 raw=int:0",
        "api=unsupported raw=int:0",
    ),
    ("range", "absent"): (
        "value=null pairs=- valid=true raw=null",
        "api=unsupported raw=null",
    ),
    ("range", "array"): (
        "value=array pairs=1-3 valid=true raw=array:2",
        "api=unsupported raw=array:2",
    ),
    ("range", "wrong"): (
        "value=null pairs=- valid=true raw=dict",
        "api=unsupported raw=dict",
    ),
    ("range", "null"): (
        "value=null pairs=- valid=true raw=null",
        "api=unsupported raw=null",
    ),
    ("range", "ind_array"): (
        "value=array pairs=2-4 valid=true raw=array:2",
        "api=unsupported raw=array:2",
    ),
    ("enforce", "absent"): (
        "value=null names=- count=0 raw=null",
        "api=unsupported raw=null",
    ),
    ("enforce", "array"): (
        "value=array names=PrintScaling,Duplex count=2 raw=array:2",
        "api=unsupported raw=array:2",
    ),
    ("enforce", "wrong"): (
        "value=null names=- count=0 raw=name:PrintScaling",
        "api=unsupported raw=name:PrintScaling",
    ),
    ("enforce", "null"): (
        "value=null names=- count=0 raw=null",
        "api=unsupported raw=null",
    ),
    ("enforce", "ind_array"): (
        "value=array names=Direction count=1 raw=array:2",
        "api=unsupported raw=array:2",
    ),
}


@requires_oracle
@pytest.mark.parametrize(
    ("surface", "case_name"),
    _ENRICHMENT_CASES,
    ids=[f"{surface[0]}-{case[:3]}" for surface, case in _ENRICHMENT_CASES],
)
def test_enrichment_accessors_are_two_sided_pins(
    surface: str, case_name: str
) -> None:
    python_actual = _python_enrichment(surface, case_name)
    java_actual = run_probe_text(
        "ViewerPreferencesFuzzProbe", "enrichment", surface, case_name
    ).rstrip("\n")
    python_expected, java_expected = _ENRICHMENT_PINS[(surface, case_name)]
    assert python_actual == python_expected
    assert java_actual == java_expected
