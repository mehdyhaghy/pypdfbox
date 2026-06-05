"""Pixel-exact parity for axial/radial shading ``/Domain`` values that are not
the default ``[0 1]``, paired with ``/Extend``, against Apache PDFBox 3.0.7.

Wave 1488 (DEFERRED.md: "Axial shading domain remap for /Domain values outside
[0,1] with /Extend"). The lite renderer (``PDFRenderer._paint_axial_shading`` /
``_paint_radial_shading``) builds a 256-entry colour ramp and indexes it with
upstream's truncating ``key = (int)(inputValue * factor)`` math
(AxialShadingContext / RadialShadingContext ``getRaster``). For the common
``/Domain [0 1]`` case the ramp index coincides regardless of how the extend
clamp is written. For a non-default ``/Domain`` the two engines only agree if
the *axial* extend branch substitutes the raw ``domain[0]`` / ``domain[1]``
endpoint for ``inputValue`` (NOT the spec-literal ``0`` / ``1``) before the
``(int)(inputValue*factor)`` lookup — the upstream quirk this wave pins.

Findings the live oracle established for this surface:

* **axial /Domain ⊆ [0,1]** (e.g. ``[0.25 0.75]``) with ``/Extend [true true]``
  — the out-of-axis pixels take the colour at ramp fraction ``domain[0]`` /
  ``domain[1]`` (NOT the domain-endpoint colour). PDFBox: a left-extend pixel of
  a red→blue gradient on ``[0.25 0.75]`` is the colour at fraction 0.25 of the
  *ramp*, i.e. ~``(159,0,95)``, not the pure start colour ``(191,0,64)``. This
  was the one real divergence; fixed by mirroring the axial quirk.

* **axial /Domain outside [0,1]** (``[0 2]``, ``[-1 1]``) with ``/Extend`` —
  upstream computes ``key = (int)(domain[1]*factor)`` which overruns the colour
  table and **throws ``ArrayIndexOutOfBoundsException``** (verified against
  PDFBox 3.0.7: ``AxialShadingContext.getRaster:238``, ``Index 284 out of
  bounds for length 143``). pypdfbox clamps the ramp index instead of crashing
  — an intentional, documented divergence (a library must not abort on a
  malformed-but-renderable shading). These cases are pinned oracle-free only;
  no ``@requires_oracle`` assertion compares them to the (crashing) Java path.

* **radial /Domain ⊆ [0,1]** — upstream radial sets ``inputValue = 0`` / ``1``
  on the extend branches (not the domain endpoint), so the radial lite renderer
  already matched; this module re-pins it as a regression guard.

Each fixture is a 100x100 page (1:1 device pixels at 72 DPI) with one
``/Sh0 sh`` clipped to the page. ``ShadingPixelProbe.java`` (wave 1484) supplies
the per-pixel Java RGB; ``_CHANNEL_TOL`` covers only sub-step ramp-quantisation
rounding (truncating ``(int)`` vs the test's reference), so anything larger is a
real divergence.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.shading import PDShadingType2, PDShadingType3
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE = 100.0
# Sub-step ramp quantisation only (truncating index vs the reference). A wrong
# extend substitution or a domain-misremap would shift a channel by tens.
_CHANNEL_TOL = 4


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _arr(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr


def _exp_function(
    c0: list[float], c1: list[float], domain: tuple[float, float]
) -> COSStream:
    """Type 2 exponential interpolation over ``domain`` (must equal the
    shading's /Domain for a single-function Type 2/3 shading)."""
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 2)
    fn.set_item(COSName.get_pdf_name("Domain"), _arr(*domain))
    a0 = COSArray()
    for v in c0:
        a0.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C0"), a0)
    a1 = COSArray()
    for v in c1:
        a1.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C1"), a1)
    fn.set_int(COSName.get_pdf_name("N"), 1)
    return fn


def _sampled_function(domain: tuple[float, float]) -> COSStream:
    """Type 0 sampled function: a 2-sample red→blue ramp over ``domain``.

    Linear interpolation between two RGB samples reproduces the same gradient
    as the Type 2 ``N=1`` exponential, so the same sample-point expectations
    hold — this variant exercises the sampled path through the same domain
    remap / extend code."""
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 0)
    fn.set_item(COSName.get_pdf_name("Domain"), _arr(*domain))
    fn.set_item(COSName.get_pdf_name("Range"), _arr(0.0, 1.0, 0.0, 1.0, 0.0, 1.0))
    size = COSArray()
    size.add(COSFloat(2))
    fn.set_item(COSName.get_pdf_name("Size"), size)
    fn.set_int(COSName.get_pdf_name("BitsPerSample"), 8)
    # two samples: (1,0,0) red then (0,0,1) blue, each channel one byte
    fn.set_data(struct.pack("6B", 255, 0, 0, 0, 0, 255))
    return fn


def _save(
    doc: PDDocument,
    page: PDPage,
    shading: PDShadingType2 | PDShadingType3,
    out: Path,
) -> Path:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh0"),
        shading.get_cos_object(),
    )
    stream = COSStream()
    stream.set_raw_data(b"0 0 100 100 re W n /Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _axial(
    out: Path,
    domain: tuple[float, float],
    extend: tuple[bool, bool],
    *,
    sampled: bool = False,
) -> Path:
    """Horizontal axis x 30..70, red→blue over ``domain``."""
    doc, page = _new_doc()
    sh = PDShadingType2()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_arr(30.0, 0.0, 70.0, 0.0))
    fn = (
        _sampled_function(domain)
        if sampled
        else _exp_function([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], domain)
    )
    sh.set_function(fn)
    sh.set_extend(*extend)
    sh.set_domain(list(domain))
    return _save(doc, page, sh, out)


def _radial(
    out: Path, domain: tuple[float, float], extend: tuple[bool, bool]
) -> Path:
    """Concentric circles r0=10 → r1=40, red→blue over ``domain``."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_arr(50.0, 50.0, 10.0, 50.0, 50.0, 40.0))
    sh.set_function(_exp_function([1.0, 0.0, 0.0], [0.0, 0.0, 1.0], domain))
    sh.set_extend(*extend)
    sh.set_domain(list(domain))
    return _save(doc, page, sh, out)


# ---------------------------------------------------------------------------
# cases: (builder, [(x, y, (r,g,b)) expected pypdfbox RGB], oracle_safe)
# oracle_safe == False marks fixtures where the Java path raises (domain
# outside [0,1] + extend) — pinned oracle-free only.
# ---------------------------------------------------------------------------


def _b_axial_quirk(out: Path) -> Path:
    return _axial(out, (0.25, 0.75), (True, True))


def _b_axial_quirk_sampled(out: Path) -> Path:
    return _axial(out, (0.25, 0.75), (True, True), sampled=True)


def _b_axial_quirk_noext(out: Path) -> Path:
    return _axial(out, (0.25, 0.75), (False, False))


def _b_axial_d02_ext(out: Path) -> Path:
    return _axial(out, (0.0, 2.0), (True, True))


def _b_axial_dm11_ext(out: Path) -> Path:
    return _axial(out, (-1.0, 1.0), (True, True))


def _b_radial_quirk(out: Path) -> Path:
    return _radial(out, (0.25, 0.75), (True, True))


# x=5 (left, u<0 -> extend[0]), x=50 (mid), x=95 (right, u>1 -> extend[1]).
_CASES: dict[str, tuple] = {
    # axial /Domain [0.25 0.75] + extend: left pixel is the colour at ramp
    # fraction 0.25 (~(160,0,95)), right at 0.75 (~(96,0,159)), NOT the pure
    # start/end colour. This is the upstream-quirk pin.
    "axial_quirk_ext": (
        _b_axial_quirk,
        [(5, 50, (160, 0, 95)), (50, 50, (128, 0, 127)), (95, 50, (96, 0, 159))],
        True,
    ),
    # The 2-sample sampled ramp indexes the quirk fraction (0.25 / 0.75) into a
    # ramp whose ends are the pure samples, so the extend pixels land at ~25% /
    # ~75% blends — different ramp shape from the N=1 exp variant, same code
    # path. Both engines agree.
    "axial_quirk_ext_sampled": (
        _b_axial_quirk_sampled,
        [(5, 50, (192, 0, 63)), (50, 50, (128, 0, 127)), (95, 50, (64, 0, 191))],
        True,
    ),
    # same domain, no extend: out-of-axis pixels untouched (white); mid blends.
    "axial_quirk_noext": (
        _b_axial_quirk_noext,
        [(5, 50, (255, 255, 255)), (50, 50, (128, 0, 127)),
         (95, 50, (255, 255, 255))],
        True,
    ),
    # /Domain [0 2] + extend: Java throws (index 284 > table len). pypdfbox
    # clamps -> left pixel is the pure start colour (frac clamps to 0), right
    # the end colour (frac clamps to ramp_steps-1). Oracle-free pin only.
    "axial_d02_ext": (
        _b_axial_d02_ext,
        [(5, 50, (255, 0, 0)), (95, 50, (0, 0, 255))],
        False,
    ),
    # /Domain [-1 1] + extend: Java throws (negative index). pypdfbox clamps.
    "axial_dm11_ext": (
        _b_axial_dm11_ext,
        [(5, 50, (255, 0, 0)), (95, 50, (0, 0, 255))],
        False,
    ),
    # radial /Domain [0.25 0.75] + extend: upstream radial sets inputValue 0/1
    # (NOT the domain endpoint), so ramp[0]/ramp[255] are consulted. The inner
    # circle (s=0) -> ramp[0] = colour at domain_lo (~(191,0,64)); points
    # outside the outer circle extend to ramp[255] = colour at domain_hi
    # (~(64,0,191)). pypdfbox already matched here (no quirk on the radial side).
    "radial_quirk_ext": (
        _b_radial_quirk,
        [(50, 50, (191, 0, 64)), (5, 5, (64, 0, 191)), (95, 95, (64, 0, 191))],
        True,
    ),
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _py_pixels(
    fixture: Path, pts: list[tuple[int, int]]
) -> tuple[tuple[int, int], list[tuple[int, int, int]]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    px = img.load()
    return img.size, [px[x, y] for (x, y) in pts]


def _java_pixels(
    fixture: Path, pts: list[tuple[int, int]]
) -> tuple[tuple[int, int], list[tuple[int, int, int]]]:
    args = [str(fixture), "0"]
    for x, y in pts:
        args += [str(x), str(y)]
    lines = run_probe_text("ShadingPixelProbe", *args).splitlines()
    w, h = (int(v) for v in lines[0].split())
    out: list[tuple[int, int, int]] = []
    for ln in lines[1:]:
        r, g, b = (int(v) for v in ln.split())
        out.append((r, g, b))
    return (w, h), out


# ---------------------------------------------------------------------------
# oracle-free regression pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_pypdfbox_pixel_pins(label: str, tmp_path: Path) -> None:
    """pypdfbox renders the pinned RGB at each sample point — regression guard
    for the domain remap / extend quirk without needing the live oracle."""
    builder, samples, _oracle_safe = _CASES[label]
    fixture = builder(tmp_path / f"{label}.pdf")
    pts = [(x, y) for (x, y, _rgb) in samples]
    (w, h), got = _py_pixels(fixture, pts)
    assert (w, h) == (100, 100), f"{label}: unexpected render size {w}x{h}"
    for (x, y, expected), actual in zip(samples, got, strict=True):
        diff = max(abs(a - b) for a, b in zip(expected, actual, strict=True))
        assert diff <= _CHANNEL_TOL, (
            f"{label}: pixel ({x},{y}) = {actual}, expected ~{expected} "
            f"(per-channel diff {diff} > {_CHANNEL_TOL})"
        )


# ---------------------------------------------------------------------------
# live differential (only oracle-safe cases — domains outside [0,1] crash Java)
# ---------------------------------------------------------------------------


_ORACLE_CASES = [k for k, v in _CASES.items() if v[2]]


@requires_oracle
@pytest.mark.parametrize("label", _ORACLE_CASES, ids=_ORACLE_CASES)
def test_pixel_rgb_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each sampled pixel matches PDFBox within ramp-quantisation rounding. A
    wrong extend substitution (0/1 vs domain endpoint) would shift the channel
    by tens of levels — far beyond ``_CHANNEL_TOL``."""
    builder, samples, _oracle_safe = _CASES[label]
    fixture = builder(tmp_path / f"{label}.pdf")
    pts = [(x, y) for (x, y, _rgb) in samples]
    (jw, jh), java = _java_pixels(fixture, pts)
    (pw, ph), py = _py_pixels(fixture, pts)
    assert (pw, ph) == (jw, jh), (
        f"{label}: render dims diverge pypdfbox={pw}x{ph} java={jw}x{jh}"
    )
    for (x, y, _exp), jc, pc in zip(samples, java, py, strict=True):
        diff = max(abs(a - b) for a, b in zip(jc, pc, strict=True))
        assert diff <= _CHANNEL_TOL, (
            f"{label}: pixel ({x},{y}) java={jc} pypdfbox={pc} "
            f"per-channel diff {diff} > {_CHANNEL_TOL}"
        )


@requires_oracle
def test_axial_quirk_not_endpoint_colour(tmp_path: Path) -> None:
    """Guard: the axial [0.25 0.75]+extend left pixel is the ramp-fraction-0.25
    colour in *both* engines, proving the gate discriminates the upstream quirk
    from the (wrong) spec-literal domain-endpoint colour ``(191,0,64)``."""
    fixture = _b_axial_quirk(tmp_path / "axial_quirk.pdf")
    pts = [(5, 50)]
    (_jw, _jh), java = _java_pixels(fixture, pts)
    (_pw, _ph), py = _py_pixels(fixture, pts)
    # The naive domain-endpoint colour would be ~(191,0,64); both engines must
    # instead land near the ramp-fraction-0.25 colour (~(159,0,95)).
    assert abs(java[0][0] - 191) > 10, "oracle unexpectedly at endpoint colour"
    assert abs(py[0][0] - 191) > 10, "pypdfbox regressed to endpoint colour"
    assert max(abs(a - b) for a, b in zip(java[0], py[0], strict=True)) <= _CHANNEL_TOL
