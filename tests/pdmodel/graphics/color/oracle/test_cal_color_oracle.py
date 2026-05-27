"""Live PDFBox differential parity for the CIE-based ``CalRGB`` / ``CalGray``
``toRGB`` conversions (PDF 32000-1 §8.6.5.2/§8.6.5.3).

The Java side is ``oracle/probes/CalColorProbe.java``. It builds a ``PDCalRGB``
(``/WhitePoint`` + ``/Gamma`` + ``/Matrix``) and a ``PDCalGray``
(``/WhitePoint`` + ``/Gamma``) from in-memory COS objects and, for a battery of
input tuples (0 / 0.5 / 1 per component plus mixed), emits ``csname comp... ->
r g b`` lines (RGB are 0-255 ints, ``round(component*255)`` clamped to
``[0, 255]``).

Upstream behaviour (verified by disassembling PDFBox 3.0.7):

* ``PDCalRGB.toRGB`` / ``PDCalGray.toRGB`` only run the calibrated CIE pipeline
  when ``isWhitePoint()`` is true, i.e. the ``/WhitePoint`` is exactly the unit
  tristimulus ``(1, 1, 1)`` (the documented PDFBOX-2553 hack). For any other
  white point they SKIP calibration and return the input components verbatim
  (CalRGB: ``[A, B, C]``; CalGray: ``[A, A, A]``).
* The calibrated path is ``A' = A ** gamma`` (per component) -> for CalRGB the
  column-major ``/Matrix`` maps ``A'B'C'`` to XYZ, for CalGray the gamma-decoded
  value is fed to the CMM as ``X = Y = Z`` (the white point is NOT applied — it
  is the unit tristimulus on this branch). Then XYZ -> sRGB via the AWT CMM
  (``ColorSpace.CS_CIEXYZ.toRGB``, a D50 PCS).

Two parity tiers:

**Exact-match / pass-through tier** — the white point is non-unit so both
sides skip CIE calibration and return components verbatim, so the only step is
``round(component*255)``. pypdfbox (Python ``float`` == C ``double``) and PDFBox
(Java ``float``) agree to within a documented <=1/255 float-vs-double rounding
artifact that only bites when ``component*255`` lands exactly on an ``x.5``
boundary (e.g. ``0.3f*255 = 76.5`` rounds up in float but ``0.3*255 = 76.499...``
rounds down in double). That 1-LSB tolerance is NOT a colour-math difference —
the gamma/matrix/white-point handling is bit-identical (verbatim pass-through).

**Documented-divergence tier** — the unit-white-point calibrated path. The
gamma decode and the ``/Matrix`` application are tight (deterministic float
arithmetic, identical on both sides — pure-primary identity-matrix inputs land
byte-exact), but the FINAL XYZ -> sRGB step diverges: PDFBox routes XYZ through
the JVM AWT CMM (D50 profile connection space) while pypdfbox uses the explicit
IEC 61966-2-1 D65 sRGB matrix (same project choice as ``LabCustom`` /
DeviceCMYK in ``test_color_to_rgb_oracle.py``). The D50-vs-D65 PCS shift makes
deltas reach 6-48/255 — these are NOT rounding epsilons. pypdfbox's own output
is pinned (regression guard) and at least one tuple is asserted to differ from
PDFBox (keeps the divergence rationale honest).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_cal_rgb import PDCalRGB
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match CalColorProbe.clamp255) ----------


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
    [0.5, 0.0, 0.0],
    [0.0, 0.5, 0.0],
    [0.0, 0.0, 0.5],
    [0.3, 0.6, 0.9],
    [0.25, 0.5, 0.75],
]
_GRAY_INPUTS = [[0.0], [0.25], [0.5], [0.75], [1.0]]


# Map the probe's emitted name -> (builder, list of input tuples). Inputs MUST
# match CalColorProbe.java exactly, in the same order.
def _battery() -> dict[str, tuple[object, list[list[float]]]]:
    return {
        "CalRgbUnit": (_cal_rgb(_UNIT, _GAMMA_RGB, _MATRIX), _RGB_INPUTS),
        "CalRgbIdent": (_cal_rgb(_UNIT, [2.2, 2.2, 2.2], _IDENTITY), _RGB_INPUTS),
        "CalRgbD65": (_cal_rgb(_D65, _GAMMA_RGB, _MATRIX), _RGB_INPUTS),
        "CalGrayUnit22": (_cal_gray(_UNIT, 2.2), _GRAY_INPUTS),
        "CalGrayUnit10": (_cal_gray(_UNIT, 1.0), _GRAY_INPUTS),
        "CalGrayD65": (_cal_gray(_D65, 2.2), _GRAY_INPUTS),
    }


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
# caught; the PDFBox value (different by design — JVM CMM) is asserted to
# actually differ so the divergence rationale stays honest.
_PYPDFBOX_DIVERGENT_EXPECTED: dict[str, list[tuple[int, int, int]]] = {
    "CalRgbUnit": [
        (0, 0, 0),
        (255, 255, 255),
        (146, 128, 120),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (146, 0, 0),
        (0, 128, 0),
        (0, 0, 120),
        (95, 154, 228),
        (81, 128, 188),
    ],
    "CalRgbIdent": [
        (0, 0, 0),
        (255, 249, 244),
        (140, 125, 123),
        (255, 0, 67),
        (0, 255, 0),
        (0, 57, 255),
        (219, 0, 29),
        (0, 171, 0),
        (0, 24, 132),
        (0, 199, 228),
        (0, 167, 191),
    ],
    "CalGrayUnit22": [
        (0, 0, 0),
        (68, 60, 59),
        (140, 125, 123),
        (209, 188, 185),
        (255, 249, 244),
    ],
    "CalGrayUnit10": [
        (0, 0, 0),
        (149, 134, 131),
        (204, 183, 180),
        (244, 219, 215),
        (255, 249, 244),
    ],
}


def _parse_probe(text: str) -> dict[str, list[tuple[int, int, int]]]:
    """Parse ``csname comp... -> r g b`` lines into name -> [(r,g,b), ...]."""
    out: dict[str, list[tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "->" not in line:
            continue
        left, right = line.split("->")
        name = left.split()[0]
        r, g, b = (int(x) for x in right.split())
        out.setdefault(name, []).append((r, g, b))
    return out


@pytest.fixture(scope="module")
def _java_rgb() -> dict[str, list[tuple[int, int, int]]]:
    return _parse_probe(run_probe_text("CalColorProbe"))


# ---------- pass-through tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_PASSTHROUGH))
def test_cal_color_to_rgb_passthrough(
    name: str,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """Non-unit white point: both sides skip CIE calibration and return the
    input components verbatim. The only step is ``round(component*255)``, so a
    mismatch beyond the documented <=1/255 float-vs-double x.5-boundary rounding
    artifact is a real bug (missing/incorrect pass-through shortcut)."""
    cs, inputs = _battery()[name]
    java = _java_rgb[name]
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
def test_cal_color_to_rgb_documented_divergence(
    name: str,
    _java_rgb: dict[str, list[tuple[int, int, int]]],
) -> None:
    """Unit white point -> calibrated CIE pipeline. The gamma decode and the
    ``/Matrix`` application are deterministic float arithmetic identical on both
    sides; only the FINAL XYZ->sRGB step diverges (pypdfbox: explicit IEC
    61966-2-1 D65 matrix; PDFBox: the JVM AWT CMM with a D50 PCS). We assert
    both that pypdfbox matches its pin (regression guard for the gamma/matrix
    math) AND that at least one tuple differs from PDFBox (keeps the documented
    CMM divergence honest)."""
    cs, inputs = _battery()[name]
    java = _java_rgb[name]
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
