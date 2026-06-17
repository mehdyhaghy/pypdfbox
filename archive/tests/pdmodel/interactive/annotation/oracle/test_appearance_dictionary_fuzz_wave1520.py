"""Malformed appearance dictionary/entry/stream parity with PDFBox 3.0.7."""

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
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name("N")
_R = COSName.get_pdf_name("R")
_D = COSName.get_pdf_name("D")
_AP_KEYS = (_N, _R, _D)
_VALUE_IDS = ("stream", "dict", "scalar", "null", "istream", "idict", "iscalar", "inull")
_DICTIONARY_IDS = (
    "default",
    "empty",
    *(f"{key}_{value}" for key in ("n", "r", "d") for value in _VALUE_IDS),
    "states_mixed",
    "set_all",
    "set_clear",
)
_SHORT_DICTIONARY_IDS = (
    "def",
    "empty",
    *(f"{key}-{index}" for key in ("n", "r", "d") for index in range(8)),
    "states",
    "set",
    "clear",
)
_STREAM_IDS = ("default", "malformed", "indirect")


def _indirect(value: COSBase, number: int) -> COSObject:
    return COSObject(number, resolved=value)


def _hex(value: str) -> str:
    encoded = value.encode("utf-8").hex()
    return encoded or "empty"


def _message(exception: Exception) -> str:
    return str(exception).replace(" ", "_") or type(exception).__name__


def _entry(value: PDAppearanceEntry | None) -> str:
    if value is None:
        return "none"
    parts = ["stream" if value.is_stream() else "dict"]
    try:
        stream = value.get_appearance_stream()
        appearance = "none" if stream is None else "stream"
    except Exception as exception:
        appearance = f"ERR:{_message(exception)}"
    parts.append(f"as={appearance}")
    try:
        names = sorted(_hex(name) for name in value.get_sub_dictionary())
        states = ",".join(names) if names else "empty"
    except Exception as exception:
        states = f"ERR:{_message(exception)}"
    parts.append(f"sub={states}")
    return ";".join(parts)


def _raw(dictionary: COSDictionary, key: COSName) -> str:
    value = dictionary.get_item(key)
    if value is None:
        return "absent"
    if isinstance(value, COSObject):
        resolved = value.get_object()
        return f"indirect:{'null' if resolved is None else type(resolved).__name__}"
    return type(value).__name__


def _emit_dictionary(name: str, appearance: PDAppearanceDictionary) -> str:
    dictionary = appearance.get_cos_object()
    raw = ",".join(_raw(dictionary, key) for key in _AP_KEYS)
    return (
        f"CASE {name} n={_entry(appearance.get_normal_appearance())}"
        f" r={_entry(appearance.get_rollover_appearance())}"
        f" d={_entry(appearance.get_down_appearance())} raw={raw}"
    )


def _value(value_id: str, number: int) -> COSBase:
    direct: dict[str, Callable[[], COSBase]] = {
        "stream": COSStream,
        "dict": COSDictionary,
        "scalar": lambda: COSName.get_pdf_name("Bad"),
        "null": lambda: COSNull.NULL,
    }
    if value_id.startswith("i"):
        return _indirect(direct[value_id[1:]](), number)
    return direct[value_id]()


def _dictionary_case(case_id: str) -> PDAppearanceDictionary:
    if case_id == "default":
        return PDAppearanceDictionary()
    if case_id == "empty":
        return PDAppearanceDictionary(COSDictionary())
    if case_id == "states_mixed":
        states = COSDictionary()
        states.set_item(COSName.get_pdf_name("On"), COSStream())
        states.set_item(COSName.get_pdf_name("Indirect"), _indirect(COSStream(), 31))
        states.set_item(COSName.get_pdf_name("Scalar"), COSInteger.get(4))
        states.set_item(COSName.get_pdf_name("Null"), COSNull.NULL)
        states.set_item(COSName.get_pdf_name("Dict"), COSDictionary())
        states.set_item(COSName.get_pdf_name(""), COSStream())
        states.set_item(COSName.get_pdf_name("A B"), COSStream())
        states.set_item(COSName.get_pdf_name("A/B"), COSStream())
        dictionary = COSDictionary()
        dictionary.set_item(_N, states)
        return PDAppearanceDictionary(dictionary)
    if case_id in ("set_all", "set_clear"):
        appearance = PDAppearanceDictionary(COSDictionary())
        appearance.set_normal_appearance(PDAppearanceEntry(COSStream()))
        appearance.set_rollover_appearance(PDAppearanceStream(COSStream()))
        down = COSDictionary()
        down.set_item(COSName.get_pdf_name("Pressed"), COSStream())
        appearance.set_down_appearance(PDAppearanceEntry(down))
        if case_id == "set_clear":
            appearance.set_normal_appearance(None)
            appearance.set_rollover_appearance(None)
            appearance.set_down_appearance(None)
        return appearance

    key_id, value_id = case_id.split("_", 1)
    dictionary = COSDictionary()
    dictionary.set_item(_N, COSStream())
    key = {"n": _N, "r": _R, "d": _D}[key_id]
    dictionary.set_item(key, _value(value_id, 10 + _DICTIONARY_IDS.index(case_id)))
    return PDAppearanceDictionary(dictionary)


def _matrix(stream: PDAppearanceStream) -> str:
    return ",".join(f"{component:g}" for component in stream.get_matrix())


def _stream_case(case_id: str) -> COSStream:
    stream = COSStream()
    if case_id == "malformed":
        stream.set_item(COSName.get_pdf_name("FormType"), COSName.get_pdf_name("Bad"))
        stream.set_item(COSName.get_pdf_name("StructParents"), COSFloat(4.75))
        stream.set_item(COSName.get_pdf_name("BBox"), COSName.get_pdf_name("Bad"))
        stream.set_item(COSName.get_pdf_name("Matrix"), COSName.get_pdf_name("Bad"))
        stream.set_item(COSName.get_pdf_name("Resources"), COSNull.NULL)
    elif case_id == "indirect":
        bbox = COSArray(
            [COSInteger.get(0), COSInteger.get(0), COSInteger.get(10), COSInteger.get(20)]
        )
        stream.set_item(COSName.get_pdf_name("BBox"), _indirect(bbox, 60))
        stream.set_item(
            COSName.get_pdf_name("Resources"), _indirect(COSDictionary(), 61)
        )
    return stream


def _emit_stream(name: str, dictionary: COSStream) -> str:
    stream = PDAppearanceStream(dictionary)
    return (
        f"STREAM {name} type={dictionary.get_name(COSName.get_pdf_name('Type'))}"
        f" subtype={dictionary.get_name(COSName.get_pdf_name('Subtype'))}"
        f" form={stream.get_form_type()} struct={stream.get_struct_parents()}"
        f" bbox={'none' if stream.get_bbox() is None else 'rect'}"
        f" matrix={_matrix(stream)}"
        f" resources={'none' if stream.get_resources() is None else 'dict'}"
    )


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("AppearanceDictionaryFuzzProbe").splitlines()
    return {
        " ".join(line.split(maxsplit=2)[:2]): line
        for line in lines
    }


@requires_oracle
@pytest.mark.parametrize(
    "case_id", _DICTIONARY_IDS, ids=_SHORT_DICTIONARY_IDS
)
def test_appearance_dictionary_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit_dictionary(case_id, _dictionary_case(case_id)) == java_lines[
        f"CASE {case_id}"
    ]


@requires_oracle
@pytest.mark.parametrize("case_id", _STREAM_IDS, ids=("def", "bad", "ind"))
def test_appearance_stream_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit_stream(case_id, _stream_case(case_id)) == java_lines[
        f"STREAM {case_id}"
    ]


@pytest.mark.parametrize(
    ("entry", "method", "message"),
    (
        (
            PDAppearanceEntry(COSStream()),
            "get_sub_dictionary",
            "This entry is not an appearance subdictionary",
        ),
        (
            PDAppearanceEntry(COSDictionary()),
            "get_appearance_stream",
            "This entry is not an appearance stream",
        ),
    ),
    ids=("stream", "dict"),
)
def test_entry_wrong_accessor_message(
    entry: PDAppearanceEntry, method: str, message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        getattr(entry, method)()


def test_setters_store_raw_cos_objects_and_none_removes_keys() -> None:
    appearance = PDAppearanceDictionary(COSDictionary())
    normal = COSStream()
    rollover = COSStream()
    down = COSDictionary()

    appearance.set_normal_appearance(PDAppearanceEntry(normal))
    appearance.set_rollover_appearance(PDAppearanceStream(rollover))
    appearance.set_down_appearance(PDAppearanceEntry(down))

    dictionary = appearance.get_cos_object()
    assert dictionary.get_item(_N) is normal
    assert dictionary.get_item(_R) is rollover
    assert dictionary.get_item(_D) is down

    appearance.set_normal_appearance(None)
    appearance.set_rollover_appearance(None)
    appearance.set_down_appearance(None)
    assert not any(dictionary.contains_key(key) for key in _AP_KEYS)
