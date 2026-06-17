"""Wave 1593 — render-side image SMask alpha + constant-alpha blit fuzz.

Hammers the draw-time alpha pipeline behind upstream
``PageDrawer.drawImage`` as ported in ``pypdfbox.rendering.pdf_renderer``:

* ``_apply_image_constant_alpha`` — the non-stroking constant alpha ``ca``
  (PDF 32000-1 §11.6.4.4) modulates image opacity. Upstream sets a
  ``setComposite(getNonStrokingAlphaConstant())`` before the image blit, so
  ``ca`` *multiplies* into the source alpha:

    - ``ca == 1.0`` is a no-op (opaque fast path; existing alpha returned
      unchanged, possibly ``None``).
    - ``ca < 1.0`` with an existing SMask/native alpha scales every sample
      by ``ca`` (``a' = round(a * ca)``) — combines, does NOT replace.
    - ``ca < 1.0`` with no native alpha synthesises a flat alpha of
      ``round(255 * ca)`` so the image paints at ``ca`` opacity.
    - ``ca == 0.0`` yields a fully transparent plane (the image is
      invisible).

* ``_paste_image`` — end-to-end with a mocked blit so we capture the alpha
  *mask* handed to ``Image.paste``. We assert: a source RGBA image whose
  alpha came from a /SMask (0 = transparent, 255 = opaque) keeps that
  orientation (not inverted); ``ca`` multiplies into it; ``ca=0`` produces
  an all-zero mask; an opaque RGB image with ``ca=1`` pastes with no mask;
  the SMask combines with (does not replace) the constant alpha.

These pin the alpha-resample + ca-multiply + blit handshake directly with a
mocked paste, independent of pixel content.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer

# ----------------------------------------------------------------- helpers


def _make_doc(width: float = 100.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _gstate_fresh():
    from pypdfbox.rendering.pdf_renderer import _GState

    return _GState()


def _renderer_with_canvas(width_px: int = 100, height_px: int = 100, scale: float = 1.0):
    """Build a PDFRenderer with a live RGB canvas and a device CTM whose
    d-component carries the user-space y-flip, exactly as the page render
    loop sets up."""
    doc, _ = _make_doc(float(width_px) / scale, float(height_px) / scale)
    rdr = PDFRenderer(doc)
    rdr._image = Image.new("RGB", (width_px, height_px), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw

    rdr._draw = aggdraw.Draw(rdr._image)
    rdr._gs_stack = [_gstate_fresh()]
    rdr._device_ctm = (scale, 0.0, 0.0, -scale, 0.0, float(height_px))
    # Place the image to cover the full page (cm = page-sized unit square).
    rdr._gs.ctm = (float(width_px), 0.0, 0.0, float(height_px), 0.0, 0.0)
    return doc, rdr


class _BlitRecorder:
    """Captures args passed to ``Image.paste`` (origin + mask) so a test
    can inspect the alpha mask handed to the blit without pixel diffing."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def install(self, rdr) -> None:
        recorder = self
        real = rdr._image

        def fake_paste(im, box=None, mask=None):  # noqa: ANN001
            recorder.calls.append({"image": im, "box": box, "mask": mask})

        real.paste = fake_paste  # type: ignore[method-assign]

    @property
    def last_mask(self):
        return self.calls[-1]["mask"] if self.calls else None


def _rgba(w: int, h: int, alpha_value: int) -> Image.Image:
    """An RGBA image with a flat alpha plane (the SMask result)."""
    return Image.merge(
        "RGBA",
        (
            Image.new("L", (w, h), 200),
            Image.new("L", (w, h), 100),
            Image.new("L", (w, h), 50),
            Image.new("L", (w, h), alpha_value),
        ),
    )


def _smask_gradient(w: int, h: int) -> Image.Image:
    """An RGBA image whose alpha is a left->right ramp (0 .. 255), so an
    inverted orientation is detectable: column 0 must be transparent (0),
    the right edge opaque (~255)."""
    alpha = Image.new("L", (w, h), 0)
    px = alpha.load()
    for x in range(w):
        v = round(255.0 * x / max(1, w - 1))
        for y in range(h):
            px[x, y] = v
    rgb = Image.new("RGB", (w, h), (10, 20, 30))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


# =================================================== _apply_image_constant_alpha

_FN = PDFRenderer._apply_image_constant_alpha


@pytest.mark.parametrize(
    "ca",
    [1.0, 1.5, 2.0],
    ids=["one", "above_one", "way_above"],
)
def test_constant_alpha_opaque_is_noop_for_none(ca) -> None:
    """``ca >= 1`` with no native alpha is the opaque fast path: ``None``
    stays ``None`` so the blit pastes without a mask."""
    assert _FN(None, ca, (8, 8)) is None


@pytest.mark.parametrize(
    "ca",
    [1.0, 1.25, 3.0],
    ids=["one", "above_one", "way_above"],
)
def test_constant_alpha_opaque_returns_existing_alpha_unchanged(ca) -> None:
    """``ca >= 1`` returns the *same* alpha object — no needless copy, and
    the SMask alpha is untouched."""
    a = Image.new("L", (8, 8), 200)
    assert _FN(a, ca, (8, 8)) is a


@pytest.mark.parametrize(
    ("ca", "expected"),
    [
        (0.0, 0),
        (0.25, 64),
        (0.5, 128),
        (0.75, 191),
    ],
    ids=["zero", "quarter", "half", "three_quarter"],
)
def test_constant_alpha_no_native_alpha_synthesises_flat_plane(ca, expected) -> None:
    """``ca < 1`` with no native alpha makes a flat ``round(255*ca)`` plane
    so the otherwise-opaque image paints at ``ca`` opacity."""
    out = _FN(None, ca, (6, 4))
    assert out is not None
    assert out.mode == "L"
    assert out.size == (6, 4)
    assert out.getpixel((0, 0)) == expected
    assert out.getpixel((5, 3)) == expected


def test_constant_alpha_zero_no_native_alpha_is_fully_transparent() -> None:
    """``ca == 0`` -> every pixel of the synthesised plane is 0 (invisible
    image)."""
    out = _FN(None, 0.0, (5, 5))
    assert out is not None
    assert out.getextrema() == (0, 0)


@pytest.mark.parametrize(
    ("native", "ca", "expected"),
    [
        (255, 0.5, 128),
        (200, 0.5, 100),
        (255, 0.25, 64),
        (128, 0.5, 64),
        (255, 0.0, 0),
        (100, 0.0, 0),
    ],
    ids=["full_half", "200_half", "full_quarter", "mid_half", "full_zero", "mid_zero"],
)
def test_constant_alpha_multiplies_into_existing_smask(native, ca, expected) -> None:
    """``ca < 1`` with an existing SMask alpha SCALES it (combine, not
    replace): ``a' = round(a * ca)``. This is the key parity point — the
    SMask must not be clobbered by ``ca`` nor ``ca`` ignored."""
    a = Image.new("L", (8, 8), native)
    out = _FN(a, ca, (8, 8))
    assert out is not None
    assert out.getpixel((0, 0)) == expected


def test_constant_alpha_preserves_smask_gradient_shape() -> None:
    """A graded SMask scaled by ``ca`` keeps its relative shape: the dark
    end stays darker, the bright end stays brighter (no inversion)."""
    alpha = Image.new("L", (16, 1), 0)
    px = alpha.load()
    for x in range(16):
        px[x, 0] = x * 17
    out = _FN(alpha, 0.5, (16, 1))
    assert out is not None
    lo = out.getpixel((0, 0))
    hi = out.getpixel((15, 0))
    assert lo < hi
    assert lo == 0
    assert hi == round(15 * 17 * 0.5)


@pytest.mark.parametrize(
    "ca",
    [-0.5, -1.0, -100.0],
    ids=["small_neg", "neg_one", "big_neg"],
)
def test_constant_alpha_negative_clamped_to_zero(ca) -> None:
    """Out-of-range negative ``ca`` clamps to 0 (fully transparent)."""
    out = _FN(None, ca, (4, 4))
    assert out is not None
    assert out.getextrema() == (0, 0)


def test_constant_alpha_size_param_used_only_when_synthesising() -> None:
    """The ``size`` arg sizes the synthesised plane; with an existing alpha
    the plane keeps the alpha's own size, not ``size``."""
    a = Image.new("L", (3, 7), 200)
    out = _FN(a, 0.5, (99, 99))
    assert out is not None
    assert out.size == (3, 7)


# =========================================================== _paste_image e2e


def test_paste_opaque_rgb_ca_one_no_mask() -> None:
    """An opaque RGB image with ``ca=1`` pastes with no alpha mask (fast
    path) — nothing modulates opacity."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(Image.new("RGB", (8, 8), (255, 0, 0)))
        assert rec.calls
        assert rec.last_mask is None
    finally:
        doc.close()


def test_paste_opaque_rgb_ca_half_pastes_flat_half_mask() -> None:
    """An opaque RGB image with ``ca=0.5`` gains a flat ~128 alpha mask so
    it composites at half opacity (the bug fix: ``ca`` modulates images)."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.fill_alpha = 0.5
        rdr._paste_image(Image.new("RGB", (8, 8), (255, 0, 0)))
        mask = rec.last_mask
        assert mask is not None
        assert mask.mode == "L"
        lo, hi = mask.getextrema()
        assert lo == hi == 128
    finally:
        doc.close()


def test_paste_opaque_rgb_ca_zero_invisible() -> None:
    """``ca=0`` -> all-zero alpha mask: the image contributes nothing."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.fill_alpha = 0.0
        rdr._paste_image(Image.new("RGB", (8, 8), (255, 0, 0)))
        mask = rec.last_mask
        assert mask is not None
        assert mask.getextrema() == (0, 0)
    finally:
        doc.close()


def test_paste_smask_alpha_orientation_not_inverted() -> None:
    """A source RGBA image whose alpha is 0=transparent/255=opaque keeps
    that orientation through the resample + blit (column 0 stays
    transparent, right edge stays opaque)."""
    doc, rdr = _renderer_with_canvas(40, 40)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(_smask_gradient(16, 16))
        mask = rec.last_mask
        assert mask is not None
        w, h = mask.size
        left = mask.getpixel((0, h // 2))
        right = mask.getpixel((w - 1, h // 2))
        assert left < right
        assert left <= 10  # near-transparent left edge
        assert right >= 230  # near-opaque right edge
    finally:
        doc.close()


def test_paste_smask_resampled_to_target_size() -> None:
    """When the image is scaled into a larger device box, its SMask alpha
    is resampled to the *target* size, not left at the source size."""
    doc, rdr = _renderer_with_canvas(40, 40)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        # cm covers the full 40x40 page; source raster is 8x8 -> upscaled.
        rdr._gs.ctm = (40.0, 0.0, 0.0, 40.0, 0.0, 0.0)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(_rgba(8, 8, 180))
        mask = rec.last_mask
        assert mask is not None
        assert mask.size == (40, 40)
    finally:
        doc.close()


@pytest.mark.parametrize(
    ("native", "ca", "expected"),
    [
        (200, 0.5, 100),
        (255, 0.5, 128),
        (100, 0.25, 25),
        (255, 0.0, 0),
    ],
    ids=["200_half", "255_half", "100_quarter", "255_zero"],
)
def test_paste_smask_combined_with_constant_alpha(native, ca, expected) -> None:
    """The SMask alpha and ``ca`` combine multiplicatively at the blit:
    a flat-``native`` SMask with ``ca`` yields a mask of ``native*ca``."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.ctm = (8.0, 0.0, 0.0, 8.0, 0.0, 0.0)
        rdr._gs.fill_alpha = ca
        rdr._paste_image(_rgba(8, 8, native))
        mask = rec.last_mask
        assert mask is not None
        lo, hi = mask.getextrema()
        # Flat native alpha resampled to a flat target stays flat.
        assert lo == hi == expected
    finally:
        doc.close()


def test_paste_smask_zero_value_is_transparent_pixel() -> None:
    """A 0 SMask value means a transparent pixel (255 = opaque): a
    fully-zero alpha source pastes an all-zero mask (nothing drawn)."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.ctm = (8.0, 0.0, 0.0, 8.0, 0.0, 0.0)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(_rgba(8, 8, 0))
        mask = rec.last_mask
        assert mask is not None
        assert mask.getextrema() == (0, 0)
    finally:
        doc.close()


def test_paste_smask_full_value_is_opaque_pixel() -> None:
    """A 255 SMask value = fully opaque: a flat-255 alpha source pastes an
    all-255 mask (image fully drawn) with ``ca=1``."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.ctm = (8.0, 0.0, 0.0, 8.0, 0.0, 0.0)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(_rgba(8, 8, 255))
        mask = rec.last_mask
        assert mask is not None
        assert mask.getextrema() == (255, 255)
    finally:
        doc.close()


def test_paste_no_smask_ca_one_fully_opaque_no_mask() -> None:
    """No SMask + ``ca=1`` => fully opaque, no mask handed to the blit."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.ctm = (8.0, 0.0, 0.0, 8.0, 0.0, 0.0)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(Image.new("L", (8, 8), 120).convert("RGB"))
        assert rec.last_mask is None
    finally:
        doc.close()


def test_paste_smask_ca_one_passes_smask_through_unchanged() -> None:
    """With ``ca=1`` the SMask alpha is passed to the blit unmodified (the
    opaque fast path returns the same alpha object)."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.ctm = (8.0, 0.0, 0.0, 8.0, 0.0, 0.0)
        rdr._gs.fill_alpha = 1.0
        rdr._paste_image(_rgba(8, 8, 90))
        mask = rec.last_mask
        assert mask is not None
        assert mask.getextrema() == (90, 90)
    finally:
        doc.close()


def test_paste_clip_path_combines_smask_and_constant_alpha() -> None:
    """When a clip mask is active, the bbox + clip + SMask*ca all multiply
    into the composite mask. We assert the paste happens (mask present)."""
    doc, rdr = _renderer_with_canvas(20, 20)
    try:
        rec = _BlitRecorder()
        rec.install(rdr)
        rdr._gs.clip_mask = Image.new("L", (20, 20), 255)
        rdr._gs.ctm = (8.0, 0.0, 0.0, 8.0, 0.0, 0.0)
        rdr._gs.fill_alpha = 0.5
        rdr._paste_image(_rgba(8, 8, 200))
        mask = rec.last_mask
        assert mask is not None
        assert mask.size == rdr._image.size
        # Inside the bbox the combined alpha is ~ 200*0.5 = 100.
        assert mask.getextrema()[1] > 0
    finally:
        doc.close()
