"""Live PDFBox differential parity for the RASTER colour-conversion surface
``PDIndexed.toRGBImage(WritableRaster)`` where the ``/Lookup`` palette is
carried as a **COSStream** (FlateDecode), NOT a literal ``COSString``.

This is the open facet not reached by the sibling Indexed oracles:

* ``test_indexed_stream_oracle.py`` drives the single-sample
  ``toRGB(float[])`` path with a stream lookup.
* ``test_color_image_rgb_oracle.py`` (waves 1456/1458) drives the raster
  ``toRGBImage`` path but with a literal **string** lookup.

The raster path takes its own code in PDFBox: ``PDIndexed.initRgbColorTable``
builds the cached RGB lookup table once from the **decoded stream bytes**, then
``toRGBImage`` does a per-pixel palette dereference clamped to
``actualMaxIndex`` (= ``hival`` when the lookup is long enough). Three
behaviours are exercised here that neither sibling reaches together:

* **stream dereference in the raster path** — the palette bytes come from
  decoding the stream's ``/Filter`` chain (FlateDecode). A regression treating
  the stream slot as empty (string-only handling) would zero the palette.
* **per-pixel palette lookup** — one byte per pixel indexes the RGB table.
* **per-pixel hival clamp** — pixel indices ``> hival`` (4, 7, 255) clamp to
  the last palette entry (entry ``hival``); a missing clamp would read past
  the palette.

The Java side is ``oracle/probes/IndexedStreamImageProbe.java``: for each
Indexed space it emits a metadata line ``csname# ncomp`` (so we assert
``get_number_of_components() == 1``) followed by ``csname idx -> r g b`` pixel
lines.

Two parity tiers, mirroring ``test_indexed_cal_oracle.py``:

**Byte-exact tier — DeviceRGB base.** Palette dereference + DeviceRGB identity,
no colour-management module. pypdfbox and PDFBox agree byte-for-byte on every
pixel including the out-of-range clamps.

**ICC sRGB tier — ICCBased(sRGB) base.** Each palette entry runs sRGB → sRGB
through a CMM on both sides (LittleCMS2 via Pillow here, AWT CMM in PDFBox).
Agreement holds within the documented ``<= 2/255`` CMM LSB-rounding tolerance —
the same window the standalone ``IccSrgb`` rows of the colour oracles apply.
The per-pixel clamp is byte-exact (pure integer logic); only the per-entry
RGB conversion involves a CMM.
"""

from __future__ import annotations

import contextlib
import os
import tempfile

import pytest

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from tests.oracle.harness import requires_oracle, run_probe_text

# Pixel index set MUST match IndexedStreamImageProbe.java exactly, in order.
_INDICES = [0, 1, 2, 3, 4, 7, 255]

# DeviceRGB base: 4 entries * 3 bytes, hival 3.
_RGB_PALETTE = bytes(
    [
        0, 0, 0,        # 0 black
        255, 0, 0,      # 1 red
        0, 255, 0,      # 2 green
        128, 128, 255,  # 3 light blue
    ]
)

# ICCBased(sRGB) base: 4 entries * 3 bytes, hival 3.
_ICC_PALETTE = bytes(
    [
        0, 0, 0,
        255, 0, 0,
        64, 128, 192,
        255, 255, 255,
    ]
)

_TOLERANCE_MAX_DELTA = 2


def _build_srgb_icc() -> bytes:
    """Mint an sRGB ICC profile via Pillow's ImageCms (LittleCMS2-backed). The
    Java probe consumes the same bytes via its argv path argument."""
    from PIL import ImageCms

    profile = ImageCms.createProfile("sRGB")
    return ImageCms.ImageCmsProfile(profile).tobytes()


def _indexed_stream(base: PDColorSpace, hival: int, palette: bytes) -> PDIndexed:
    """Build a ``PDIndexed`` whose ``/Lookup`` is a FlateDecode ``COSStream``,
    matching ``IndexedStreamImageProbe.indexedStream``."""
    lookup = COSStream()
    with lookup.create_output_stream(["FlateDecode"]) as os_:
        os_.write(palette)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(base.get_cos_object())
    arr.add(COSInteger.get(hival))
    arr.add(lookup)
    cs = PDColorSpace.create(arr)
    assert isinstance(cs, PDIndexed), f"expected PDIndexed, got {type(cs)!r}"
    return cs


def _icc_srgb(icc_bytes: bytes) -> PDColorSpace:
    s = COSStream()
    s.set_int("N", 3)
    with s.create_output_stream() as os_:
        os_.write(icc_bytes)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("ICCBased"))
    arr.add(s)
    cs = PDColorSpace.create(arr)
    assert cs is not None
    return cs


def _raster_bytes(indices: list[int]) -> bytes:
    """Tightly-packed 8-bit single-band sample buffer (1 row)."""
    return bytes(indices)


def _image_pixels(cs: PDIndexed) -> list[tuple[int, int, int]]:
    width = len(_INDICES)
    img = cs.to_rgb_image(_raster_bytes(_INDICES), width, 1)
    rgb = img.convert("RGB")
    return [rgb.getpixel((x, 0)) for x in range(width)]


def _parse_probe(
    text: str,
) -> tuple[dict[str, int], dict[str, list[tuple[int, int, int]]]]:
    """Parse the probe output into (ncomp-by-name, pixels-by-name)."""
    ncomp: dict[str, int] = {}
    pixels: dict[str, list[tuple[int, int, int]]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "->" in line:
            left, right = line.split("->")
            name = left.split()[0]
            r, g, b = (int(x) for x in right.split())
            pixels.setdefault(name, []).append((r, g, b))
        elif "#" in line:
            name, n = line.split("#")
            ncomp[name.strip()] = int(n.strip())
    return ncomp, pixels


@pytest.fixture(scope="module")
def _icc_bytes() -> bytes:
    return _build_srgb_icc()


@pytest.fixture(scope="module")
def _java(
    _icc_bytes: bytes,
) -> tuple[dict[str, int], dict[str, list[tuple[int, int, int]]]]:
    # mkstemp (no open Python handle) + explicit unlink so Windows CI doesn't
    # trip on the "file opened exclusively" reopen issue when the Java probe
    # re-opens the path. Same pattern as test_indexed_cal_oracle.
    fd, tmp_name = tempfile.mkstemp(suffix=".icc")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(_icc_bytes)
        text = run_probe_text("IndexedStreamImageProbe", tmp_name)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
    return _parse_probe(text)


# ---------- byte-exact tier: DeviceRGB base ----------


@requires_oracle
def test_indexed_stream_image_rgb_base_exact(
    _java: tuple[dict[str, int], dict[str, list[tuple[int, int, int]]]],
) -> None:
    """Stream ``/Lookup`` + DeviceRGB base raster decode: pypdfbox
    ``to_rgb_image`` pixels == PDFBox ``toRGBImage`` pixels, byte-for-byte,
    including the out-of-range hival clamps (indices 4, 7, 255 → entry 3)."""
    ncomp, pixels = _java
    cs = _indexed_stream(
        PDColorSpace.create(COSName.get_pdf_name("DeviceRGB")), 3, _RGB_PALETTE
    )
    assert ncomp["IdxRgbStreamImg"] == 1
    assert cs.get_number_of_components() == 1
    java = pixels["IdxRgbStreamImg"]
    assert len(java) == len(_INDICES), f"probe emitted {len(java)} rows"
    py = _image_pixels(cs)
    for index, py_rgb, j_rgb in zip(_INDICES, py, java, strict=True):
        assert py_rgb == j_rgb, (
            f"IdxRgbStreamImg index {index}: pypdfbox {py_rgb} != PDFBox {j_rgb}"
        )


# ---------- ICC sRGB tier (CMM tolerance) ----------


@requires_oracle
def test_indexed_stream_image_icc_base_tolerance(
    _icc_bytes: bytes,
    _java: tuple[dict[str, int], dict[str, list[tuple[int, int, int]]]],
) -> None:
    """Stream ``/Lookup`` + ICCBased(sRGB) base raster decode: each palette
    entry runs sRGB → sRGB through a CMM on both sides; agreement holds within
    the documented ``<= 2/255`` CMM LSB-rounding tolerance. The per-pixel clamp
    (indices 4, 7, 255 → entry 3) is byte-exact integer logic regardless."""
    ncomp, pixels = _java
    cs = _indexed_stream(_icc_srgb(_icc_bytes), 3, _ICC_PALETTE)
    assert ncomp["IdxIccStreamImg"] == 1
    assert cs.get_number_of_components() == 1
    java = pixels["IdxIccStreamImg"]
    assert len(java) == len(_INDICES), f"probe emitted {len(java)} rows"
    py = _image_pixels(cs)
    for index, py_rgb, j_rgb in zip(_INDICES, py, java, strict=True):
        for chan, (p, j) in enumerate(zip(py_rgb, j_rgb, strict=True)):
            assert abs(p - j) <= _TOLERANCE_MAX_DELTA, (
                f"IdxIccStreamImg index {index} channel {chan}: pypdfbox {p} "
                f"vs PDFBox {j} exceeds the {_TOLERANCE_MAX_DELTA}/255 CMM "
                f"tolerance"
            )


# ---------- clamp invariant (independent of the base) ----------


@requires_oracle
def test_indexed_stream_image_clamp_to_hival_entry(
    _icc_bytes: bytes,
    _java: tuple[dict[str, int], dict[str, list[tuple[int, int, int]]]],
) -> None:
    """A pixel index ``> hival`` resolves to the SAME palette entry as ``hival``
    in both pypdfbox and PDFBox — pure integer clamp logic, no CMM involved. We
    verify PDFBox's rows for the out-of-range indices equal its row for index 3,
    and that pypdfbox makes the identical clamp choice, for both bases."""
    _, pixels = _java
    rgb_cs = _indexed_stream(
        PDColorSpace.create(COSName.get_pdf_name("DeviceRGB")), 3, _RGB_PALETTE
    )
    icc_cs = _indexed_stream(_icc_srgb(_icc_bytes), 3, _ICC_PALETTE)
    for name, cs in (
        ("IdxRgbStreamImg", rgb_cs),
        ("IdxIccStreamImg", icc_cs),
    ):
        rows = dict(zip(_INDICES, pixels[name], strict=True))
        for over in (4, 7, 255):
            assert rows[over] == rows[3], (
                f"{name}: PDFBox index {over} should clamp to hival entry 3"
            )
        py = dict(zip(_INDICES, _image_pixels(cs), strict=True))
        for over in (4, 7, 255):
            assert py[over] == py[3], (
                f"{name}: pypdfbox index {over} should clamp to hival entry 3"
            )
