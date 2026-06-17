"""Live PDFBox differential parity for the **Lab** colour space
(PDF 32000-1 §8.6.5.4) — the structural surface, the single-value
``toRGB`` conversion, AND the ``toRGBImage`` raster path.

The Java side is ``oracle/probes/LabImageProbe.java``. It builds three
``[/Lab << /WhitePoint [...] /Range [...] >>]`` spaces (D50 and D65 white
points, plus a D50 space with an asymmetric ``[-128 127 -128 127]``
``/Range``) and emits, line-oriented:

* ``STRUCT <name> <numComponents> ic <c0> <c1> <c2>`` — the component count
  and ``getInitialColor`` components.
* ``RGB <name> L a b -> r g b`` — a battery of single L*a*b* triples run
  through ``PDLab.toRGB`` (RGB 0-255 ints, ``round(component*255)`` clamped).
* ``IMG <name> <w> <h>`` + ``PX <name> r g b ...`` — a 16x16 raster
  (left→right L* ramp, top→bottom a* ramp, fixed mid b*) run through
  ``PDLab.toRGBImage(WritableRaster)``, emitted row-major.

Three parity tiers:

**Structural tier (exact)** — ``getNumberOfComponents() == 3`` and
``getInitialColor()`` are pure dictionary reads (``[0, max(0, aMin),
max(0, bMin)]``), so they must match PDFBox byte-for-byte.

**Single-value ``toRGB`` tier (documented divergence)** — the L*a*b* → XYZ
step (the CIE ``inverse`` companding scaled by the dictionary
``/WhitePoint``) is deterministic float arithmetic identical on both sides,
but the FINAL XYZ → sRGB step diverges: PDFBox routes XYZ through the JVM
AWT CMM (a D50 profile-connection space) while pypdfbox uses the explicit
IEC 61966-2-1 D65 sRGB matrix (the same project choice as ``CalRGB`` /
``CalGray`` / ``LabCustom`` in the sibling colour oracles). pypdfbox's own
output is pinned (regression guard for the Lab→XYZ math) and at least one
tuple is asserted to differ from PDFBox so the divergence rationale stays
honest.

**Raster ``toRGBImage`` tier (MAD/MAXDIFF)** — the per-pixel scaling
(``0..255 → L*=0..100`` / ``a*=minA+t*deltaA`` / ``b*=minB+t*deltaB``) is
byte-identical to upstream's ``toRGBImage`` loop; only the inner ``toRGB``
inherits the documented XYZ→sRGB CMM divergence above. We gate the full
16x16 RGB grid with the established mean-abs / max-abs fingerprint, with a
band wide enough to absorb the D50-vs-D65 PCS shift but tight enough to
catch a mis-strided raster, a dropped ``/Range`` scaling, or a missing
render branch (a Lab image XObject that fails to decode at all).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match LabImageProbe.clamp255) ----------


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: PDLab, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _floats(vals: list[float]) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(v))
    return a


def _lab(white_point: list[float], rng: list[float] | None) -> PDLab:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    d = COSDictionary()
    d.set_item("WhitePoint", _floats(white_point))
    if rng is not None:
        d.set_item("Range", _floats(rng))
    arr.add(d)
    return PDLab(arr)


_D50 = [0.9642, 1.0, 0.8249]
_D65 = [0.9505, 1.0, 1.089]
_DEF_RANGE = [-100.0, 100.0, -100.0, 100.0]
_ASYM_RANGE = [-128.0, 127.0, -128.0, 127.0]

_INPUTS = [
    [0.0, 0.0, 0.0],
    [100.0, 0.0, 0.0],
    [50.0, 0.0, 0.0],
    [53.23, 80.11, 67.22],
    [87.74, -86.18, 83.18],
    [32.30, 79.20, -107.86],
    [25.0, 60.0, -60.0],
    [90.0, -30.0, 70.0],
    [75.0, 20.0, -40.0],
    [40.0, -50.0, 30.0],
]

_SPACES = {
    "LabD50": _lab(_D50, _DEF_RANGE),
    "LabD65": _lab(_D65, _DEF_RANGE),
    "LabAsym": _lab(_D50, _ASYM_RANGE),
}

# pypdfbox's own deterministic single-value output. Pinned so a regression
# in the Lab→XYZ companding / white-point scaling / XYZ→sRGB matrix is
# caught; the PDFBox value (different by design — JVM CMM, D50 PCS) is
# asserted to actually differ so the divergence rationale stays honest.
_PIN: dict[str, list[tuple[int, int, int]]] = {
    "LabD50": [
        (0, 0, 0),
        (255, 252, 221),
        (128, 118, 102),
        (255, 0, 0),
        (49, 254, 0),
        (98, 0, 225),
        (108, 0, 134),
        (218, 238, 52),
        (206, 172, 226),
        (0, 111, 29),
    ],
    "LabD65": [
        (0, 0, 0),
        (255, 255, 255),
        (119, 119, 119),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (92, 0, 153),
        (210, 239, 82),
        (182, 176, 255),
        (0, 112, 41),
    ],
}

# Raster grid tolerance: the per-pixel L*a*b* scaling is byte-exact, only the
# inner XYZ→sRGB step carries the documented D50-vs-D65 PCS divergence. The
# band is wide enough to absorb that shift yet narrow enough to catch a
# mis-strided / unscaled raster or a missing render branch.
_IMG_MAD_TOLERANCE = 18.0
# The worst single-channel diff lands on high-L*, low-a* (cyan-ish) pixels
# where pypdfbox's D65 sRGB matrix yields a small positive red while the
# PDFBox D50-PCS CMM clamps red to 0 — the documented XYZ→sRGB CMM shift,
# the same class as the (49,254,0) vs (0,255,0) divergence in the
# single-value tier. The mean stays low (~8), confirming the bulk of the
# grid agrees and only saturated-gamut cells reach this band (observed
# worst ~93/255 on the D50 cyan-gamut cells).
_IMG_MAXDIFF_TOLERANCE = 100


# ---------- probe parsing ----------


def _parse_probe(text: str) -> dict[str, dict[str, object]]:
    """Parse the line-oriented probe output into a per-name record with
    ``components`` / ``initial`` / ``rgb`` / ``image`` keys."""
    out: dict[str, dict[str, object]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        tok = line.split()
        kind = tok[0]
        name = tok[1]
        rec = out.setdefault(name, {})
        if kind == "STRUCT":
            rec["components"] = int(tok[2])
            assert tok[3] == "ic"
            rec["initial"] = [float(v) for v in tok[4:]]
        elif kind == "RGB":
            arrow = tok.index("->")
            rgb = (int(tok[arrow + 1]), int(tok[arrow + 2]), int(tok[arrow + 3]))
            rec.setdefault("rgb", []).append(rgb)  # type: ignore[union-attr]
        elif kind == "IMG":
            rec["dims"] = (int(tok[2]), int(tok[3]))
        elif kind == "PX":
            rec["pixels"] = [int(v) for v in tok[2:]]
    return out


@pytest.fixture(scope="module")
def _java() -> dict[str, dict[str, object]]:
    return _parse_probe(run_probe_text("LabImageProbe"))


# ---------- structural tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_SPACES))
def test_lab_structural_matches_pdfbox(
    name: str, _java: dict[str, dict[str, object]]
) -> None:
    """Component count + initial colour are pure dictionary reads, so they
    must match PDFBox byte-for-byte."""
    cs = _SPACES[name]
    rec = _java[name]
    assert cs.get_number_of_components() == rec["components"]
    py_initial = cs.get_initial_color().get_components()
    java_initial = rec["initial"]
    assert len(py_initial) == len(java_initial)
    for p, j in zip(py_initial, java_initial, strict=True):
        assert p == pytest.approx(j, abs=1e-6), (
            f"{name}: initial colour {py_initial} != PDFBox {java_initial}"
        )


# ---------- single-value toRGB tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_PIN))
def test_lab_to_rgb_documented_divergence(
    name: str, _java: dict[str, dict[str, object]]
) -> None:
    """Lab→XYZ is deterministic and identical on both sides; only the final
    XYZ→sRGB step diverges (pypdfbox: explicit IEC 61966-2-1 D65 matrix;
    PDFBox: the JVM AWT CMM with a D50 PCS). Assert both that pypdfbox
    matches its pin (regression guard for the Lab→XYZ math) AND that at
    least one tuple differs from PDFBox (keeps the documented CMM
    divergence honest)."""
    cs = _SPACES[name]
    java = _java[name]["rgb"]
    expected = _PIN[name]
    assert len(java) == len(_INPUTS)  # type: ignore[arg-type]
    any_diff = False
    for comps, j_rgb, exp in zip(_INPUTS, java, expected, strict=True):  # type: ignore[arg-type]
        py_rgb = _rgb_int(cs, list(comps))
        assert py_rgb == exp, (
            f"{name} {comps}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != tuple(j_rgb):
            any_diff = True
    assert any_diff, (
        f"{name}: pypdfbox now matches PDFBox on every tuple — the documented "
        f"XYZ->sRGB CMM divergence no longer holds; re-tier {name}."
    )


# ---------- raster toRGBImage tier ----------


def _build_ramp(width: int, height: int) -> bytes:
    """16x16 L* ramp left→right, a* ramp top→bottom, fixed mid b* — must
    match the byte layout LabImageProbe feeds its WritableRaster."""
    out = bytearray(width * height * 3)
    p = 0
    for y in range(height):
        for x in range(width):
            out[p] = round(x * 255.0 / (width - 1))
            out[p + 1] = round(y * 255.0 / (height - 1))
            out[p + 2] = 128
            p += 3
    return bytes(out)


@requires_oracle
@pytest.mark.parametrize("name", sorted(_SPACES))
def test_lab_to_rgb_image_matches_pdfbox(
    name: str, _java: dict[str, dict[str, object]]
) -> None:
    """``toRGBImage`` over a 16x16 Lab raster. The per-pixel L*a*b* scaling
    is byte-identical to upstream; only the inner XYZ→sRGB step carries the
    documented CMM divergence. Gate the full RGB grid with the MAD/MAXDIFF
    fingerprint — a band wide enough to absorb the D50-vs-D65 PCS shift but
    tight enough to catch a mis-strided / unscaled raster or a dropped
    ``/Range`` scaling."""
    cs = _SPACES[name]
    rec = _java[name]
    width, height = rec["dims"]  # type: ignore[misc]
    java_px = rec["pixels"]

    img = cs.to_rgb_image(_build_ramp(width, height), width, height)
    assert img.size == (width, height)
    py_px = list(img.tobytes())

    assert len(py_px) == len(java_px), (  # type: ignore[arg-type]
        f"{name}: pypdfbox emitted {len(py_px)} channel values, "
        f"PDFBox {len(java_px)}"  # type: ignore[arg-type]
    )
    diffs = [abs(a - b) for a, b in zip(py_px, java_px, strict=True)]  # type: ignore[arg-type]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _IMG_MAD_TOLERANCE, (
        f"{name}: mean abs channel diff {mad:.2f} >= {_IMG_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — Lab raster likely mis-strided, the /Range "
        f"scaling dropped, or the render branch absent"
    )
    assert maxdiff < _IMG_MAXDIFF_TOLERANCE, (
        f"{name}: worst channel diff {maxdiff} >= {_IMG_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond the CMM shift"
    )
