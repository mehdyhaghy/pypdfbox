"""Live PDFBox differential parity for axial shadings over a *non-Device*
colour space.

Companion to ``test_function_shading_oracle.py`` (Type 1) and
``test_shading_extend_oracle.py`` (axial / radial extend), all of which paint
shadings whose ``/ColorSpace`` is ``DeviceRGB`` / ``DeviceGray``. This module
pins the path those tests never exercise: a Type 2 (axial) shading whose
``/ColorSpace`` is **Separation** or **Indexed**, so the shading's
``/Function`` output is *not* RGB — it is the colour space's *input* (a tint
for Separation, an index for Indexed) that the colour space then converts to
RGB.

* **separation_axial** — ``/ColorSpace [/Separation /MyTint /DeviceRGB
  <tint>]`` with a 1-component tint ramp ``0 -> 1`` along the axis. The tint
  transform maps ``0 -> blue (0,0,1)``, ``1 -> yellow (1,1,0)``; the shading
  ``/Function`` produces the tint, the Separation colour space runs it through
  the tint transform to the alternate DeviceRGB. A DeviceRGB-only renderer
  would treat the single tint value as DeviceGray (g,g,g) — grossly wrong.
* **indexed_axial** — ``/ColorSpace [/Indexed /DeviceRGB 3 <palette>]`` with a
  4-entry palette (red, green, blue, white). The shading ``/Function`` (Type 0
  sampled, range ``[0 3]``) produces an *index*; the Indexed colour space
  dereferences the palette. A DeviceRGB-only renderer would treat the index as
  a grey level — wrong.

Both fixtures are *built and rendered in Java* by
``oracle/probes/NonDeviceShadingProbe.java`` (which saves the PDF to a path the
Python side then loads), so the two engines render byte-identical fixtures and
any grid divergence is a rendering-pipeline difference, not a writer one.

Comparison uses the render oracle's shared fingerprint:

* **Exact page dimensions** — a mismatch is a real bug (scale / media-box).
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF).

Separation / Indexed colour conversion has documented tolerance tiers (the
tint-transform float-rounding and palette quantisation leave a small uniform
offset versus PDFBox's per-axis colour table); the whole-page render gate
``MAD < 6`` / ``MAXDIFF < 60`` applies and comfortably separates a correct
colour-space conversion from the DeviceGray-impostor failure mode (guarded
below).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_LABELS = ("separation_axial", "indexed_axial")


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _oracle(label: str, out: Path) -> tuple[tuple[int, int], list[int]]:
    """Run the probe: it writes the fixture PDF to ``out`` *and* returns the
    Java render fingerprint of that same file."""
    lines = run_probe_text(
        "NonDeviceShadingProbe", label, str(out)
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _pypdfbox_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_non_device_shading_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    (java_w, java_h), java_grid = _oracle(label, fixture)
    (py_w, py_h), py_grid = _pypdfbox_grid(fixture)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity — catches the function output being treated
    #     as DeviceGray/RGB instead of routed through the Separation tint
    #     transform or the Indexed palette lookup.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — non-Device shading colour grossly divergent "
        f"(tint transform / palette lookup not applied)"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond AA / quantisation"
    )


@requires_oracle
@pytest.mark.parametrize("label", _LABELS, ids=_LABELS)
def test_devicegray_impostor_would_fail_tolerance(
    label: str, tmp_path: Path
) -> None:
    """Guard the gate: the failure mode is treating the shading function's
    single-component output as DeviceGray ``(g, g, g)`` instead of running it
    through the Separation tint transform / Indexed palette. That impostor —
    a luminance ramp built from the raw function output — must score outside
    tolerance versus PDFBox's actual colour-space conversion, proving the gate
    discriminates the conversion from the raw-value fallback."""
    fixture = tmp_path / f"{label}.pdf"
    _dims, java_grid = _oracle(label, fixture)
    # The DeviceGray impostor: the function output along the axis is a linear
    # ramp 0..1 (separation tint) or 0..3 index→{0,255}; as a grey level that
    # spans 0..255 left→right. Build the matching 16-col ramp, broadcast to
    # all rows (the shading is horizontal), to model the wrong-colourspace
    # render.
    impostor: list[int] = []
    for _row in range(_GRID):
        for col in range(_GRID):
            impostor.append(round(col / (_GRID - 1) * 255))
    diffs = [abs(a - b) for a, b in zip(java_grid, impostor, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — a DeviceGray-impostor ramp passes "
        f"the MAD gate ({mad:.2f}); the gate cannot tell the colour-space "
        f"conversion from the raw-function fallback"
    )
