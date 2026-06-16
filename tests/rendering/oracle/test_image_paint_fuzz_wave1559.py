"""Differential fuzz of the RENDER-TIME image-XObject painting path against
the live Apache PDFBox 3.0.7 oracle (wave 1559).

Surface: ``PageDrawer.drawImage`` — the pixels a ``Do`` of a
:class:`PDImageXObject` actually puts on the raster. Distinct from wave 1546
(which fuzzed the PDImageXObject *model* accessors); here we render and compare
painted regions. The edge attributes fuzzed, each over a white backdrop so the
painted region is isolatable:

* **/ImageMask stencil filled with the current non-stroking colour**
  (§8.9.5.4) — a 1-bpc matte painted in red / cyan; default ``/Decode [0 1]``
  and inverted ``/Decode [1 0]`` polarities; varied stencil shapes (half,
  quadrant, ring) and varied draw scales.
* **color-key /Mask** (§8.9.6.4) — a value-range that keys out a band of the
  raster, leaving a sub-region painted; the keyed band must NOT paint.
* **/SMask soft mask** (§11.6.5.3) — an alpha gradient and an alpha step so a
  partially-transparent region blends and a fully-transparent region drops.
* **/Decode inversion on a colour image** (§8.9.5.2) — ``[1 0 1 0 1 0]`` on a
  DeviceRGB raster renders the per-component complement; an un-inverted render
  shifts the colour sample far past tolerance.
* **1-bit vs 8-bit DeviceGray** (§8.9.5.2) — same visual content at two bit
  depths must paint the same region / colour.
* **/Interpolate true vs false** (§8.9.5.3) — upscaled low-res raster, both
  smoothing settings; the painted region / colour identity is invariant to the
  kernel even though the per-pixel AA differs.

Pixel-EXACT parity is impossible (Java2D vs Pillow AA / sampling — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the COARSE
painted-region facts emitted by ``oracle/probes/ImagePaintFuzzProbe.java``:

* exact rendered dimensions (a mismatch is a real bug, never AA);
* the non-white pixel-count bucket (count*16/total, 0..16) within ±1 — pins
  *how much* paints, so a masked region that wrongly paints (or a painted one
  that wrongly masks) moves the bucket;
* the painted bbox in 16ths of the page, each edge within ±1 cell — pins
  *where* it paints, so a mis-positioned / mis-polarised mask is caught;
* a quantised average colour of the painted pixels (6 levels/channel) within
  ±1 level — pins the gross colour identity, so an un-inverted /Decode image or
  a stencil filled with the wrong colour is unmistakable while AA edge blending
  is absorbed.

Wave 1559 found + fixed: ``PDFRenderer._paint_stencil_mask`` ignored the image
XObject's ``/Interpolate`` flag and always bicubic-resampled the 1-bit matte,
blurring the stencil edge on an upscale. It now threads the flag exactly like
the colour-image path (``test_stencil_no_interpolate_keeps_hard_edge`` pins the
corrected behaviour).

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
``LosslessFactory`` + content-stream API (no committed binaries).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.graphics.image.lossless_factory import LosslessFactory
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_MB = 200  # media-box side, pt
_IMG = 32  # default source image side, px

# Coarse-fact gates. Dims are exact. The bucket / bbox / colour gates are sized
# above the AA + quantisation ceiling (a 1-level colour drift and a 1-cell bbox
# drift are both routine, observed on the stencil-edge probe) yet well below
# any masking / polarity / decode bug (which moves the bucket by several units,
# the bbox by half the page, or the colour sample by 2+ levels).
_BUCKET_TOL = 1
_BBOX_TOL = 1
_COLOR_TOL = 51  # one quantisation level per channel


# --------------------------------------------------------------------------- #
# Coarse painted-region fingerprint — identical math to ImagePaintFuzzProbe.   #
# --------------------------------------------------------------------------- #
def _quantize(v: int) -> int:
    level = round(v / 255 * 5)
    level = max(0, min(5, level))
    return level * 51


def _facts(img: Image.Image) -> tuple[int, ...]:
    """``(w, h, bucket, bx0, by0, bx1, by1, qr, qg, qb)`` — mirror of the
    Java probe's coarse painted-region facts."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    count = 0
    sr = sg = sb = 0
    min_x = w
    min_y = h
    max_x = -1
    max_y = -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            luma = round(0.299 * r + 0.587 * g + 0.114 * b)
            if luma < 250:
                count += 1
                sr += r
                sg += g
                sb += b
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    total = w * h
    bucket = count * 16 // total if total else 0
    if count == 0:
        return (w, h, bucket, -1, -1, -1, -1, 255, 255, 255)
    bx0 = min_x * 16 // w
    by0 = min_y * 16 // h
    bx1 = (max_x * 16 + w - 1) // w
    by1 = (max_y * 16 + h - 1) // h
    return (
        w,
        h,
        bucket,
        bx0,
        by0,
        bx1,
        by1,
        _quantize(sr // count),
        _quantize(sg // count),
        _quantize(sb // count),
    )


def _oracle_facts(fixture: Path) -> tuple[int, ...]:
    line = run_probe_text("ImagePaintFuzzProbe", str(fixture), "0").strip()
    return tuple(int(v) for v in line.split())


def _assert_facts_match(label: str, java: tuple[int, ...], py: tuple[int, ...]) -> None:
    jw, jh, jbucket, jbx0, jby0, jbx1, jby1, jqr, jqg, jqb = java
    pw, ph, pbucket, pbx0, pby0, pbx1, pby1, pqr, pqg, pqb = py
    assert (pw, ph) == (jw, jh), (
        f"{label}: rendered dims {pw}x{ph} != PDFBox {jw}x{jh}"
    )
    assert abs(pbucket - jbucket) <= _BUCKET_TOL, (
        f"{label}: non-white bucket {pbucket} vs PDFBox {jbucket} "
        f"(>±{_BUCKET_TOL}) — wrong amount painted (mask mis-applied)"
    )
    for axis, (pv, jv) in enumerate(
        zip((pbx0, pby0, pbx1, pby1), (jbx0, jby0, jbx1, jby1), strict=True)
    ):
        assert abs(pv - jv) <= _BBOX_TOL, (
            f"{label}: painted bbox edge[{axis}] {pv} vs PDFBox {jv} "
            f"(>±{_BBOX_TOL} cells) — painted region mis-positioned"
        )
    for chan, (pv, jv) in enumerate(
        zip((pqr, pqg, pqb), (jqr, jqg, jqb), strict=True)
    ):
        assert abs(pv - jv) <= _COLOR_TOL, (
            f"{label}: painted colour chan[{chan}] {pv} vs PDFBox {jv} "
            f"(>±{_COLOR_TOL}) — wrong colour painted (decode / fill / mask bug)"
        )


# --------------------------------------------------------------------------- #
# Fixture builders.                                                            #
# --------------------------------------------------------------------------- #
def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _stencil(side: int, predicate) -> Image.Image:
    """A 1-bit stencil where ``predicate(x, y)`` decides the sample (0/1)."""
    img = Image.new("1", (side, side), 0)
    px = img.load()
    for x in range(side):
        for y in range(side):
            px[x, y] = 1 if predicate(x, y) else 0
    return img


def _build_stencil(
    path: Path,
    predicate,
    fill: tuple[float, float, float],
    *,
    decode: list[float] | None = None,
    interpolate: bool = False,
    box: tuple[float, float, float, float] = (40, 40, 120, 120),
    side: int = 16,
) -> None:
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, _stencil(side, predicate))
    image.set_image_mask(True)
    if decode is not None:
        image.set_decode(decode)
    if interpolate:
        image.set_interpolate(True)
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(*fill)
    cs.draw_image(image, *box)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_color_key(
    path: Path,
    *,
    keyed_band: tuple[tuple[int, int, int], tuple[int, int, int]],
    ranges: list[int],
) -> None:
    """RGB image: top half = a colour inside the key range (masked out),
    bottom half = a colour outside it (painted). Over a white backdrop the
    keyed band leaves no marks, so only the bottom half shows."""
    keyed, kept = keyed_band
    base = Image.new("RGB", (_IMG, _IMG), kept)
    px = base.load()
    for x in range(_IMG):
        for y in range(_IMG // 2):
            px[x, y] = keyed
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    image.set_color_key_mask(ranges)
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 40, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_smask(path: Path, mode: str) -> None:
    """RGB image (solid dark red) + an /SMask alpha plane. ``mode`` ==
    ``gradient`` fades left→right; ``step`` is opaque-right / transparent-left.
    The transparent region drops out (white backdrop shows)."""
    base = Image.new("RGB", (_IMG, _IMG), (200, 20, 20))
    alpha = Image.new("L", (_IMG, _IMG))
    apx = alpha.load()
    for x in range(_IMG):
        if mode == "gradient":
            col = round(x * 255 / (_IMG - 1))
        elif x >= _IMG // 2:  # step
            col = 255
        else:
            col = 0
        for y in range(_IMG):
            apx[x, y] = col
    rgba = base.convert("RGBA")
    rgba.putalpha(alpha)
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, rgba)
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 40, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_decode_invert(path: Path, color: tuple[int, int, int]) -> None:
    """Solid DeviceRGB image with /Decode [1 0 1 0 1 0]; renders complement."""
    base = Image.new("RGB", (_IMG, _IMG), color)
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    image.set_decode([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 40, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_gray_bitdepth(path: Path, *, one_bit: bool) -> None:
    """Half-black/half-white DeviceGray image at 1-bpc or 8-bpc. Same
    visual content; the painted (black) region must match across depths."""
    if one_bit:
        base = Image.new("1", (_IMG, _IMG), 1)
        px = base.load()
        for x in range(_IMG // 2):
            for y in range(_IMG):
                px[x, y] = 0
    else:
        base = Image.new("L", (_IMG, _IMG), 255)
        px = base.load()
        for x in range(_IMG // 2):
            for y in range(_IMG):
                px[x, y] = 0
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 40, 40, 120, 120)
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_interpolate_checker(path: Path, *, interpolate: bool) -> None:
    """A tiny 4x4 black/white checkerboard upscaled into a large box, with
    /Interpolate on/off. The painted region / colour identity is invariant
    to the kernel."""
    base = Image.new("L", (4, 4), 255)
    px = base.load()
    for x in range(4):
        for y in range(4):
            px[x, y] = 0 if (x + y) % 2 == 0 else 255
    doc, page = _new_doc_page()
    image = LosslessFactory.create_from_image(doc, base)
    if interpolate:
        image.set_interpolate(True)
    cs = PDPageContentStream(doc, page)
    cs.draw_image(image, 30, 30, 140, 140)
    cs.close()
    doc.save(str(path))
    doc.close()


_RED = (0.9, 0.1, 0.1)
_CYAN = (0.1, 0.8, 0.8)
_BLUE = (0.1, 0.1, 0.9)


def _left(x: int, y: int) -> bool:
    return x < 8


def _right(x: int, y: int) -> bool:
    return x >= 8


def _quadrant(x: int, y: int) -> bool:
    return x < 8 and y < 8


def _ring(x: int, y: int) -> bool:
    cx = cy = 7.5
    d2 = (x - cx) ** 2 + (y - cy) ** 2
    return 9 <= d2 <= 49


# Each entry builds one fuzz fixture page.
_BUILDERS: dict[str, object] = {
    # --- /ImageMask stencils painted with the fill colour --- #
    # default /Decode [0 1]: sample 0 paints. predicate==True => sample 1.
    "stencil_left_red": lambda p: _build_stencil(p, _right, _RED),
    "stencil_right_cyan": lambda p: _build_stencil(p, _left, _CYAN),
    "stencil_quadrant_blue": lambda p: _build_stencil(p, _ring, _BLUE),
    "stencil_ring_red": lambda p: _build_stencil(p, _quadrant, _RED),
    # inverted /Decode [1 0]: sample 1 paints.
    "stencil_left_red_inv": lambda p: _build_stencil(
        p, _right, _RED, decode=[1.0, 0.0]
    ),
    "stencil_quadrant_cyan_inv": lambda p: _build_stencil(
        p, _quadrant, _CYAN, decode=[1.0, 0.0]
    ),
    # interpolate true (smooth) on a stencil — region / colour invariant.
    "stencil_left_red_interp": lambda p: _build_stencil(
        p, _right, _RED, interpolate=True
    ),
    # small + large draw boxes.
    "stencil_small_box": lambda p: _build_stencil(
        p, _right, _BLUE, box=(70, 70, 60, 60)
    ),
    "stencil_large_box": lambda p: _build_stencil(
        p, _right, _RED, box=(10, 10, 180, 180)
    ),
    # --- color-key /Mask --- #
    # near-white keyed (top half white-ish, masked); bottom green painted.
    "colorkey_white_band": lambda p: _build_color_key(
        p,
        keyed_band=((250, 250, 250), (30, 180, 60)),
        ranges=[230, 255, 230, 255, 230, 255],
    ),
    # mid-magenta keyed; bottom blue painted.
    "colorkey_magenta_band": lambda p: _build_color_key(
        p,
        keyed_band=((180, 40, 160), (30, 30, 200)),
        ranges=[160, 200, 20, 60, 140, 180],
    ),
    # key range that matches NOTHING — whole image paints (both halves).
    "colorkey_no_match": lambda p: _build_color_key(
        p,
        keyed_band=((10, 10, 10), (200, 30, 30)),
        ranges=[250, 255, 250, 255, 250, 255],
    ),
    # --- /SMask soft mask --- #
    "smask_gradient": lambda p: _build_smask(p, "gradient"),
    "smask_step": lambda p: _build_smask(p, "step"),
    # --- /Decode inversion on a colour image --- #
    "decode_invert_blue": lambda p: _build_decode_invert(p, (40, 40, 200)),
    "decode_invert_red": lambda p: _build_decode_invert(p, (200, 40, 40)),
    "decode_invert_gray": lambda p: _build_decode_invert(p, (60, 60, 60)),
    # --- 1-bit vs 8-bit DeviceGray --- #
    "gray_1bit_half": lambda p: _build_gray_bitdepth(p, one_bit=True),
    "gray_8bit_half": lambda p: _build_gray_bitdepth(p, one_bit=False),
    # --- /Interpolate on a tiny upscaled checkerboard --- #
    "interp_checker_false": lambda p: _build_interpolate_checker(
        p, interpolate=False
    ),
    "interp_checker_true": lambda p: _build_interpolate_checker(
        p, interpolate=True
    ),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_image_paint_fuzz_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each fuzz fixture's painted-region facts must match Java PDFBox 3.0.7
    within the coarse gate (exact dims; bucket / bbox / colour within
    tolerance that absorbs AA + quantisation drift but not a masking,
    polarity, decode, or fill-colour bug)."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)  # type: ignore[operator]

    java = _oracle_facts(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py = _facts(img)
    _assert_facts_match(label, java, py)


@requires_oracle
def test_stencil_default_polarity_paints_unset_samples(tmp_path: Path) -> None:
    """Direct proof of /ImageMask default /Decode [0 1] polarity: predicate
    ``_right`` makes the RIGHT half sample==1, so the LEFT half (sample 0)
    paints in the fill colour while the right half is transparent. Both
    pypdfbox and PDFBox must place the painted bbox in the left half."""
    fixture = tmp_path / "stencil_polarity.pdf"
    _build_stencil(fixture, _right, _RED)
    java = _oracle_facts(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py = _facts(img)
    # bbox right-edge (index 5) stays left of page centre (cell 8).
    assert py[5] <= 9 and java[5] <= 9, (
        f"default-polarity stencil painted into right half: py={py} java={java}"
    )
    _assert_facts_match("stencil_polarity", java, py)


@requires_oracle
def test_decode_invert_actually_inverts(tmp_path: Path) -> None:
    """Direct proof /Decode [1 0 1 0 1 0] inverts: a near-black source
    (60,60,60) must render near-white (complement) — i.e. the painted-pixel
    colour sample is HIGH, not low. A renderer that ignored /Decode would
    paint the near-black source and the luma would stay below the 250
    'non-white' threshold across most pixels (a much larger bucket)."""
    fixture = tmp_path / "decode_invert.pdf"
    _build_decode_invert(fixture, (60, 60, 60))
    java = _oracle_facts(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    # Sample the centre of the painted box (40..160pt @72dpi).
    centre = img.getpixel((100, 100))
    assert all(c >= 150 for c in centre), (
        f"decode-invert centre {centre} not light — /Decode not applied"
    )
    _assert_facts_match("decode_invert", java, _facts(img))


@requires_oracle
def test_stencil_no_interpolate_keeps_hard_edge(tmp_path: Path) -> None:
    """Wave 1559 fix proof: a /ImageMask stencil with /Interpolate FALSE
    (the default) must be resampled nearest-neighbour, keeping the matte's
    edge hard. Before the fix ``_paint_stencil_mask`` always passed
    ``interpolate=True`` (bicubic), blurring the 4x4-upscaled edge — the
    blurred fringe pixels lifted the non-white bucket and softened the bbox
    past the gate against PDFBox's nearest-neighbour stencil paint."""
    fixture = tmp_path / "stencil_hard_edge.pdf"
    # Tiny 4x4 stencil upscaled into a big box so the kernel choice bites.
    _build_stencil(
        fixture,
        lambda x, y: x >= 2,
        _RED,
        box=(20, 20, 160, 160),
        side=4,
        interpolate=False,
    )
    java = _oracle_facts(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py = _facts(img)
    _assert_facts_match("stencil_hard_edge", java, py)
