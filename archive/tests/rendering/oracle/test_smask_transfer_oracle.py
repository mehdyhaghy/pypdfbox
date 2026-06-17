"""Live PDFBox differential parity for the ExtGState soft-mask ``/TR``
transfer function.

An ExtGState ``/SMask << /S /Luminosity /G <group> /TR <function> >>`` applies
the ``/TR`` function to each computed mask value *before* it is used as the
per-pixel alpha multiplier (PDF 32000-1 §11.6.5.2). ``/TR`` maps a single
mask sample in ``[0,1]`` back to ``[0,1]``:

* **/Identity** (or absent) — no remap (the control case).
* an inverting Type 4 PostScript function ``{ 1 exch sub }`` — flips the mask
  so the alpha is the complement of the computed luminosity.
* a Type 2 exponential function — a smooth monotone remap.

Each fixture is a tiny one-page PDF synthesised in-memory via pypdfbox's COS +
content-stream API: a yellow full-page backdrop, then a full-page near-black
fill painted under ``gs`` with the soft mask active. The mask GROUP paints a
left→right stepped grey gradient (luminance ~0 at the left edge, ~1 at the
right). So the computed luminosity mask alpha rises left→right; ``/Identity``
leaves it alone (left transparent → yellow, right opaque → black) and the
inverting ``/TR`` flips it (left opaque → black, right transparent → yellow).

Because the inverting ``/TR`` reverses the gradient, its render DIFFERS
materially from the ``/Identity`` control — the guard test below asserts this
difference directly, proving the ``/TR`` function is actually applied (a
renderer that ignores ``/TR`` would render the inverting case identically to
the control).

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a 16x16
average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). A render that
ignores ``/TR`` (or evaluates it wrong) lands far outside this gate against the
Java oracle's transfer-applied render — the guard test measures that divergence
directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_alpha_smask_oracle.py — comfortably above the AA ceiling
# (correct gradient renders measure MAD<=1 here) yet well below the
# gross-failure floor (ignoring /TR on the inverting case = the un-flipped
# gradient, MAD well past the gate against the oracle's transfer-applied render).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)

_BACKDROP_RGB = (1.0, 1.0, 0.0)  # yellow page fill (luma ~226)
_GRAD_STEPS = 10  # number of grey bands in the mask-group gradient


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell)."""
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
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run RenderProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _gradient_group_stream() -> bytes:
    """Content stream painting a left→right stepped grey gradient over the
    full media box: band ``i`` is grey ``i/(steps-1)`` (left ~black, right
    ~white)."""
    band_w = _MB / _GRAD_STEPS
    parts: list[str] = []
    for i in range(_GRAD_STEPS):
        grey = i / (_GRAD_STEPS - 1)
        x0 = i * band_w
        parts.append(f"{grey} {grey} {grey} rg\n{x0} 0 {band_w} {_MB} re\nf\n")
    return "".join(parts).encode("ascii")


def _make_invert_tr() -> COSStream:
    """Type 4 PostScript ``{ 1 exch sub }`` — inverts a unit value."""
    fn = COSStream()
    fn.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(4))
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("Domain"), domain)
    rng = COSArray()
    rng.add(COSFloat(0.0))
    rng.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("Range"), rng)
    fn.set_raw_data(b"{ 1 exch sub }")
    return fn


def _make_exponential_tr() -> COSDictionary:
    """Type 2 exponential function: y = x**2 over [0,1] (a smooth monotone
    remap that darkens the low end of the mask)."""
    fn = COSDictionary()
    fn.set_item(COSName.get_pdf_name("FunctionType"), COSInteger.get(2))
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("Domain"), domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    fn.set_item(COSName.get_pdf_name("C0"), c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    fn.set_item(COSName.get_pdf_name("C1"), c1)
    fn.set_item(COSName.get_pdf_name("N"), COSFloat(2.0))
    return fn


def _build_smask_tr_fixture(path: Path, tr_kind: str) -> None:
    """Yellow full-page backdrop, then a full-page near-black fill painted
    through an ExtGState ``/SMask /S /Luminosity`` whose mask group paints a
    left→right grey gradient, with the ``/TR`` selected by ``tr_kind``:

    * ``"identity"`` → ``/TR /Identity`` (control, no remap)
    * ``"invert"``   → ``/TR`` = Type 4 ``{ 1 exch sub }`` (flips the mask)
    * ``"exponential"`` → ``/TR`` = Type 2 ``y = x**2`` (smooth remap)
    """
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    mask_stream = COSStream()
    mask_stream.set_raw_data(_gradient_group_stream())
    mask_form = PDFormXObject(mask_stream)
    mask_form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB"))
    mask_form.set_group(group)

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
    if tr_kind == "identity":
        smask.set_item(COSName.get_pdf_name("TR"), COSName.get_pdf_name("Identity"))
    elif tr_kind == "invert":
        smask.set_item(COSName.get_pdf_name("TR"), _make_invert_tr())
    elif tr_kind == "exponential":
        smask.set_item(COSName.get_pdf_name("TR"), _make_exponential_tr())
    else:  # pragma: no cover - guard against typos in the builder map
        raise ValueError(f"unknown tr_kind {tr_kind!r}")

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("SMask"), smask)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), egs
    )

    contents = COSStream()
    contents.set_raw_data(
        b"1 1 0 rg\n0 0 100 100 re\nf\n"
        b"q\n/GS0 gs\n0 0 0 rg\n0 0 100 100 re\nf\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(path))
    doc.close()


_BUILDERS = ("identity", "invert", "exponential")


@requires_oracle
@pytest.mark.parametrize("tr_kind", _BUILDERS, ids=_BUILDERS)
def test_smask_transfer_render_matches_pdfbox(tr_kind: str, tmp_path: Path) -> None:
    """Each ``/TR`` variant (control identity, inverting Type 4, exponential
    Type 2) must match Java PDFBox's render of the same fixture within the
    fingerprint gate."""
    fixture = tmp_path / f"smask_tr_{tr_kind}.pdf"
    _build_smask_tr_fixture(fixture, tr_kind)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{tr_kind}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance. Ignoring /TR (or evaluating
    # it wrong) lands far outside this gate.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{tr_kind}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — /TR ignored or mis-evaluated, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{tr_kind}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_inverting_tr_differs_from_identity_control(tmp_path: Path) -> None:
    """Direct-pixel proof that the inverting ``/TR`` is actually applied: the
    mask group's gradient makes the left edge ~transparent (yellow backdrop)
    and the right edge ~opaque (black fill) under ``/Identity``; the inverting
    ``/TR { 1 exch sub }`` must reverse that — left edge ~opaque (black), right
    edge ~transparent (yellow). A renderer that ignored ``/TR`` would render
    the two identically."""
    identity_pdf = tmp_path / "smask_tr_identity.pdf"
    invert_pdf = tmp_path / "smask_tr_invert.pdf"
    _build_smask_tr_fixture(identity_pdf, "identity")
    _build_smask_tr_fixture(invert_pdf, "invert")

    with PDDocument.load(identity_pdf) as doc:
        id_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    with PDDocument.load(invert_pdf) as doc:
        inv_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")

    # Sample near each edge, mid-height, in the gradient direction (x).
    id_left = id_img.getpixel((8, _MB // 2))
    id_right = id_img.getpixel((_MB - 8, _MB // 2))
    inv_left = inv_img.getpixel((8, _MB // 2))
    inv_right = inv_img.getpixel((_MB - 8, _MB // 2))

    # Identity: left ~yellow backdrop (R,G high), right ~black fill (all low).
    assert min(id_left[:2]) >= 150, (
        f"identity left edge {id_left} not the ~transparent (yellow) end"
    )
    assert max(id_right) <= 60, (
        f"identity right edge {id_right} not the ~opaque (black) end"
    )
    # Invert flips it: left ~black fill, right ~yellow backdrop.
    assert max(inv_left) <= 60, (
        f"inverting /TR left edge {inv_left} not flipped to the opaque end — "
        "/TR not applied"
    )
    assert min(inv_right[:2]) >= 150, (
        f"inverting /TR right edge {inv_right} not flipped to the transparent "
        "end — /TR not applied"
    )
    # The inverting render must differ materially from the identity control at
    # both edges — the load-bearing proof that /TR is applied.
    left_gap = max(abs(id_left[i] - inv_left[i]) for i in range(3))
    right_gap = max(abs(id_right[i] - inv_right[i]) for i in range(3))
    assert left_gap >= 100 and right_gap >= 100, (
        f"inverting /TR did not materially change the render vs identity "
        f"(left_gap={left_gap}, right_gap={right_gap}) — /TR appears ignored"
    )


@requires_oracle
def test_ignored_tr_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the *inverting-/TR* fixture but stripping the
    ``/TR`` entry (so the mask is the un-flipped gradient — the exact bug this
    surface guards against) must land outside tolerance against the Java
    oracle's true transfer-applied render, proving the gate detects an ignored
    ``/TR`` rather than passing everything."""
    fixture = tmp_path / "smask_tr_invert.pdf"
    _build_smask_tr_fixture(fixture, "invert")
    _dims, java_grid = _oracle_signature(fixture)

    smask_key = COSName.get_pdf_name("SMask")
    tr_key = COSName.get_pdf_name("TR")
    resources_key = COSName.get_pdf_name("Resources")
    ext_g_state_key = COSName.get_pdf_name("ExtGState")
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        egs = (
            page.get_cos_object()
            .get_dictionary_object(resources_key)
            .get_dictionary_object(ext_g_state_key)
        )
        for key in list(egs.key_set()):
            gs = egs.get_dictionary_object(key)
            smask = gs.get_dictionary_object(smask_key)
            if smask is not None:
                smask.remove_item(tr_key)
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: ignoring the inverting /TR passes the MAD gate "
        "against the oracle's true transfer-applied render"
    )
