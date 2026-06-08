"""Malformed and cyclic article thread/bead differential fuzzing."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.interactive.pagenavigation import PDThread, PDThreadBead
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_SHAPES = (
    "absent",
    "null",
    "wrong",
    "direct",
    "indirect",
    "ind_null",
    "ind_wrong",
    "nested",
)
_NULL_LINK_CASES = tuple(
    f"{prefix}_{shape}"
    for prefix in ("n", "v")
    for shape in ("absent", "null", "wrong", "ind_null", "ind_wrong", "nested")
)
# Python cannot expose PDFBox's null-backed PDThreadBead wrapper safely, and
# append_bead intentionally repairs a missing /N instead of raising.
_INTENTIONAL_CASES = (*_NULL_LINK_CASES, "append_missing")


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _result(accessor: Callable[[], str]) -> str:
    try:
        return accessor()
    except Exception as exc:  # noqa: BLE001 - mirrors the Java Throwable arm
        return f"ERR:{type(exc).__name__}"


def _indirect(value: COSBase) -> COSObject:
    return COSObject(1, resolved=value)


def _set_shape(
    owner: COSDictionary,
    key: COSName,
    shape: str,
    valid: COSBase,
) -> None:
    values: dict[str, COSBase | None] = {
        "absent": None,
        "null": COSNull.NULL,
        "wrong": COSInteger.ONE,
        "direct": valid,
        "indirect": _indirect(valid),
        "ind_null": _indirect(COSNull.NULL),
        "ind_wrong": _indirect(COSInteger.ONE),
        "nested": _indirect(_indirect(valid)),
    }
    value = values[shape]
    if value is not None:
        owner.set_item(key, value)


def _dictionary_result(expected: COSDictionary, actual: COSDictionary | None) -> str:
    if actual is None:
        return "null"
    return "same" if actual is expected else "other"


def _wrapper_result(expected: COSDictionary, wrapper: object | None) -> str:
    if wrapper is None:
        return "null"
    return _dictionary_result(expected, wrapper.get_cos_object())


def _number(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _rectangle_result(rectangle: PDRectangle | None) -> str:
    if rectangle is None:
        return "null"
    return ",".join(
        _number(value)
        for value in (
            rectangle.get_lower_left_x(),
            rectangle.get_lower_left_y(),
            rectangle.get_upper_right_x(),
            rectangle.get_upper_right_y(),
        )
    )


def _rectangle(*values: int) -> COSArray:
    return COSArray([COSInteger.get(value) for value in values])


def _accessor_cases() -> dict[str, str]:
    cases: dict[str, str] = {}
    accessors = {
        "t": ("T", lambda bead: bead.get_thread()),
        "n": ("N", lambda bead: bead.get_next_bead()),
        "v": ("V", lambda bead: bead.get_previous_bead()),
        "p": ("P", lambda bead: bead.get_page()),
    }
    for shape in _SHAPES:
        info = COSDictionary()
        thread_dictionary = COSDictionary()
        _set_shape(thread_dictionary, _name("I"), shape, info)
        thread = PDThread(thread_dictionary)
        cases[f"i_{shape}"] = _result(
            lambda info=info, thread=thread: _wrapper_result(
                info, thread.get_thread_info()
            )
        )

        first = COSDictionary()
        thread_dictionary = COSDictionary()
        _set_shape(thread_dictionary, _name("F"), shape, first)
        thread = PDThread(thread_dictionary)
        cases[f"f_{shape}"] = _result(
            lambda first=first, thread=thread: _wrapper_result(
                first, thread.get_first_bead()
            )
        )

        for prefix, (key, accessor) in accessors.items():
            expected = COSDictionary()
            bead_dictionary = COSDictionary()
            _set_shape(bead_dictionary, _name(key), shape, expected)
            bead = PDThreadBead(bead_dictionary)
            cases[f"{prefix}_{shape}"] = _result(
                lambda bead=bead, expected=expected, accessor=accessor: (
                    _wrapper_result(expected, accessor(bead))
                )
            )
    return cases


def _rectangle_cases() -> dict[str, str]:
    cases: dict[str, str] = {}
    for shape in _SHAPES:
        dictionary = COSDictionary()
        _set_shape(dictionary, _name("R"), shape, _rectangle(4, 3, 2, 1))
        bead = PDThreadBead(dictionary)
        cases[f"r_{shape}"] = _result(
            lambda bead=bead: _rectangle_result(bead.get_rectangle())
        )

    short_dictionary = COSDictionary()
    short_dictionary.set_item(_name("R"), _rectangle(7, 8))
    short_bead = PDThreadBead(short_dictionary)
    cases["r_short"] = _result(
        lambda: _rectangle_result(short_bead.get_rectangle())
    )

    bad_array = _rectangle(1, 2, 3)
    bad_array.add(COSString("x"))
    bad_dictionary = COSDictionary()
    bad_dictionary.set_item(_name("R"), bad_array)
    bad_bead = PDThreadBead(bad_dictionary)
    cases["r_bad"] = _result(lambda: _rectangle_result(bad_bead.get_rectangle()))
    return cases


def _link(
    owner: COSDictionary,
    key: str,
    first: COSDictionary,
    second: COSDictionary,
) -> str:
    value = owner.get_dictionary_object(_name(key))
    if value is None:
        return "null"
    if value is first:
        return "a"
    if value is second:
        return "b"
    return "other"


def _append_cases() -> dict[str, str]:
    first = PDThreadBead()
    second = PDThreadBead()
    first.append_bead(second)
    a = first.get_cos_object()
    b = second.get_cos_object()
    cases = {
        "append_two": ",".join(
            (
                _link(a, "N", a, b),
                _link(a, "V", a, b),
                _link(b, "N", a, b),
                _link(b, "V", a, b),
            )
        )
    }

    bare_dictionary = COSDictionary()
    bare = PDThreadBead(bare_dictionary)
    added = PDThreadBead()

    def append_missing() -> str:
        bare.append_bead(added)
        return _link(bare_dictionary, "N", bare_dictionary, added.get_cos_object())

    cases["append_missing"] = _result(append_missing)
    return cases


def _walk(start: COSDictionary) -> str:
    values: list[str] = []
    seen: set[int] = set()
    current: PDThreadBead | None = PDThreadBead(start)
    for _ in range(8):
        if current is None:
            return ",".join([*values, "null"])
        dictionary = current.get_cos_object()
        if id(dictionary) in seen:
            return ",".join([*values, "repeat"])
        seen.add(id(dictionary))
        values.append("a" if dictionary is start else "b")
        current = current.get_next_bead()
    return ",".join([*values, "limit"])


def _cycle_cases() -> dict[str, str]:
    self_cycle = COSDictionary()
    self_cycle.set_item(_name("N"), self_cycle)

    first = COSDictionary()
    second = COSDictionary()
    first.set_item(_name("N"), second)
    second.set_item(_name("N"), first)

    missing = COSDictionary()
    wrong = COSDictionary()
    wrong.set_item(_name("N"), COSInteger.ONE)

    indirect_self = COSDictionary()
    indirect_self.set_item(_name("N"), _indirect(indirect_self))

    dictionaries = {
        "walk_self": self_cycle,
        "walk_two": first,
        "walk_missing": missing,
        "walk_wrong": wrong,
        "walk_ind_self": indirect_self,
    }
    return {name: _result(lambda value=value: _walk(value)) for name, value in dictionaries.items()}


def _setter_cases() -> dict[str, str]:
    thread = PDThread()
    bead = PDThreadBead()
    thread.set_first_bead(bead)
    first_result = ",".join(
        (
            str(thread.get_first_bead().get_cos_object() is bead.get_cos_object()).lower(),
            str(bead.get_thread().get_cos_object() is thread.get_cos_object()).lower(),
        )
    )
    thread.set_first_bead(None)
    clear_first = str(thread.get_cos_object().get_item(_name("F")) is None).lower()

    bead.set_thread(thread)
    bead.set_page(PDPage())
    bead.set_rectangle(PDRectangle(1, 2, 3, 4))
    bead.set_thread(None)
    bead.set_page(None)
    bead.set_rectangle(None)
    clear_bead = ",".join(
        str(bead.get_cos_object().get_item(_name(key)) is None).lower()
        for key in ("T", "P", "R")
    )
    return {
        "set_first": first_result,
        "clear_first": clear_first,
        "clear_bead": clear_bead,
    }


def _python_cases() -> dict[str, str]:
    return {
        **_accessor_cases(),
        **_rectangle_cases(),
        **_append_cases(),
        **_cycle_cases(),
        **_setter_cases(),
    }


def _java_cases() -> dict[str, str]:
    output = run_probe_text("ThreadBeadCycleFuzzProbe")
    return {
        name: value
        for line in output.splitlines()
        for _, name, value in (line.split(" ", 2),)
    }


@requires_oracle
def test_thread_bead_malformed_shapes_match_pdfbox() -> None:
    python = _python_cases()
    java = _java_cases()
    assert {
        key: value for key, value in python.items() if key not in _INTENTIONAL_CASES
    } == {key: value for key, value in java.items() if key not in _INTENTIONAL_CASES}


@requires_oracle
def test_thread_bead_defensive_differences_are_pinned() -> None:
    python = _python_cases()
    java = _java_cases()
    for case_id in _NULL_LINK_CASES:
        assert python[case_id] == "null"
        assert java[case_id] == "wrap:null"
    assert python["append_missing"] == "b"
    assert java["append_missing"] == "ERR:NullPointerException"


@pytest.mark.parametrize(
    ("case_id", "expected"),
    (("r_short", "0,0,7,8"), ("r_bad", "1,0,3,2")),
    ids=("short", "mixed"),
)
def test_malformed_rectangles_use_pdfbox_zero_padding(
    case_id: str,
    expected: str,
) -> None:
    assert _rectangle_cases()[case_id] == expected


@pytest.mark.parametrize(
    ("case_id", "expected"),
    (
        ("walk_self", "a,repeat"),
        ("walk_two", "a,b,repeat"),
        ("walk_missing", "a,null"),
        ("walk_wrong", "a,null"),
        ("walk_ind_self", "a,repeat"),
    ),
    ids=("self", "two", "missing", "wrong", "indirect"),
)
def test_thread_bead_walks_terminate(case_id: str, expected: str) -> None:
    assert _cycle_cases()[case_id] == expected
