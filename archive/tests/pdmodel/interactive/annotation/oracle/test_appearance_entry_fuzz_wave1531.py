"""Per-state appearance-entry / appearance-stream parity with PDFBox 3.0.7.

Differential oracle for the ``/AP`` *entry value* resolution and the
``PDAppearanceStream`` form-XObject accessors against the live PDFBox 3.0.7
jar. Complements ``test_appearance_dictionary_fuzz_wave1520`` (which fuzzed the
``/AP`` dictionary level) by drilling into:

- ``PDAppearanceEntry`` dispatch: ``is_stream`` / ``is_sub_dictionary`` for a
  single appearance ``COSStream`` vs a state sub-dictionary, and the
  ``IllegalStateException``-mirroring ``ValueError`` raised by the *wrong*
  accessor (``get_appearance_stream`` on a sub-dict, ``get_sub_dictionary`` on a
  stream).
- ``get_sub_dictionary`` value filtering: only ``COSStream`` state values
  (direct or indirect-resolved) make it into the returned map; scalars / nulls /
  plain dicts / strings / indirect-null are skipped (upstream
  ``COSDictionary.getCOSStream`` semantics, PDFBOX-1599).
- ``PDAppearanceStream`` numeric accessors on malformed entries: partial /
  over-long / non-numeric / wrong-typed / empty ``/BBox`` (with the
  ``PDRectangle`` coordinate normalisation that reorders a 3-element box),
  wrong-length / non-numeric / wrong-typed ``/Matrix`` (identity fallback),
  ``/Resources`` that is a name / null (PDFBOX-4372 empty ``PDResources``), and
  indirect ``/BBox`` // ``/Matrix`` // ``/Resources`` resolution.

Every case matched upstream exactly when this wave was written — this is a
parity-lock test (no production divergence), so a future refactor that breaks
any of these resolutions is caught against the live oracle.
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
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_BBOX = COSName.get_pdf_name("BBox")
_MATRIX = COSName.get_pdf_name("Matrix")
_RESOURCES = COSName.get_pdf_name("Resources")
_FORMTYPE = COSName.get_pdf_name("FormType")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_BAD = COSName.get_pdf_name("Bad")


def _indirect(value: COSBase, number: int) -> COSObject:
    return COSObject(number, resolved=value)


def _message(exception: Exception) -> str:
    return (str(exception) or type(exception).__name__).replace(" ", "_")


def _num(value: float) -> str:
    value = float(value)
    return str(int(value)) if value == int(value) else str(value)


def _nums(*values: float) -> COSArray:
    return COSArray([COSFloat(float(v)) for v in values])


# ---------------------------------------------------------------------------
# PDAppearanceEntry value resolution
# ---------------------------------------------------------------------------

_ENTRY_IDS = (
    "stream",
    "empty_dict",
    "two_states",
    "mixed",
    "only_null",
    "odd_names",
)


def _entry_case(case_id: str) -> PDAppearanceEntry:
    if case_id == "stream":
        return PDAppearanceEntry(COSStream())
    if case_id == "empty_dict":
        return PDAppearanceEntry(COSDictionary())
    if case_id == "two_states":
        states = COSDictionary()
        states.set_item(COSName.get_pdf_name("On"), COSStream())
        states.set_item(COSName.get_pdf_name("Off"), COSStream())
        return PDAppearanceEntry(states)
    if case_id == "mixed":
        mixed = COSDictionary()
        mixed.set_item(COSName.get_pdf_name("Direct"), COSStream())
        mixed.set_item(COSName.get_pdf_name("Indirect"), _indirect(COSStream(), 1))
        mixed.set_item(COSName.get_pdf_name("Scalar"), COSInteger.get(7))
        mixed.set_item(COSName.get_pdf_name("Null"), COSNull.NULL)
        mixed.set_item(COSName.get_pdf_name("Dict"), COSDictionary())
        mixed.set_item(COSName.get_pdf_name("Str"), COSString("x"))
        mixed.set_item(COSName.get_pdf_name("IndNull"), _indirect(COSNull.NULL, 2))
        return PDAppearanceEntry(mixed)
    if case_id == "only_null":
        only_null = COSDictionary()
        only_null.set_item(COSName.get_pdf_name("D"), COSNull.NULL)
        return PDAppearanceEntry(only_null)
    if case_id == "odd_names":
        odd = COSDictionary()
        odd.set_item(COSName.get_pdf_name("A B"), COSStream())
        odd.set_item(COSName.get_pdf_name("A/B"), COSStream())
        return PDAppearanceEntry(odd)
    raise AssertionError(case_id)


def _emit_entry(case_id: str, entry: PDAppearanceEntry) -> str:
    parts = [f"ENTRY {case_id}"]
    parts.append(" isStream=" + ("true" if entry.is_stream() else "false"))
    parts.append(" isSub=" + ("true" if entry.is_sub_dictionary() else "false"))
    parts.append(" as=")
    try:
        stream = entry.get_appearance_stream()
        parts.append("none" if stream is None else "stream")
    except Exception as exception:  # noqa: BLE001
        parts.append("ERR:" + _message(exception))
    parts.append(" sub=")
    try:
        states = entry.get_sub_dictionary()
        names = sorted(states.keys())
        parts.append(",".join(names) if names else "empty")
    except Exception as exception:  # noqa: BLE001
        parts.append("ERR:" + _message(exception))
    return "".join(parts)


# ---------------------------------------------------------------------------
# PDAppearanceStream form-XObject accessors
# ---------------------------------------------------------------------------

_STREAM_IDS = (
    "default",
    "good",
    "bbox3",
    "bbox6",
    "bbox_nan",
    "bbox_name",
    "bbox_empty",
    "mtx5",
    "mtx7",
    "mtx_nan",
    "mtx_name",
    "res_name",
    "res_null",
    "indirect",
    "badints",
)


def _stream_case(case_id: str) -> COSStream:
    stream = COSStream()
    if case_id == "good":
        stream.set_item(_BBOX, _nums(0, 0, 100, 200))
        stream.set_item(_MATRIX, _nums(2, 0, 0, 3, 5, 7))
        stream.set_item(_RESOURCES, COSDictionary())
        stream.set_item(_FORMTYPE, COSInteger.get(1))
        stream.set_item(_STRUCT_PARENTS, COSInteger.get(4))
    elif case_id == "bbox3":
        stream.set_item(_BBOX, _nums(1, 2, 3))
    elif case_id == "bbox6":
        stream.set_item(_BBOX, _nums(1, 2, 3, 4, 5, 6))
    elif case_id == "bbox_nan":
        stream.set_item(
            _BBOX,
            COSArray([COSInteger.get(1), _BAD, COSInteger.get(3), COSInteger.get(4)]),
        )
    elif case_id == "bbox_name":
        stream.set_item(_BBOX, _BAD)
    elif case_id == "bbox_empty":
        stream.set_item(_BBOX, COSArray())
    elif case_id == "mtx5":
        stream.set_item(_MATRIX, _nums(2, 0, 0, 3, 5))
    elif case_id == "mtx7":
        stream.set_item(_MATRIX, _nums(2, 0, 0, 3, 5, 7, 9))
    elif case_id == "mtx_nan":
        stream.set_item(
            _MATRIX,
            COSArray(
                [
                    COSInteger.get(2),
                    COSInteger.get(0),
                    _BAD,
                    COSInteger.get(3),
                    COSInteger.get(5),
                    COSInteger.get(7),
                ]
            ),
        )
    elif case_id == "mtx_name":
        stream.set_item(_MATRIX, _BAD)
    elif case_id == "res_name":
        stream.set_item(_RESOURCES, _BAD)
    elif case_id == "res_null":
        stream.set_item(_RESOURCES, COSNull.NULL)
    elif case_id == "indirect":
        stream.set_item(_BBOX, _indirect(_nums(0, 0, 10, 20), 10))
        stream.set_item(_MATRIX, _indirect(_nums(1, 0, 0, 1, 3, 4), 11))
        stream.set_item(_RESOURCES, _indirect(COSDictionary(), 12))
    elif case_id == "badints":
        stream.set_item(_FORMTYPE, _BAD)
        stream.set_item(_STRUCT_PARENTS, COSFloat(4.75))
    return stream


def _bbox(stream: PDAppearanceStream) -> str:
    rect = stream.get_bbox()
    if rect is None:
        return "none"
    return ",".join(
        _num(value)
        for value in (
            rect.get_lower_left_x(),
            rect.get_lower_left_y(),
            rect.get_upper_right_x(),
            rect.get_upper_right_y(),
        )
    )


def _matrix(stream: PDAppearanceStream) -> str:
    return ",".join(_num(value) for value in stream.get_matrix())


def _emit_stream(case_id: str, cos: COSStream) -> str:
    stream = PDAppearanceStream(cos)
    return (
        f"STREAM {case_id} form={stream.get_form_type()}"
        f" struct={stream.get_struct_parents()}"
        f" bbox={_bbox(stream)} matrix={_matrix(stream)}"
        f" resources={'none' if stream.get_resources() is None else 'dict'}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("AppearanceEntryFuzzProbe").splitlines()
    return {" ".join(line.split(maxsplit=2)[:2]): line for line in lines}


@requires_oracle
@pytest.mark.parametrize("case_id", _ENTRY_IDS, ids=_ENTRY_IDS)
def test_appearance_entry_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit_entry(case_id, _entry_case(case_id)) == java_lines[
        f"ENTRY {case_id}"
    ]


@requires_oracle
@pytest.mark.parametrize("case_id", _STREAM_IDS, ids=_STREAM_IDS)
def test_appearance_stream_accessor_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit_stream(case_id, _stream_case(case_id)) == java_lines[
        f"STREAM {case_id}"
    ]


def test_wrong_accessor_raises_value_error() -> None:
    """Mirror upstream ``IllegalStateException`` via ``ValueError``."""
    with pytest.raises(ValueError, match="not an appearance subdictionary"):
        PDAppearanceEntry(COSStream()).get_sub_dictionary()
    with pytest.raises(ValueError, match="not an appearance stream"):
        PDAppearanceEntry(COSDictionary()).get_appearance_stream()


def test_sub_dictionary_skips_non_stream_state_values() -> None:
    """Only ``COSStream`` (direct or indirect) state values survive."""
    states = COSDictionary()
    states.set_item(COSName.get_pdf_name("Direct"), COSStream())
    states.set_item(COSName.get_pdf_name("Indirect"), _indirect(COSStream(), 1))
    states.set_item(COSName.get_pdf_name("Scalar"), COSInteger.get(7))
    states.set_item(COSName.get_pdf_name("Null"), COSNull.NULL)
    states.set_item(COSName.get_pdf_name("Dict"), COSDictionary())
    result = PDAppearanceEntry(states).get_sub_dictionary()
    assert sorted(result) == ["Direct", "Indirect"]
    assert all(isinstance(value, PDAppearanceStream) for value in result.values())
