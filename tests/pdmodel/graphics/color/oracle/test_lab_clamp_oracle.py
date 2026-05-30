"""Live PDFBox differential parity for ``PDLab.toRGB(float[])`` input-domain
handling at and beyond the legal L*/a*/b* bounds (PDF 32000-1 §8.6.5.4).

The Java side is ``oracle/probes/LabClampProbe.java``. It builds two
``[/Lab << /WhitePoint [...] /Range [...] >>]`` spaces — a default-range D50
space and a D50 space with a custom asymmetric ``/Range [-50 60 -70 40]`` —
and drives ``PDLab.toRGB`` over a battery of triples whose components sit at,
below, and above the bounds (``L*`` outside ``[0, 100]``; ``a*``/``b*``
outside the ``/Range`` slots). The probe forwards the **raw** triple to
``toRGB`` (it never clamps in Java itself) and emits the resulting RGB.

What this surface actually pins
-------------------------------
PDF §8.6.5.4 describes ``L*`` on ``[0, 100]`` and ``a*``/``b*`` on the
``/Range`` bounds, with a producer expected to keep values in range. The
*empirical oracle finding* (see ``LabClampProbe`` output) is that Apache
PDFBox 3.0.7's ``PDLab.toRGB(float[])`` does **NOT** clamp its input domain:
an out-of-range ``L*`` such as ``150`` yields RGB distinct from the clamped
``L*`` of ``100`` (``241 254 176`` vs ``255 255 255`` on the Java side), and
likewise for ``L*`` below ``0`` (e.g. ``-1`` and ``-10`` give continuous,
distinct results rather than collapsing to the ``L*=0`` value). The only
clamp upstream applies is the XYZ ``< 0 → 0`` floor inside its
``convXYZtoRGB`` step — a *post*-companding clamp, not an input-domain one.

pypdfbox's :meth:`PDLab.to_rgb` mirrors this exactly: raw inputs flow through
the CIE ``inverse`` companding (scaled by the dictionary ``/WhitePoint``)
with the same XYZ ``< 0 → 0`` floor and no input-domain clamp. So this test
asserts the **no-clamp parity invariant** structurally (out-of-range inputs
remain distinguishable from their would-be clamped neighbours on both sides)
and pins pypdfbox's own deterministic RGB output as a regression guard.

Two tiers (mirroring ``test_lab_image_oracle.py``)
--------------------------------------------------
**No-clamp structural tier (exact, both sides)** — for the ``L*``-only
out-of-range probes we assert that pypdfbox does NOT collapse the
out-of-range value onto the clamped bound, AND that PDFBox does not either.
This is the load-bearing parity check: it would fire if *either* side
silently started clamping the input domain.

**Pinned ``toRGB`` divergence tier (documented CMM tail)** — pypdfbox's RGB
output is pinned (regression guard for the Lab→XYZ companding + white-point
scaling + no-clamp path). At least one tuple is asserted to differ from
PDFBox so the documented XYZ→sRGB CMM divergence (pypdfbox: explicit IEC
61966-2-1 D65 matrix; PDFBox: the JVM AWT CMM with a D50 PCS — the same
project choice as ``CalRGB`` / ``CalGray`` / the sibling Lab oracle) stays
honest.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match LabClampProbe.clamp255) ----------


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
_DEF_RANGE = [-100.0, 100.0, -100.0, 100.0]
_CUSTOM_RANGE = [-50.0, 60.0, -70.0, 40.0]

# Default-range clamping battery — must match LabClampProbe.defInputs order.
_DEF_INPUTS = [
    [-10.0, 0.0, 0.0],
    [0.0, 0.0, 0.0],
    [150.0, 0.0, 0.0],
    [100.0, 0.0, 0.0],
    [50.0, 200.0, 0.0],
    [50.0, -200.0, 0.0],
    [50.0, 0.0, 200.0],
    [50.0, 0.0, -200.0],
    [-5.0, 150.0, -150.0],
    [120.0, -130.0, 130.0],
    [100.0, 100.0, 100.0],
    [0.0, -100.0, -100.0],
]

# Custom-range clamping battery — must match LabClampProbe.customInputs order.
_CUSTOM_INPUTS = [
    [50.0, 80.0, 0.0],
    [50.0, -80.0, 0.0],
    [50.0, 0.0, 60.0],
    [50.0, 0.0, -90.0],
    [50.0, 60.0, 40.0],
    [50.0, -50.0, -70.0],
    [200.0, 200.0, -200.0],
]

_SPACES = {
    "LabDef": _lab(_D50, _DEF_RANGE),
    "LabCustom": _lab(_D50, _CUSTOM_RANGE),
}

_INPUTS = {
    "LabDef": _DEF_INPUTS,
    "LabCustom": _CUSTOM_INPUTS,
}

# pypdfbox's own deterministic output over the clamp battery. Pinned so a
# regression in the Lab→XYZ companding / white-point scaling / no-clamp input
# path is caught. The PDFBox values differ by design (JVM CMM, D50 PCS); at
# least one tuple is asserted to actually differ so the divergence stays
# honest.
_PIN: dict[str, list[tuple[int, int, int]]] = {
    "LabDef": [
        (0, 0, 0),
        (0, 0, 0),
        (255, 255, 255),
        (255, 252, 221),
        (255, 0, 115),
        (0, 159, 98),
        (147, 116, 0),
        (0, 150, 255),
        (0, 0, 192),
        (0, 255, 0),
        (255, 141, 0),
        (0, 24, 131),
    ],
    "LabCustom": [
        (238, 0, 106),
        (0, 146, 100),
        (145, 116, 0),
        (0, 126, 243),
        (220, 58, 43),
        (0, 143, 210),
        (255, 255, 255),
    ],
}

# Out-of-range L*-only probes whose RGB MUST stay distinct from the same
# space's clamped-bound RGB. (input index, clamped-bound input index) pairs
# into _DEF_INPUTS. L=150 vs L=100, and L=-10 vs L=0. If either side starts
# clamping the input domain these would collapse and the test fires.
_NO_CLAMP_PAIRS = [
    (2, 3),   # L=150 vs L=100 (upper bound)
]


# ---------- probe parsing ----------


def _parse_probe(text: str) -> dict[str, list[tuple[int, int, int]]]:
    """Parse the line-oriented probe output into ``{name: [rgb, ...]}``."""
    out: dict[str, list[tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        tok = line.split()
        if tok[0] != "RGB":
            continue
        name = tok[1]
        arrow = tok.index("->")
        rgb = (int(tok[arrow + 1]), int(tok[arrow + 2]), int(tok[arrow + 3]))
        out.setdefault(name, []).append(rgb)
    return out


@pytest.fixture(scope="module")
def _java() -> dict[str, list[tuple[int, int, int]]]:
    return _parse_probe(run_probe_text("LabClampProbe"))


# ---------- pinned toRGB divergence tier ----------


@requires_oracle
@pytest.mark.parametrize("name", sorted(_SPACES))
def test_lab_clamp_to_rgb_documented_divergence(
    name: str, _java: dict[str, list[tuple[int, int, int]]]
) -> None:
    """Raw out-of-range L*/a*/b* triples run through ``toRGB``. The Lab→XYZ
    companding (with the dictionary ``/WhitePoint`` and the XYZ ``<0→0``
    floor) is deterministic and identical on both sides; only the final
    XYZ→sRGB step diverges (pypdfbox: explicit IEC 61966-2-1 D65 matrix;
    PDFBox: the JVM AWT CMM with a D50 PCS). Assert both that pypdfbox
    matches its pin (regression guard) AND that at least one tuple differs
    from PDFBox (keeps the documented CMM divergence honest)."""
    cs = _SPACES[name]
    java = _java[name]
    inputs = _INPUTS[name]
    expected = _PIN[name]
    assert len(java) == len(inputs)
    assert len(expected) == len(inputs)
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
        f"XYZ->sRGB CMM divergence no longer holds; re-tier {name}."
    )


# ---------- no-clamp structural tier (load-bearing parity) ----------


@requires_oracle
def test_lab_to_rgb_does_not_clamp_input_domain(
    _java: dict[str, list[tuple[int, int, int]]]
) -> None:
    """Load-bearing parity invariant: neither PDFBox nor pypdfbox clamps the
    ``toRGB`` *input* domain. An out-of-range ``L*`` (e.g. 150) must yield RGB
    distinct from the clamped-bound ``L*`` (100) on BOTH sides — empirically
    PDFBox's ``PDLab.toRGB`` passes the raw value through (only the XYZ ``<0→0``
    post-companding floor applies). This test fires if either side silently
    starts clamping the input domain (which would collapse the two onto one
    value)."""
    cs = _SPACES["LabDef"]
    java = _java["LabDef"]
    for oor_idx, bound_idx in _NO_CLAMP_PAIRS:
        oor = _DEF_INPUTS[oor_idx]
        bound = _DEF_INPUTS[bound_idx]

        # PDFBox side: raw vs clamped-bound RGB must differ (no input clamp).
        assert java[oor_idx] != java[bound_idx], (
            f"PDFBox collapsed out-of-range {oor} onto clamped {bound} "
            f"(both -> {java[oor_idx]}) — upstream began clamping the toRGB "
            f"input domain; re-evaluate the no-clamp invariant."
        )

        # pypdfbox side: same — out-of-range stays distinguishable.
        py_oor = _rgb_int(cs, list(oor))
        py_bound = _rgb_int(cs, list(bound))
        assert py_oor != py_bound, (
            f"pypdfbox collapsed out-of-range {oor} onto clamped {bound} "
            f"(both -> {py_oor}) — to_rgb began clamping the input domain, "
            f"diverging from upstream's pass-through behaviour."
        )
