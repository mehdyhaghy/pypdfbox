"""Live PDFBox differential fuzz for the whole ``PDDestination`` family
(``pypdfbox.pdmodel.interactive.documentnavigation.destination``).

Drives ``PDDestination.create`` over ~30 malformed / edge-case destination
inputs (empty array, missing/garbage page slot, every fit-mode keyword, short /
null / non-numeric coordinate operands, named-destination forms, deeply wrong
base types) and compares pypdfbox's observable surface against Apache PDFBox
3.0.7's, via the ``DestinationFuzzProbe`` Java oracle.

Each case is reduced to one canonical ``<case>=<value>`` line whose grammar
must match ``oracle/probes/DestinationFuzzProbe.java`` exactly so the two
languages compare byte-for-byte. The probe emits upstream's raw int/float
``-1`` "retain current value" sentinel verbatim; the pypdfbox projector below
maps its ``None`` to the same ``-1`` (int getters) / ``-1.0`` (XYZ float
getters) so the comparison is honest.

HONEST DIVERGENCE — out-of-bounds coordinate reads
--------------------------------------------------
When a destination array is physically shorter than a coordinate slot's index
(e.g. ``[page /XYZ]`` with no left/top/zoom, or ``[page /XYZ 10]`` missing
top+zoom), upstream's coordinate getters index past the array end and throw a
``java.lang.IndexOutOfBoundsException``. pypdfbox's ``_get_float`` guards
``index < array.size()`` and returns ``None`` instead — a deliberate,
pervasive "graceful None" design choice (see ``PDPageDestination._get_float``
and the fresh-construct tests that depend on it). The two affected cases
(``xyz_missing_coords``, ``xyz_short_one_coord``) are pinned BOTH sides with
this divergence called out, rather than papered over. The present-but-COSNull
case (a fresh-grown array) maps to ``-1`` on both sides and is NOT a
divergence.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------
# Case battery — mirrors DestinationFuzzProbe.main() one-for-one (same order,
# same keys). Each value is a zero-arg builder returning the COS base passed
# to PDDestination.create().
# --------------------------------------------------------------------------


def _array(*items: COSBase) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


_CASES: list[tuple[str, object]] = [
    # base-type dispatch
    ("null_base", None),
    ("name_base", _name("ChapterOne")),
    ("string_base", COSString("Chapter Two")),
    ("integer_base", COSInteger.get(9)),
    ("float_base", COSFloat(1.5)),
    # malformed arrays
    ("empty_array", _array()),
    ("one_element_int", _array(COSInteger.get(0))),
    ("one_element_name", _array(_name("Fit"))),
    ("type_slot_string", _array(COSInteger.get(0), COSString("Fit"))),
    ("type_slot_int", _array(COSInteger.get(0), COSInteger.get(5))),
    ("type_slot_null", _array(COSInteger.get(0), COSNull.NULL)),
    # every fit-mode keyword
    ("xyz", _array(COSInteger.get(3), _name("XYZ"),
                   COSInteger.get(10), COSInteger.get(20), COSFloat(1.5))),
    ("fit", _array(COSInteger.get(3), _name("Fit"))),
    ("fith", _array(COSInteger.get(3), _name("FitH"), COSInteger.get(700))),
    ("fitv", _array(COSInteger.get(3), _name("FitV"), COSInteger.get(72))),
    ("fitr", _array(COSInteger.get(3), _name("FitR"),
                    COSInteger.get(1), COSInteger.get(2),
                    COSInteger.get(3), COSInteger.get(4))),
    ("fitb", _array(COSInteger.get(3), _name("FitB"))),
    ("fitbh", _array(COSInteger.get(3), _name("FitBH"), COSInteger.get(700))),
    ("fitbv", _array(COSInteger.get(3), _name("FitBV"), COSInteger.get(72))),
    ("unknown_type", _array(COSInteger.get(0), _name("Bogus"))),
    # page-slot variants
    ("page_float", _array(COSFloat(3.9), _name("Fit"))),
    ("page_null", _array(COSNull.NULL, _name("Fit"))),
    ("page_name", _array(_name("NotAPage"), _name("Fit"))),
    ("page_string", _array(COSString("p"), _name("Fit"))),
    ("page_negative", _array(COSInteger.get(-5), _name("Fit"))),
    # coordinate operand fuzz
    ("xyz_missing_coords", _array(COSInteger.get(0), _name("XYZ"))),
    ("xyz_short_one_coord", _array(COSInteger.get(0), _name("XYZ"), COSInteger.get(10))),
    ("xyz_null_coords", _array(COSInteger.get(0), _name("XYZ"),
                               COSNull.NULL, COSNull.NULL, COSNull.NULL)),
    ("xyz_name_coord", _array(COSInteger.get(0), _name("XYZ"),
                              _name("Garbage"), COSInteger.get(20), COSFloat(1.5))),
    ("xyz_string_coord", _array(COSInteger.get(0), _name("XYZ"),
                                COSString("x"), COSInteger.get(20), COSFloat(1.5))),
    ("xyz_zoom_zero", _array(COSInteger.get(0), _name("XYZ"),
                             COSInteger.get(10), COSInteger.get(20), COSInteger.get(0))),
    ("xyz_extra_operands", _array(COSInteger.get(0), _name("XYZ"),
                                  COSInteger.get(10), COSInteger.get(20), COSFloat(1.5),
                                  COSInteger.get(99), COSInteger.get(100))),
    ("fith_missing_coord", _array(COSInteger.get(0), _name("FitH"))),
    ("fith_null_coord", _array(COSInteger.get(0), _name("FitH"), COSNull.NULL)),
    ("fitr_short", _array(COSInteger.get(0), _name("FitR"),
                          COSInteger.get(1), COSInteger.get(2))),
    ("fitr_null_edges", _array(COSInteger.get(0), _name("FitR"),
                               COSNull.NULL, COSNull.NULL, COSNull.NULL, COSNull.NULL)),
]

# Cases whose ONLY divergence from the live oracle is the out-of-bounds
# coordinate read (Java throws IndexOutOfBoundsException; pypdfbox returns
# None). See the module docstring. These are dropped from the byte-for-byte
# oracle comparison and pinned separately in test_out_of_bounds_divergence.
_DIVERGENT_CASES = {"xyz_missing_coords", "xyz_short_one_coord"}


# --------------------------------------------------------------------------
# pypdfbox projector — must reproduce DestinationFuzzProbe's line grammar.
# --------------------------------------------------------------------------


def _int_getter(value: float | None) -> str:
    """Render an int-style coordinate getter the way Java prints it.

    Upstream FitH/FitV/FitR getters return ``int``; the "retain" sentinel is
    ``-1``. pypdfbox returns ``float | None`` — map None to -1 and drop the
    fractional part of integral floats so e.g. ``700.0`` prints as ``700``.
    """
    if value is None:
        return "-1"
    return str(int(value))


def _float_getter(value: float | None) -> str:
    """Render an XYZ float coordinate getter the way Java prints a ``float``.

    Upstream getLeft/getTop/getZoom on PDPageXYZDestination return ``float``;
    the sentinel is ``-1.0``. Java prints e.g. ``1.5`` / ``0.0`` / ``-1.0``;
    integral floats keep one decimal (``20.0``). Reproduce that exactly.
    """
    f = -1.0 if value is None else float(value)
    if f == int(f):
        return f"{int(f)}.0"
    return str(f)


def _coords(dest: PDPageDestination) -> str:
    if isinstance(dest, PDPageXYZDestination):
        # Upstream XYZ getLeft()/getTop() return int (sentinel -1); getZoom()
        # returns float (sentinel -1.0). Match that int/float split exactly.
        return (
            f"left={_int_getter(dest.get_left())},"
            f"top={_int_getter(dest.get_top())},"
            f"zoom={_float_getter(dest.get_zoom())}"
        )
    if isinstance(dest, PDPageFitRectangleDestination):
        return (
            f"left={_int_getter(dest.get_left())},"
            f"bottom={_int_getter(dest.get_bottom())},"
            f"right={_int_getter(dest.get_right())},"
            f"top={_int_getter(dest.get_top())}"
        )
    if isinstance(dest, PDPageFitWidthDestination):
        return f"top={_int_getter(dest.get_top())}"
    if isinstance(dest, PDPageFitHeightDestination):
        return f"left={_int_getter(dest.get_left())}"
    return "none"


def _project(case: str, base: object) -> str:
    """Reproduce DestinationFuzzProbe.run() for one case in pypdfbox terms."""
    try:
        dest = PDDestination.create(base)
    except OSError:
        # Upstream's malformed-array / wrong-base fall-through is an
        # IOException; pypdfbox raises OSError (its IOException analogue).
        return f"{case}=ERR:IOException"
    if dest is None:
        return f"{case}=null"
    if isinstance(dest, PDNamedDestination):
        return f"{case}=class:PDNamedDestination;value:{dest.get_named_destination()}"
    page = dest
    type_name = page.get_cos_object().get_name(1)
    retrieve = page.retrieve_page_number()
    return (
        f"{case}=class:{type(dest).__name__}"
        f";page:{page.get_page_number()}"
        f";retrieve:{retrieve}"
        f";type:{type_name}"
        f";{_coords(page)}"
    )


def _python_lines() -> dict[str, str]:
    return {case: _project(case, builder) for case, builder in _CASES}


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


@requires_oracle
def test_destination_fuzz_matches_pdfbox() -> None:
    """pypdfbox's projected destination surface equals Apache PDFBox's for
    every non-divergent fuzz case, byte-for-byte."""
    raw = run_probe_text("DestinationFuzzProbe")
    java = {
        line.split("=", 1)[0]: line
        for line in raw.splitlines()
        if line and "=" in line
    }
    py = _python_lines()

    # The probe must emit exactly the cases we model (same keys, same count).
    assert set(java) == set(py), (
        f"case-set mismatch: java-only={set(java) - set(py)}, "
        f"py-only={set(py) - set(java)}"
    )

    for case in py:
        if case in _DIVERGENT_CASES:
            continue
        assert py[case] == java[case], f"divergence in {case}"


@requires_oracle
def test_out_of_bounds_divergence_is_pinned() -> None:
    """The two out-of-bounds XYZ cases are the ONLY ones where pypdfbox and
    upstream differ: Java throws IndexOutOfBoundsException reading a coordinate
    past the array end; pypdfbox returns None (-> -1.0 sentinel). Pin both
    sides so a future change on either is caught."""
    raw = run_probe_text("DestinationFuzzProbe")
    java = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in raw.splitlines()
        if line and "=" in line
    }
    # Upstream: a too-short XYZ array throws when its coordinate getter indexes
    # past the array end.
    assert java["xyz_missing_coords"] == "ERR:IndexOutOfBoundsException"
    assert java["xyz_short_one_coord"] == "ERR:IndexOutOfBoundsException"

    # pypdfbox: graceful None for every missing slot, -> -1.0 float sentinel.
    py = _python_lines()
    assert py["xyz_missing_coords"] == (
        "xyz_missing_coords=class:PDPageXYZDestination;page:0;retrieve:0;"
        "type:XYZ;left=-1,top=-1,zoom=-1.0"
    )
    assert py["xyz_short_one_coord"] == (
        "xyz_short_one_coord=class:PDPageXYZDestination;page:0;retrieve:0;"
        "type:XYZ;left=10,top=-1,zoom=-1.0"
    )


# --------------------------------------------------------------------------
# Value-pinned mirror (runs even without the live oracle). Expected values are
# the verbatim DestinationFuzzProbe output captured against PDFBox 3.0.7, so
# the suite still guards the surface on a machine with no jar / no JDK.
# --------------------------------------------------------------------------

_EXPECTED_PDFBOX_3_0_7: dict[str, str] = {
    "null_base": "null_base=null",
    "name_base": "name_base=class:PDNamedDestination;value:ChapterOne",
    "string_base": "string_base=class:PDNamedDestination;value:Chapter Two",
    "integer_base": "integer_base=ERR:IOException",
    "float_base": "float_base=ERR:IOException",
    "empty_array": "empty_array=ERR:IOException",
    "one_element_int": "one_element_int=ERR:IOException",
    "one_element_name": "one_element_name=ERR:IOException",
    "type_slot_string": "type_slot_string=ERR:IOException",
    "type_slot_int": "type_slot_int=ERR:IOException",
    "type_slot_null": "type_slot_null=ERR:IOException",
    "xyz": "xyz=class:PDPageXYZDestination;page:3;retrieve:3;type:XYZ;"
           "left=10,top=20,zoom=1.5",
    "fit": "fit=class:PDPageFitDestination;page:3;retrieve:3;type:Fit;none",
    "fith": "fith=class:PDPageFitWidthDestination;page:3;retrieve:3;type:FitH;top=700",
    "fitv": "fitv=class:PDPageFitHeightDestination;page:3;retrieve:3;type:FitV;left=72",
    "fitr": "fitr=class:PDPageFitRectangleDestination;page:3;retrieve:3;type:FitR;"
            "left=1,bottom=2,right=3,top=4",
    "fitb": "fitb=class:PDPageFitDestination;page:3;retrieve:3;type:FitB;none",
    "fitbh": "fitbh=class:PDPageFitWidthDestination;page:3;retrieve:3;type:FitBH;top=700",
    "fitbv": "fitbv=class:PDPageFitHeightDestination;page:3;retrieve:3;type:FitBV;left=72",
    "unknown_type": "unknown_type=ERR:IOException",
    "page_float": "page_float=class:PDPageFitDestination;page:3;retrieve:3;type:Fit;none",
    "page_null": "page_null=class:PDPageFitDestination;page:-1;retrieve:-1;type:Fit;none",
    "page_name": "page_name=class:PDPageFitDestination;page:-1;retrieve:-1;type:Fit;none",
    "page_string": "page_string=class:PDPageFitDestination;page:-1;retrieve:-1;type:Fit;none",
    "page_negative": "page_negative=class:PDPageFitDestination;page:-5;retrieve:-5;"
                     "type:Fit;none",
    # The two divergent cases: pypdfbox does NOT throw. Expected value is the
    # pypdfbox surface (graceful -1.0), NOT upstream's IndexOutOfBoundsException.
    "xyz_missing_coords": "xyz_missing_coords=class:PDPageXYZDestination;page:0;"
                          "retrieve:0;type:XYZ;left=-1,top=-1,zoom=-1.0",
    "xyz_short_one_coord": "xyz_short_one_coord=class:PDPageXYZDestination;page:0;"
                           "retrieve:0;type:XYZ;left=10,top=-1,zoom=-1.0",
    "xyz_null_coords": "xyz_null_coords=class:PDPageXYZDestination;page:0;retrieve:0;"
                       "type:XYZ;left=-1,top=-1,zoom=-1.0",
    "xyz_name_coord": "xyz_name_coord=class:PDPageXYZDestination;page:0;retrieve:0;"
                      "type:XYZ;left=-1,top=20,zoom=1.5",
    "xyz_string_coord": "xyz_string_coord=class:PDPageXYZDestination;page:0;retrieve:0;"
                        "type:XYZ;left=-1,top=20,zoom=1.5",
    "xyz_zoom_zero": "xyz_zoom_zero=class:PDPageXYZDestination;page:0;retrieve:0;"
                     "type:XYZ;left=10,top=20,zoom=0.0",
    "xyz_extra_operands": "xyz_extra_operands=class:PDPageXYZDestination;page:0;"
                          "retrieve:0;type:XYZ;left=10,top=20,zoom=1.5",
    "fith_missing_coord": "fith_missing_coord=class:PDPageFitWidthDestination;page:0;"
                          "retrieve:0;type:FitH;top=-1",
    "fith_null_coord": "fith_null_coord=class:PDPageFitWidthDestination;page:0;"
                       "retrieve:0;type:FitH;top=-1",
    "fitr_short": "fitr_short=class:PDPageFitRectangleDestination;page:0;retrieve:0;"
                  "type:FitR;left=1,bottom=2,right=-1,top=-1",
    "fitr_null_edges": "fitr_null_edges=class:PDPageFitRectangleDestination;page:0;"
                       "retrieve:0;type:FitR;left=-1,bottom=-1,right=-1,top=-1",
}


@pytest.mark.parametrize("case", [c[0] for c in _CASES])
def test_value_pinned_surface(case: str) -> None:
    """pypdfbox's projected surface matches the PDFBox-3.0.7-captured baseline,
    independent of the live oracle. Divergent cases pin the pypdfbox (None ->
    -1.0) surface; see the module docstring."""
    py = _python_lines()
    assert py[case] == _EXPECTED_PDFBOX_3_0_7[case]
