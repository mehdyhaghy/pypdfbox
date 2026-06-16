"""PDAbstractPattern.create dispatcher + subclass-surface parity with PDFBox 3.0.7.

Complements ``test_tiling_pattern_dictionary_fuzz_wave1521`` (which fuzzes a
*pre-typed* ``PDTilingPattern``'s accessors): this module fuzzes the dispatch
decision itself — ``PDAbstractPattern.create`` over malformed ``/PatternType``
(tiling/shading/missing/garbage/non-int/indirect) — then projects the resulting
wrapper's class plus the key accessors per branch, including shading-pattern
``/Shading`` (dict vs stream vs garbage) and ``/ExtGState``.

Two principled divergences from raw upstream output are normalised/pinned:

- Java throws ``IOException`` for an unknown ``/PatternType``; the Python port
  raises ``OSError`` (the CLAUDE.md test-porting mapping for ``IOException``).
  Both surface as an error for the same cases, so the harness compares the
  error *cases*, not the exception class name.
- ``tiling-bbox-short``: upstream ``getBBox`` builds a zero-padded
  ``PDRectangle`` from a short array (``bbox=rect``); ``PDTilingPattern.get_b_box``
  gates on ``value.size() < 4`` and returns ``None`` (``bbox=none``). Same
  already-documented divergence pinned in wave 1521.
"""

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
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
    PDTilingPattern,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_PATTERN_TYPE = COSName.get_pdf_name("PatternType")
_PAINT_TYPE = COSName.get_pdf_name("PaintType")
_TILING_TYPE = COSName.get_pdf_name("TilingType")
_BBOX = COSName.get_pdf_name("BBox")
_X_STEP = COSName.get_pdf_name("XStep")
_Y_STEP = COSName.get_pdf_name("YStep")
_MATRIX = COSName.get_pdf_name("Matrix")
_RESOURCES = COSName.get_pdf_name("Resources")
_SHADING = COSName.get_pdf_name("Shading")
_EXT_G_STATE = COSName.get_pdf_name("ExtGState")
_SHADING_TYPE = COSName.get_pdf_name("ShadingType")
_COLOR_SPACE = COSName.get_pdf_name("ColorSpace")
_DEVICE_RGB = COSName.get_pdf_name("DeviceRGB")


def _indirect(value: COSBase | None) -> COSObject:
    return COSObject(1, resolved=value)


def _numbers(*values: float) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


def _bits(value: float) -> str:
    return struct.pack(">f", float(value)).hex()


def _matrix(pattern: PDAbstractPattern) -> str:
    try:
        return ",".join(_bits(value) for value in pattern.get_matrix())
    except Exception as exception:  # noqa: BLE001
        return f"ERR:{type(exception).__name__}"


def _shading_ext(pattern: PDShadingPattern) -> str:
    try:
        return (
            "none"
            if pattern.get_extended_graphics_state() is None
            else "present"
        )
    except Exception as exception:  # noqa: BLE001
        return f"ERR:{type(exception).__name__}"


def _tiling_projection(pattern: PDTilingPattern) -> str:
    try:
        bbox = "none" if pattern.get_b_box() is None else "rect"
    except Exception as exception:  # noqa: BLE001
        bbox = f"ERR:{type(exception).__name__}"
    try:
        resources = "none" if pattern.get_resources() is None else "present"
    except Exception as exception:  # noqa: BLE001
        resources = f"ERR:{type(exception).__name__}"
    return (
        f"paint={pattern.get_paint_type()}"
        f" ptype={pattern.get_pattern_type()}"
        f" tiling={pattern.get_tiling_type()}"
        f" bbox={bbox}"
        f" x={_bits(pattern.get_x_step())}"
        f" y={_bits(pattern.get_y_step())}"
        f" matrix={_matrix(pattern)}"
        f" resources={resources}"
    )


def _shading_projection(pattern: PDShadingPattern) -> str:
    try:
        value = pattern.get_shading()
        shading = "none" if value is None else f"type{value.get_shading_type()}"
    except Exception as exception:  # noqa: BLE001
        shading = f"ERR:{type(exception).__name__}"
    return (
        f"ptype={pattern.get_pattern_type()}"
        f" shading={shading}"
        f" matrix={_matrix(pattern)}"
        f" ext={_shading_ext(pattern)}"
    )


def _dispatch(dictionary: COSDictionary) -> str:
    try:
        pattern = PDAbstractPattern.create(dictionary, None)
        if pattern is None:
            return "null"
        if isinstance(pattern, PDTilingPattern):
            return "tiling " + _tiling_projection(pattern)
        if isinstance(pattern, PDShadingPattern):
            return "shading " + _shading_projection(pattern)
        return f"other:{type(pattern).__name__}"
    except Exception as exception:  # noqa: BLE001
        return f"ERR:{type(exception).__name__}"


def _with_type(pattern_type: COSBase | None) -> COSDictionary:
    dictionary = COSDictionary()
    if pattern_type is not None:
        dictionary.set_item(_PATTERN_TYPE, pattern_type)
    return dictionary


def _minimal_shading() -> COSDictionary:
    shading = COSDictionary()
    shading.set_item(_SHADING_TYPE, COSInteger.get(2))
    shading.set_item(_COLOR_SPACE, _DEVICE_RGB)
    return shading


def _shading_stream() -> COSStream:
    stream = COSStream()
    stream.set_item(_SHADING_TYPE, COSInteger.get(4))
    stream.set_item(_COLOR_SPACE, _DEVICE_RGB)
    return stream


def _build_cases() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    # ----- /PatternType dispatch -----
    cases["ptype-missing"] = _with_type(None)
    cases["ptype-1"] = _with_type(COSInteger.get(1))
    cases["ptype-2"] = _with_type(COSInteger.get(2))
    cases["ptype-0"] = _with_type(COSInteger.ZERO)
    cases["ptype-3"] = _with_type(COSInteger.get(3))
    cases["ptype-neg"] = _with_type(COSInteger.get(-1))
    cases["ptype-wide"] = _with_type(COSInteger.get(4294967297))
    cases["ptype-float1"] = _with_type(COSFloat(1.0))
    cases["ptype-float1p9"] = _with_type(COSFloat(1.9))
    cases["ptype-float2"] = _with_type(COSFloat(2.4))
    cases["ptype-name"] = _with_type(COSName.get_pdf_name("Bad"))
    cases["ptype-null"] = _with_type(COSNull.NULL)
    cases["ptype-i1"] = _with_type(_indirect(COSInteger.get(1)))
    cases["ptype-i2"] = _with_type(_indirect(COSInteger.get(2)))
    cases["ptype-inull"] = _with_type(_indirect(None))

    # ----- tiling (type 1) body fuzz via dispatch -----
    cases["tiling-bare"] = _with_type(COSInteger.get(1))

    t = _with_type(COSInteger.get(1))
    t.set_item(_PAINT_TYPE, COSFloat(2.5))
    cases["tiling-paint-float"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_TILING_TYPE, COSName.get_pdf_name("Bad"))
    cases["tiling-tiling-name"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_BBOX, _numbers(4, 3, 2, 1))
    t.set_item(_X_STEP, COSFloat(10.0))
    t.set_item(_Y_STEP, COSFloat(-20.0))
    cases["tiling-bbox-full"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_BBOX, _numbers(1, 2))
    cases["tiling-bbox-short"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_X_STEP, COSInteger.ZERO)
    t.set_item(_Y_STEP, COSInteger.get(-5))
    cases["tiling-step-zeroneg"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_MATRIX, _numbers(1, 2, 3, 4, 5))
    cases["tiling-matrix-short"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_RESOURCES, COSName.get_pdf_name("Bad"))
    cases["tiling-res-name"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_RESOURCES, COSDictionary())
    cases["tiling-res-dict"] = t

    t = _with_type(COSInteger.get(1))
    t.set_item(_EXT_G_STATE, COSDictionary())
    cases["tiling-ext-dict"] = t

    # ----- shading (type 2) body fuzz via dispatch -----
    cases["shading-bare"] = _with_type(COSInteger.get(2))

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, _minimal_shading())
    cases["shading-dict"] = s

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, _shading_stream())
    cases["shading-stream"] = s

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, COSName.get_pdf_name("Bad"))
    cases["shading-name"] = s

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, COSNull.NULL)
    cases["shading-null"] = s

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, _indirect(_minimal_shading()))
    cases["shading-idict"] = s

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, _minimal_shading())
    s.set_item(_MATRIX, _numbers(2, 0, 0, 2, 5, 5))
    s.set_item(_EXT_G_STATE, COSDictionary())
    cases["shading-full"] = s

    s = _with_type(COSInteger.get(2))
    s.set_item(_SHADING, _minimal_shading())
    s.set_item(_EXT_G_STATE, COSName.get_pdf_name("Bad"))
    cases["shading-ext-name"] = s

    return cases


_CASES = _build_cases()
_CASE_IDS = tuple(_CASES)
_SHORT_IDS = tuple(f"c{index:02d}" for index in range(len(_CASE_IDS)))

# Cases where Java throws IOException and the Python port raises OSError. Both
# are "error" outcomes; the dispatcher behaviour (unknown /PatternType) is
# identical — only the exception class name differs per the documented
# IOException -> OSError porting mapping.
_ERROR_CASES = frozenset(
    {
        "ptype-missing",
        "ptype-0",
        "ptype-3",
        "ptype-neg",
        "ptype-name",
        "ptype-null",
        "ptype-inull",
    }
)

# tiling-bbox-short: upstream getBBox zero-pads a short array (bbox=rect);
# pypdfbox get_b_box gates on size()<4 and returns None (bbox=none). Same
# divergence pinned in wave 1521's tiling-dictionary fuzz.
_PINNED_BBOX = {
    "tiling-bbox-short": ("bbox=none", "bbox=rect"),
}


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("PatternFuzzProbe").splitlines()
    return {line.split(maxsplit=2)[1]: line.split(maxsplit=2)[2] for line in lines}


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS, ids=_SHORT_IDS)
def test_create_dispatch_matches_pdfbox(
    case_id: str, java_lines: dict[str, str]
) -> None:
    python_body = _dispatch(_CASES[case_id])
    java_body = java_lines[case_id]

    if case_id in _ERROR_CASES:
        # IOException (Java) vs OSError (Python) — same dispatch outcome.
        assert python_body == "ERR:OSError"
        assert java_body == "ERR:IOException"
        return

    if case_id in _PINNED_BBOX:
        python_bbox, java_bbox = _PINNED_BBOX[case_id]
        assert python_bbox in python_body
        assert java_bbox in java_body
        assert python_body.replace(python_bbox, java_bbox) == java_body
        return

    assert python_body == java_body


def test_unknown_pattern_type_message() -> None:
    """The OSError message mirrors upstream's IOException text + the (wrapped)
    pattern-type int — independent of the live oracle."""
    dictionary = _with_type(COSInteger.get(3))
    with pytest.raises(OSError, match=r"Unknown pattern type 3"):
        PDAbstractPattern.create(dictionary, None)


def test_none_dictionary_returns_none() -> None:
    assert PDAbstractPattern.create(None, None) is None
