"""Live PDFBox differential parity for the ``PDCalRGB`` / ``PDCalGray``
component-count + initial-color + single-value ``toRGB`` surface
(PDF 32000-1 §8.6.5.2/§8.6.5.3).

The Java side is ``oracle/probes/CalComponentsProbe.java``. It builds the same
in-memory CalRGB / CalGray spaces as ``CalColorProbe`` but additionally emits
the deterministic, exact parts of the surface:

* ``COMP <name> <n>`` — ``getNumberOfComponents()`` (CalRGB = 3, CalGray = 1);
* ``INIT <name> c0 [c1 c2]`` — ``getInitialColor().getComponents()`` (black);
* ``RGB <name> comp... -> r g b`` — single-value ``toRGB`` for a battery of
  inputs (RGB as 0-255 ints, ``round(component*255)`` clamped to ``[0, 255]``).

This complements ``test_cal_color_oracle.py`` (which only covers the ``toRGB``
conversion battery) by pinning the exact ``getNumberOfComponents`` /
``getInitialColor`` surface against the live oracle.

Three parity tiers:

* **Exact tier** — ``getNumberOfComponents`` and ``getInitialColor`` must match
  PDFBox byte-for-byte (no float math, no CMM).
* **Pass-through tier** — the non-unit (D65) white point makes both sides skip
  CIE calibration and return the input components verbatim, so the only step is
  ``round(component*255)``; agreement is exact bar a documented <=1/255
  float-vs-double x.5-boundary rounding artifact.
* **Documented-divergence tier** — the unit-white-point calibrated path: the
  gamma decode and ``/Matrix`` application are deterministic and identical on
  both sides, but the FINAL XYZ->sRGB step diverges (PDFBox routes XYZ through
  the JVM AWT CMM / D50 PCS; pypdfbox uses the explicit IEC 61966-2-1 D65
  matrix). pypdfbox's own output is pinned as a regression guard and at least
  one tuple is asserted to differ from PDFBox so the divergence rationale stays
  honest. (Same project choice as ``LabCustom`` / DeviceCMYK in
  ``test_color_to_rgb_oracle.py``.)
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match CalComponentsProbe.clamp255) ----------


def _clamp255(value: float) -> int:
    """round(value * 255), clamped to [0, 255] — mirrors the Java probe."""
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: object, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)  # type: ignore[attr-defined]
    assert rgb is not None, f"{cs!r}.to_rgb({comps}) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _floats(vals: list[float]) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(v))
    return a


def _cal_rgb(
    white_point: list[float], gamma: list[float], matrix: list[float]
) -> PDCalRGB:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalRGB"))
    d = COSDictionary()
    d.set_item("WhitePoint", _floats(white_point))
    d.set_item("Gamma", _floats(gamma))
    d.set_item("Matrix", _floats(matrix))
    arr.add(d)
    return PDCalRGB(arr)


def _cal_gray(white_point: list[float], gamma: float) -> PDCalGray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    d = COSDictionary()
    d.set_item("WhitePoint", _floats(white_point))
    d.set_item("Gamma", COSFloat(gamma))
    arr.add(d)
    return PDCalGray(arr)


_UNIT = [1.0, 1.0, 1.0]
_D65 = [0.9505, 1.0, 1.089]
_GAMMA_RGB = [1.8, 2.2, 2.4]
# sRGB-ish primaries matrix, column-major [Xa Ya Za  Xb Yb Zb  Xc Yc Zc].
_MATRIX = [
    0.4124, 0.2126, 0.0193,
    0.3576, 0.7152, 0.1192,
    0.1805, 0.0722, 0.9505,
]
_IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]

_RGB_INPUTS = [
    [0.0, 0.0, 0.0],
    [1.0, 1.0, 1.0],
    [0.5, 0.5, 0.5],
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
    [0.2, 0.4, 0.8],
]
_GRAY_INPUTS = [[0.0], [0.2], [0.5], [0.8], [1.0]]


def _battery() -> dict[str, tuple[object, list[list[float]]]]:
    """Probe-emitted name -> (space, inputs). Inputs MUST match
    CalComponentsProbe.java exactly, in the same order."""
    return {
        "CalRgbUnit": (_cal_rgb(_UNIT, _GAMMA_RGB, _MATRIX), _RGB_INPUTS),
        "CalRgbIdent": (_cal_rgb(_UNIT, [2.2, 2.2, 2.2], _IDENTITY), _RGB_INPUTS),
        "CalRgbD65": (_cal_rgb(_D65, _GAMMA_RGB, _MATRIX), _RGB_INPUTS),
        "CalGrayUnit22": (_cal_gray(_UNIT, 2.2), _GRAY_INPUTS),
        "CalGrayUnit10": (_cal_gray(_UNIT, 1.0), _GRAY_INPUTS),
        "CalGrayD65": (_cal_gray(_D65, 2.2), _GRAY_INPUTS),
    }


# Exact tier: getNumberOfComponents / getInitialColor. The space the probe
# emits COMP/INIT for under each short name (any white point: arity + initial
# colour do not depend on calibration).
_EXPECTED_COMP = {"CalRgb": 3, "CalGray": 1}
_EXPECTED_INIT = {"CalRgb": [0.0, 0.0, 0.0], "CalGray": [0.0]}
_EXACT_SPACE_KEY = {"CalRgb": "CalRgbUnit", "CalGray": "CalGrayUnit22"}

# Pass-through tier: non-unit white point -> components returned verbatim.
_PASSTHROUGH = {"CalRgbD65", "CalGrayD65"}
# Float-vs-double rounding only bites on an exact x.5 boundary; <=1/255.
_PASSTHROUGH_MAX_DELTA = 1

# Documented-divergence tier: unit white point -> calibrated CIE pipeline whose
# XYZ->sRGB step routes through the AWT CMM (D50 PCS) in PDFBox vs the explicit
# IEC 61966-2-1 D65 matrix in pypdfbox.
_DIVERGENT = {"CalRgbUnit", "CalRgbIdent", "CalGrayUnit22", "CalGrayUnit10"}

# pypdfbox's own deterministic output for the calibrated spaces. Pinned so a
# regression in the gamma decode / matrix application / XYZ->sRGB matrix is
# caught; at least one tuple is asserted to actually differ from PDFBox so the
# documented CMM divergence stays honest.
_PYPDFBOX_DIVERGENT_EXPECTED: dict[str, list[tuple[int, int, int]]] = {
    "CalRgbUnit": [
        (0, 0, 0),
        (255, 255, 255),
        (146, 128, 120),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (66, 102, 201),
    ],
    "CalRgbIdent": [
        (0, 0, 0),
        (255, 249, 244),
        (140, 125, 123),
        (255, 0, 67),
        (0, 255, 0),
        (0, 57, 255),
        (0, 136, 207),
    ],
    "CalGrayUnit22": [
        (0, 0, 0),
        (52, 46, 45),
        (140, 125, 123),
        (223, 200, 197),
        (255, 249, 244),
    ],
    "CalGrayUnit10": [
        (0, 0, 0),
        (135, 121, 118),
        (204, 183, 180),
        (251, 226, 222),
        (255, 249, 244),
    ],
}


def _parse_probe(
    text: str,
) -> tuple[
    dict[str, int],
    dict[str, list[float]],
    dict[str, list[tuple[int, int, int]]],
]:
    """Parse the probe output into (COMP, INIT, RGB) maps."""
    comp: dict[str, int] = {}
    init: dict[str, list[float]] = {}
    rgb: dict[str, list[tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("COMP "):
            _, name, n = line.split()
            comp[name] = int(n)
        elif line.startswith("INIT "):
            parts = line.split()
            init[parts[1]] = [float(x) for x in parts[2:]]
        elif line.startswith("RGB ") and "->" in line:
            left, right = line[4:].split("->")
            name = left.split()[0]
            r, g, b = (int(x) for x in right.split())
            rgb.setdefault(name, []).append((r, g, b))
    return comp, init, rgb


@pytest.fixture(scope="module")
def _probe() -> tuple[
    dict[str, int],
    dict[str, list[float]],
    dict[str, list[tuple[int, int, int]]],
]:
    return _parse_probe(run_probe_text("CalComponentsProbe"))


# ---------- exact tier: component count ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_EXPECTED_COMP))
def test_cal_number_of_components(
    name: str,
    _probe: tuple[dict[str, int], dict[str, list[float]], object],
) -> None:
    """``getNumberOfComponents`` must match PDFBox exactly (CalRGB 3, CalGray 1)."""
    comp, _init, _rgb = _probe
    assert comp[name] == _EXPECTED_COMP[name]
    # And pypdfbox agrees with both.
    cs = _battery()[_EXACT_SPACE_KEY[name]][0]
    assert cs.get_number_of_components() == comp[name]  # type: ignore[attr-defined]


# ---------- exact tier: initial color ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_EXPECTED_INIT))
def test_cal_initial_color(
    name: str,
    _probe: tuple[dict[str, int], dict[str, list[float]], object],
) -> None:
    """``getInitialColor().getComponents()`` must be the black tristimulus and
    match PDFBox exactly."""
    _comp, init, _rgb = _probe
    assert init[name] == _EXPECTED_INIT[name]
    cs = _battery()[_EXACT_SPACE_KEY[name]][0]
    py = cs.get_initial_color().get_components()  # type: ignore[attr-defined]
    assert py == _EXPECTED_INIT[name]


# ---------- pass-through tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_PASSTHROUGH))
def test_cal_to_rgb_passthrough(
    name: str,
    _probe: tuple[object, object, dict[str, list[tuple[int, int, int]]]],
) -> None:
    """Non-unit white point: both sides skip CIE calibration and return the
    input components verbatim. The only step is ``round(component*255)``, so a
    mismatch beyond the documented <=1/255 float-vs-double x.5-boundary rounding
    artifact is a real bug (missing/incorrect pass-through shortcut)."""
    _comp, _init, rgb = _probe
    cs, inputs = _battery()[name]
    java = rgb[name]
    assert len(java) == len(inputs), f"{name}: probe emitted {len(java)} rows"
    for comps, j_rgb in zip(inputs, java, strict=True):
        py_rgb = _rgb_int(cs, list(comps))
        for chan, (p, j) in enumerate(zip(py_rgb, j_rgb, strict=True)):
            assert abs(p - j) <= _PASSTHROUGH_MAX_DELTA, (
                f"{name} {comps} channel {chan}: pypdfbox {p} vs PDFBox {j} "
                f"exceeds the {_PASSTHROUGH_MAX_DELTA}/255 float-vs-double "
                f"rounding tolerance"
            )


# ---------- documented-divergence tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_DIVERGENT))
def test_cal_to_rgb_documented_divergence(
    name: str,
    _probe: tuple[object, object, dict[str, list[tuple[int, int, int]]]],
) -> None:
    """Unit white point -> calibrated CIE pipeline. The gamma decode and the
    ``/Matrix`` application are deterministic float arithmetic identical on both
    sides; only the FINAL XYZ->sRGB step diverges (pypdfbox: explicit IEC
    61966-2-1 D65 matrix; PDFBox: the JVM AWT CMM with a D50 PCS). We assert
    both that pypdfbox matches its pin (regression guard for the gamma/matrix
    math) AND that at least one tuple differs from PDFBox (keeps the documented
    CMM divergence honest)."""
    _comp, _init, rgb = _probe
    cs, inputs = _battery()[name]
    java = rgb[name]
    expected = _PYPDFBOX_DIVERGENT_EXPECTED[name]
    assert len(java) == len(inputs)
    any_diff = False
    for comps, j_rgb, exp in zip(inputs, java, expected, strict=True):
        py_rgb = _rgb_int(cs, list(comps))
        assert py_rgb == exp, (
            f"{name} {comps}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != j_rgb:
            any_diff = True
    assert any_diff, (
        f"{name}: pypdfbox now matches PDFBox on every tuple — the documented "
        f"XYZ->sRGB CMM divergence no longer holds; move {name} to the "
        f"pass-through/exact tier."
    )
