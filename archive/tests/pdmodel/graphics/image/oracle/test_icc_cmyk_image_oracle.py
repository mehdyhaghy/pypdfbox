"""Live PDFBox differential parity for an **ICCBased N=4 CMYK image
XObject carrying a VALID (LUT-bearing) CMYK ICC profile**.

PDF §8.6.5.5 lets an image XObject's ``/ColorSpace`` be ``[/ICCBased
<stream /N 4>]`` where the stream body holds an embedded CMYK ICC profile.
When the profile carries a real ``A2B0`` lookup table, *both* CMMs — Java
AWT's ``ICC_ColorSpace`` and Pillow's ``ImageCms`` / LittleCMS2 — can
build a genuine CMYK→RGB transform, so the conversion runs *through the
profile* (not the ``/Alternate`` fallback).

This is the surface left UNCOVERED by the sibling oracles:

* ``test_icc_image_render_oracle.py`` covers N=3 sRGB, N=1 GRAY, and an
  N=4 *LUT-less* CMYK profile that **forces** the ``/Alternate
  /DeviceCMYK`` fallback (a documented subtractive-vs-CGATS001 model
  gap).
* ``test_icc_alternate_fallback_oracle.py`` covers N=3 / N=1 *totally
  unparseable* profiles that fall back to ``/Alternate``.

Here the profile is valid and LUT-bearing, so the ICC CMM path itself is
exercised — the very thing the other two files deliberately avoid. We
drive the actual ``PDImageXObject.getImage()`` surface (which routes an
ICCBased image through ``PDICCBased.toRGBImage(raster)``) on both sides
and assert:

* ``getNumberOfComponents() == 4`` and ``getInitialColor()`` is the
  all-zero CMYK init colour (4 components, each 0.0);
* ``/Alternate`` resolves to ``DeviceCMYK``;
* the rendered RGB raster matches PDFBox within a TOLERANT MAD/MAXDIFF
  gate on a downsampled grid — CMYK→RGB CMM output differs slightly
  between Java's CMM and LittleCMS2, so this is the same documented-
  divergence tier as the existing CMYK cases, not a byte-exact gate.

Both sides consume **byte-identical** profile + raster bytes (the probe
reads them from files this test writes), so any divergence is a genuine
CMM / pipeline difference, not an input mismatch.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 8  # downsample grid side (cells per axis)
_IMG = 16  # source image side, px
# CMYK→RGB CMM output differs slightly between Java's CMM and LittleCMS2
# even for a byte-identical profile + LUT; this is the documented CMYK
# divergence tier, so the gate is tolerant (perceptual match, not exact).
_MAD_TOLERANCE = 8.0
_MAXDIFF_TOLERANCE = 24


# --------------------------------------------------------------------------
# Minimal but VALID CMYK ICC profile (with an A2B0 lut16Type LUT)
# --------------------------------------------------------------------------
def _pad4(b: bytes) -> bytes:
    """Pad ``b`` up to the next 4-byte boundary (ICC tag data is 4-byte
    aligned per ICC.1:2010 §7.3.5)."""
    return b + b"\x00" * ((4 - len(b) % 4) % 4)


def _build_cmyk_profile() -> bytes:
    """Assemble a minimal-but-VALID CMYK ICC v2 profile carrying a real
    ``A2B0`` ``lut16Type`` (``mft2``) table.

    The ``A2B0`` tag is what lets a CMM build a CMYK→PCS transform; with
    it present both Java AWT and LittleCMS2 convert *through the profile*
    rather than falling back to ``/Alternate``. The LUT is a 2-node-per-
    axis (2^4 = 16-node) CLUT computed from a naive subtractive CMYK model
    mapped to PCS XYZ (D50) — enough for both CMMs to interpolate a smooth
    CMYK→RGB conversion. Carries the bare-minimum required tags (``desc``,
    ``wtpt``, ``cprt``) plus the ``A2B0`` LUT.
    """
    name = b"CMYKtest"
    desc = b"desc" + b"\x00" * 4 + struct.pack(">I", len(name) + 1) + name + b"\x00"
    desc += struct.pack(">I", 0) + struct.pack(">I", 0)
    desc += struct.pack(">H", 0) + b"\x00" + bytes(67)
    desc = _pad4(desc)
    wtpt = b"XYZ " + b"\x00" * 4 + struct.pack(
        ">iii", int(0.9642 * 65536), 65536, int(0.8249 * 65536)
    )
    cprt = _pad4(b"text" + b"\x00" * 4 + b"CC0\x00")

    in_ch, out_ch, grid = 4, 3, 2
    a2b = b"mft2" + b"\x00" * 4 + bytes([in_ch, out_ch, grid, 0])
    # e-matrix: identity (only consulted for XYZ-input profiles; harmless).
    for m in (65536, 0, 0, 0, 65536, 0, 0, 0, 65536):
        a2b += struct.pack(">i", m)
    a2b += struct.pack(">H", 2) + struct.pack(">H", 2)  # in/out table entries
    # Input tables: identity ramp 0→65535, one pair per input channel.
    for _ in range(in_ch):
        a2b += struct.pack(">HH", 0, 65535)
    # CLUT: grid^in_ch nodes, each out_ch uint16, CMYK→XYZ via naive model.
    for c in range(grid):
        for m in range(grid):
            for y in range(grid):
                for k in range(grid):
                    r = (1 - c) * (1 - k)
                    g = (1 - m) * (1 - k)
                    b = (1 - y) * (1 - k)
                    x_pcs = 0.4124 * r + 0.3576 * g + 0.1805 * b
                    y_pcs = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    z_pcs = 0.0193 * r + 0.1192 * g + 0.9505 * b

                    def enc(v: float) -> int:
                        return max(0, min(65535, int(round(v * 65535))))

                    a2b += struct.pack(">HHH", enc(x_pcs), enc(y_pcs), enc(z_pcs))
    # Output tables: identity ramp, one pair per output channel.
    for _ in range(out_ch):
        a2b += struct.pack(">HH", 0, 65535)
    a2b = _pad4(a2b)

    tags = [(b"desc", desc), (b"wtpt", wtpt), (b"A2B0", a2b), (b"cprt", cprt)]
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
    header[12:16] = b"prtr"  # output device class (carries A2B0)
    header[16:20] = b"CMYK"  # data colour space signature
    header[20:24] = b"XYZ "  # PCS
    header[36:40] = b"acsp"  # profile file signature
    struct.pack_into(
        ">iii", header, 68, int(0.9642 * 65536), 65536, int(0.8249 * 65536)
    )  # illuminant (D50)
    return bytes(header) + table + body


def _build_cmyk_raster() -> bytes:
    """An ``_IMG x _IMG`` 8-bpc CMYK raster: a left→right K (black) ramp
    with C=M=Y=0. The K ramp gives a monotone luminance gradient the CMM
    must darken left→right; C=M=Y=0 keeps the chroma channels out of it so
    the gate isolates the K→RGB conversion."""
    samples = bytearray()
    for _y in range(_IMG):
        for x in range(_IMG):
            k = round(x * 255 / (_IMG - 1))
            samples += bytes((0, 0, 0, k))
    return bytes(samples)


# --------------------------------------------------------------------------
# pypdfbox image authoring
# --------------------------------------------------------------------------
def _make_icc_cmyk_image(profile: bytes, raster: bytes) -> PDImageXObject:
    """Assemble an ``[/ICCBased <stream /N 4 /Alternate /DeviceCMYK>]``
    image XObject over the raw CMYK ``raster``."""
    icc = COSStream()
    icc.set_int(COSName.get_pdf_name("N"), 4)
    icc.set_item("Alternate", COSName.get_pdf_name("DeviceCMYK"))
    icc.set_raw_data(profile)
    cs = COSArray()
    cs.add(COSName.get_pdf_name("ICCBased"))
    cs.add(icc)

    stream = COSStream()
    stream.set_raw_data(raster)
    image = PDImageXObject(stream)
    image.set_width(_IMG)
    image.set_height(_IMG)
    image.set_bits_per_component(8)
    stream.set_item("ColorSpace", cs)
    return image


# --------------------------------------------------------------------------
# Fingerprint helpers
# --------------------------------------------------------------------------
def _rgb_grid(image: PDImageXObject) -> list[int]:
    """``_GRID x _GRID`` row-major downsampled RGB grid (cell averages),
    identical cell mapping to ``IccCmykImageProbe.java`` (integer-division
    of pixel coord over image size, clamped to the last cell)."""
    pil = image.get_image()
    assert pil is not None, "ICCBased N=4 image decoded to None"
    rgb = pil.convert("RGB")
    width, height = rgb.size
    px = rgb.load()
    acc_r = [0] * (_GRID * _GRID)
    acc_g = [0] * (_GRID * _GRID)
    acc_b = [0] * (_GRID * _GRID)
    cnt = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            i = cy * _GRID + cx
            r, g, b = px[x, y][:3]
            acc_r[i] += r
            acc_g[i] += g
            acc_b[i] += b
            cnt[i] += 1
    grid: list[int] = []
    for i in range(_GRID * _GRID):
        c = cnt[i] or 1
        grid += [round(acc_r[i] / c), round(acc_g[i] / c), round(acc_b[i] / c)]
    return grid


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
@requires_oracle
def test_icc_cmyk_image_matches_pdfbox(tmp_path: Path) -> None:
    """An ICCBased N=4 CMYK image with a valid LUT-bearing profile must
    convert CMYK→RGB through the embedded profile and match PDFBox's
    ``PDImageXObject.getImage()`` output within the tolerant CMYK gate,
    while exposing the same structural surface (N=4, all-zero init colour,
    ``/Alternate /DeviceCMYK``)."""
    profile = _build_cmyk_profile()
    raster = _build_cmyk_raster()
    prof_path = tmp_path / "cmyk.icc"
    ras_path = tmp_path / "cmyk.raster"
    prof_path.write_bytes(profile)
    ras_path.write_bytes(raster)

    out = run_probe_text(
        "IccCmykImageProbe",
        str(prof_path),
        str(ras_path),
        str(_IMG),
        str(_IMG),
        str(_GRID),
    )
    java = json.loads(out.strip().splitlines()[-1])

    image = _make_icc_cmyk_image(profile, raster)
    cs = image.get_color_space()

    # ---- structural surface ----
    assert cs.get_number_of_components() == 4 == java["n"]
    assert cs.get_initial_color().get_components() == [0.0, 0.0, 0.0, 0.0]
    assert java["initial"] == [0.0, 0.0, 0.0, 0.0]
    alt = cs.get_alternate()
    assert alt is not None and alt.get_name() == "DeviceCMYK"
    assert java["alt"] == "DeviceCMYK"

    # ---- rendered raster parity (tolerant CMYK CMM gate) ----
    java_grid = java["grid"]
    py_grid = _rgb_grid(image)
    assert len(py_grid) == len(java_grid) == _GRID * _GRID * 3

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"mean abs RGB cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — CMYK samples likely not converted through "
        f"the embedded ICC profile, wrong /N stride, or the LUT was ignored"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"worst RGB channel diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond CMM rounding"
    )


@requires_oracle
def test_icc_cmyk_k_ramp_darkens_left_to_right(tmp_path: Path) -> None:
    """Guard against a degenerate decode (LUT ignored, raster mis-strided
    as a different /N, or fallback scrambling the raster). The K (black)
    ramp grows left→right with C=M=Y=0, so the rendered luminance must
    *decrease* left→right (more black = darker). A wrong-N misread
    (treating the 4-channel raster as 3-channel) would scramble it."""
    profile = _build_cmyk_profile()
    raster = _build_cmyk_raster()
    image = _make_icc_cmyk_image(profile, raster)
    pil = image.get_image()
    assert pil is not None
    gray = pil.convert("L")
    width, height = gray.size
    px = gray.load()
    left = right = 0
    n = 0
    for y in range(height):
        for x in range(width // 3):
            left += px[x, y]
            right += px[width - 1 - x, y]
            n += 1
    left_avg = left / n
    right_avg = right / n
    assert left_avg - right_avg > 60, (
        "ICCBased CMYK K-ramp is not darkening left→right "
        f"(left_avg={left_avg:.1f} right_avg={right_avg:.1f}) — the "
        "4-channel raster was likely mis-strided or the ICC LUT ignored"
    )
