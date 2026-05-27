"""Live PDFBox differential parity for **ICCBased-colour-space image
XObjects** rendered as rasters.

PDF §8.6.5.5 lets an image XObject's ``/ColorSpace`` be ``[/ICCBased
<stream N>]`` where the stream body carries an embedded ICC profile and
``/N`` ∈ {1, 3, 4} gives the component count. The raster samples must be
converted *through the embedded profile* to sRGB for display — both
PDFBox (Java2D / AWT's ``ICC_ColorSpace``) and pypdfbox (Pillow's
``ImageCms`` / LittleCMS2) bottom out in LittleCMS, so a profile that
both CMMs can parse renders near-identically.

Cases (each a tiny one-page PDF, 8 bpc, authored via pypdfbox):

* **rgb_srgb** — ``/N 3`` over a real embedded **sRGB** profile (Pillow's
  ``ImageCms.createProfile('sRGB')`` → bytes). A left→right grayscale-ish
  ramp. sRGB→sRGB is the identity-ish round-trip, so this is near-exact.
  A degenerate misread (profile ignored / wrong N / raw samples shown)
  would not be near-exact, but more importantly would shift the ramp.
* **gray** — ``/N 1`` over a minimal valid monochrome (``GRAY``-signature,
  gamma-2.2 ``kTRC``) ICC profile. A left→right 0→255 ramp. Both CMMs
  parse the profile and apply the same gamma curve.
* **cmyk_fallback** — ``/N 4`` over a minimal CMYK-signature profile that
  carries *no* ``A2B0`` LUT, so neither LittleCMS nor AWT can build a
  CMYK→RGB transform from it; both renderers fall back to the
  ``/Alternate /DeviceCMYK`` conversion. A left→right K (black) ramp,
  C=M=Y=0. The DeviceCMYK fallback is a *documented* CMM-model divergence
  (pypdfbox's naive subtractive model vs PDFBox's CGATS001 ICC profile —
  see ``pd_device_cmyk.py`` and ``test_color_to_rgb_oracle.py``'s
  ``IccFallbackCmyk`` case), so this case uses a wider luminance
  tolerance. The gradient orientation must still match (a misread would
  reverse or scramble it).

Pixel-EXACT parity is impossible (LittleCMS rounding + Java2D vs Pillow
anti-aliasing), so we compare the same coarse fingerprint the page-render
oracle uses: exact rendered dimensions plus a 16x16 average-luminance
grid, gated against ``oracle/probes/RenderProbe.java`` at 72 DPI.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Profile-driven cases (sRGB / gray) round-trip through the same CMM as
# PDFBox, so they're near-exact. The CMYK-fallback case inherits the
# documented DeviceCMYK CMM-model divergence (subtractive vs CGATS001),
# so it gets a wider band.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_CMYK_MAD_TOLERANCE = 12.0
_CMYK_MAXDIFF_TOLERANCE = 60

_IMG = 32  # source image side, px
_MB = 200  # media-box side, pt


# --------------------------------------------------------------------------
# Minimal ICC profile authoring
# --------------------------------------------------------------------------
def _pad4(b: bytes) -> bytes:
    """Pad ``b`` up to the next 4-byte boundary with NULs (ICC tag data
    is 4-byte aligned per ICC.1:2010 §7.3.5)."""
    return b + b"\x00" * ((4 - len(b) % 4) % 4)


def _u8fixed8(x: float) -> int:
    """Encode ``x`` as an ICC ``u8Fixed8Number`` (8.8 fixed point)."""
    return int(round(x * 256)) & 0xFFFF


def _build_minimal_profile(colorspace: bytes, with_trc: bool) -> bytes:
    """Assemble a minimal-but-valid ICC v2 profile.

    ``colorspace`` is the 4-byte data-colour-space signature written to
    header offset 16 (``b"GRAY"`` / ``b"CMYK"``). ``with_trc`` adds a
    gamma-2.2 ``kTRC`` curve (needed for a monochrome profile to actually
    convert); a CMYK-signature profile is left LUT-less on purpose so the
    CMM refuses to build a transform and the renderer falls back to the
    ``/Alternate``. Carries the bare minimum required tags (``desc``,
    ``wtpt``, ``cprt``) plus ``kTRC`` when requested — enough for
    LittleCMS and AWT to parse the header without complaint.
    """
    name = b"CC0"
    desc = _pad4(b"desc" + b"\x00" * 4 + struct.pack(">I", len(name) + 1) + name + b"\x00")
    # textDescriptionType trailer: unicode lang/count + scriptcode block.
    desc += struct.pack(">I", 0) + struct.pack(">I", 0)
    desc += struct.pack(">H", 0) + b"\x00" + bytes(67)
    desc = _pad4(desc)
    # D50 white point (the ICC PCS reference illuminant).
    wtpt = b"XYZ " + b"\x00" * 4 + struct.pack(
        ">iii", int(0.9642 * 65536), 65536, int(0.8249 * 65536)
    )
    cprt = _pad4(b"text" + b"\x00" * 4 + b"CC0\x00")

    tags: list[tuple[bytes, bytes]] = [(b"desc", desc), (b"wtpt", wtpt)]
    if with_trc:
        ktrc = _pad4(
            b"curv" + b"\x00" * 4 + struct.pack(">I", 1) + struct.pack(">H", _u8fixed8(2.2))
        )
        tags.append((b"kTRC", ktrc))
    tags.append((b"cprt", cprt))

    n = len(tags)
    offset = 128 + 4 + n * 12
    body = b""
    entries = b""
    for sig, data in tags:
        entries += sig + struct.pack(">II", offset, len(data))
        body += data
        offset += len(data)
    table = struct.pack(">I", n) + entries
    total = 128 + len(table) + len(body)

    header = bytearray(128)
    struct.pack_into(">I", header, 0, total)  # profile size
    struct.pack_into(">I", header, 8, 0x02400000)  # version 2.4
    header[12:16] = b"mntr"  # device class: display
    header[16:20] = colorspace  # data colour space signature
    header[20:24] = b"XYZ "  # PCS
    header[36:40] = b"acsp"  # profile file signature
    struct.pack_into(
        ">iii", header, 68, int(0.9642 * 65536), 65536, int(0.8249 * 65536)
    )  # illuminant (D50)
    return bytes(header) + table + body


def _srgb_profile_bytes() -> bytes:
    """Real embedded sRGB profile (Pillow's built-in, always available)."""
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


# --------------------------------------------------------------------------
# PDF authoring
# --------------------------------------------------------------------------
def _make_icc_image(
    profile: bytes, n: int, raster: bytes, alternate: str | None = None
) -> PDImageXObject:
    """Assemble an ``[/ICCBased <stream N>]`` image XObject over ``raster``."""
    icc = COSStream()
    icc.set_int(COSName.get_pdf_name("N"), n)
    icc.set_raw_data(profile)
    if alternate is not None:
        icc.set_item("Alternate", COSName.get_pdf_name(alternate))
    cs = COSArray()
    cs.add(COSName.get_pdf_name("ICCBased"))
    cs.add(icc)

    stream = COSStream()
    stream.set_raw_data(bytes(raster))
    image = PDImageXObject(stream)
    image.set_width(_IMG)
    image.set_height(_IMG)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", cs)
    return image


def _save_with_image(path: Path, image: PDImageXObject) -> None:
    """Paint ``image`` into a 120x120 box over a black backdrop and save."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    content = PDPageContentStream(doc, page)
    content.set_non_stroking_color(0.0, 0.0, 0.0)
    content.add_rect(0, 0, _MB, _MB)
    content.fill()
    content.draw_image(image, 40, 60, 120, 120)
    content.close()
    doc.save(str(path))
    doc.close()


def _build_rgb_srgb(path: Path) -> None:
    """``/N 3`` over an embedded sRGB profile; left→right gray ramp."""
    samples = bytearray()
    for _y in range(_IMG):
        for x in range(_IMG):
            v = round(x * 255 / (_IMG - 1))
            samples += bytes((v, v, v))
    image = _make_icc_image(_srgb_profile_bytes(), 3, bytes(samples))
    _save_with_image(path, image)


def _build_gray(path: Path) -> None:
    """``/N 1`` over a minimal gray ICC profile; left→right 0→255 ramp."""
    samples = bytearray()
    for _y in range(_IMG):
        for x in range(_IMG):
            samples.append(round(x * 255 / (_IMG - 1)))
    profile = _build_minimal_profile(b"GRAY", with_trc=True)
    image = _make_icc_image(profile, 1, bytes(samples))
    _save_with_image(path, image)


def _build_cmyk_fallback(path: Path) -> None:
    """``/N 4`` over a LUT-less CMYK profile + ``/Alternate /DeviceCMYK``;
    left→right K (black) ramp, C=M=Y=0. The CMM cannot transform through
    the profile, so both renderers fall back to DeviceCMYK."""
    samples = bytearray()
    for _y in range(_IMG):
        for x in range(_IMG):
            k = round(x * 255 / (_IMG - 1))
            samples += bytes((0, 0, 0, k))
    profile = _build_minimal_profile(b"CMYK", with_trc=False)
    image = _make_icc_image(profile, 4, bytes(samples), alternate="DeviceCMYK")
    _save_with_image(path, image)


_BUILDERS = {
    "rgb_srgb": _build_rgb_srgb,
    "gray": _build_gray,
    "cmyk_fallback": _build_cmyk_fallback,
}

# Per-case luminance tolerances (CMYK fallback inherits the documented
# DeviceCMYK CMM divergence — see module docstring).
_TOLERANCES = {
    "rgb_srgb": (_MAD_TOLERANCE, _MAXDIFF_TOLERANCE),
    "gray": (_MAD_TOLERANCE, _MAXDIFF_TOLERANCE),
    "cmyk_fallback": (_CMYK_MAD_TOLERANCE, _CMYK_MAXDIFF_TOLERANCE),
}


# --------------------------------------------------------------------------
# Fingerprint helpers
# --------------------------------------------------------------------------
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


def _render_grid(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_icc_image_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)
    (py_w, py_h), py_grid = _render_grid(fixture)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    mad_tol, maxdiff_tol = _TOLERANCES[label]
    assert mad < mad_tol, (
        f"{label}: mean abs cell diff {mad:.2f} >= {mad_tol} "
        f"(maxdiff={maxdiff}) — ICC samples likely not converted through "
        f"the profile, wrong /N interpretation, or profile stream not read"
    )
    assert maxdiff < maxdiff_tol, (
        f"{label}: worst cell diff {maxdiff} >= {maxdiff_tol} "
        f"(mad={mad:.2f}) — a region diverges far beyond CMM rounding"
    )


@requires_oracle
def test_icc_rgb_image_is_smooth_left_to_right_ramp(tmp_path: Path) -> None:
    """Guard against a degenerate misread (profile ignored / wrong N /
    raw samples shown). The sRGB-profile RGB image must render as a
    *smooth* left→right ramp: the left third must be materially darker
    than the right third. Reversing the profile interpretation or
    mis-striding the raster (reading 3-byte pixels as a different N)
    would collapse or invert this monotonic difference."""
    fixture = tmp_path / "rgb_srgb.pdf"
    _build_rgb_srgb(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
    width, height = img.size
    px = img.load()
    left = right = 0
    n = 0
    for y in range(height):
        for x in range(width // 3):
            left += px[x, y]
            right += px[width - 1 - x, y]
            n += 1
    left_avg = left / n
    right_avg = right / n
    assert right_avg - left_avg > 40, (
        "ICCBased sRGB RGB image is not a smooth left→right ramp "
        f"(left_avg={left_avg:.1f} right_avg={right_avg:.1f}) — the "
        "embedded profile was ignored or the raster was mis-strided"
    )


@requires_oracle
def test_icc_cmyk_fallback_k_ramp_orientation(tmp_path: Path) -> None:
    """The CMYK K (black) ramp grows left→right, so with C=M=Y=0 the
    rendered luminance must *decrease* left→right (more black = darker).
    The DeviceCMYK fallback's absolute luminance diverges from PDFBox by
    a documented CMM-model amount, but the orientation is model-
    independent — a wrong-N misread (treating the 4-channel raster as
    3-channel) would scramble it."""
    fixture = tmp_path / "cmyk_fallback.pdf"
    _build_cmyk_fallback(fixture)
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("L")
    width, height = img.size
    px = img.load()
    left = right = 0
    n = 0
    for y in range(height):
        for x in range(width // 3):
            left += px[x, y]
            right += px[width - 1 - x, y]
            n += 1
    left_avg = left / n
    right_avg = right / n
    assert left_avg - right_avg > 30, (
        "ICCBased CMYK K-ramp is not darkening left→right "
        f"(left_avg={left_avg:.1f} right_avg={right_avg:.1f}) — the "
        "4-channel raster was likely mis-strided (wrong /N)"
    )
