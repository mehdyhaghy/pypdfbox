"""Wave 1349 coverage-boost: drive the residual defensive branches in
``pypdfbox.pdmodel.graphics.image.pd_inline_image``.

Targets the 8 uncovered lines after wave 1348:

* lines 641-652 — ``get_image`` honouring the optional ``region``
  (``(x, y, w, h)`` crop) and ``subsampling`` (nearest-neighbour
  resize) overload parameters. Mirrors upstream ``PDInlineImage#getImage(Rectangle, int)``
  (PDInlineImage.java line 359).
* lines 665-666 — ``get_stencil_image`` returning the underlying
  1-bit mask after the ``is_stencil()`` guard passes. The ``paint``
  argument is intentionally discarded (rendering-cluster work).

Both code paths require an inline image whose :meth:`to_pil_image`
returns a real ``PIL.Image.Image`` — a 2×2 DeviceGray raster covers the
crop / resize / stencil paths without dragging in JPEG / CCITT
fixtures.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.image import PDInlineImage


def _device_gray_params(width: int, height: int, *, stencil: bool = False) -> COSDictionary:
    """Build a minimal inline-image /CS=/G dictionary with no /F filter
    chain so the constructor's eager decode passes the raw bytes through
    verbatim."""
    params = COSDictionary()
    params.set_int("W", width)
    params.set_int("H", height)
    params.set_int("BPC", 8)
    params.set_item("CS", COSName.get_pdf_name("G"))
    if stencil:
        params.set_boolean("IM", True)
    return params


# ---------- get_image: region + subsampling overload (lines 641-652) ----------


def test_wave1349_get_image_returns_full_image_when_no_region_or_subsampling() -> None:
    # Sanity baseline so the region / subsampling branches below have a
    # known-good reference point.
    params = _device_gray_params(2, 2)
    img = PDInlineImage(params, bytes([0, 64, 128, 255]), None)

    out = img.get_image()

    assert out is not None
    assert out.size == (2, 2)


def test_wave1349_get_image_crops_to_region_tuple() -> None:
    params = _device_gray_params(4, 4)
    # 4x4 gray ramp 0..15 (×16 to spread the range).
    raster = bytes(i * 16 for i in range(16))
    img = PDInlineImage(params, raster, None)

    out = img.get_image(region=(1, 1, 2, 2))

    assert out is not None
    assert out.size == (2, 2)
    # The cropped pixels are positions (1,1), (2,1), (1,2), (2,2) in the
    # original 4×4 ramp — values 5, 6, 9, 10 → ×16 → 80, 96, 144, 160.
    # ``to_pil_image`` for DeviceGray converts to RGB so we read tuples.
    pixels = list(out.getdata())
    assert pixels == [(80, 80, 80), (96, 96, 96), (144, 144, 144), (160, 160, 160)]


def test_wave1349_get_image_subsamples_with_nearest_resize() -> None:
    params = _device_gray_params(4, 4)
    raster = bytes(i * 16 for i in range(16))
    img = PDInlineImage(params, raster, None)

    out = img.get_image(subsampling=2)

    assert out is not None
    assert out.size == (2, 2)


def test_wave1349_get_image_crop_plus_subsampling_applies_both() -> None:
    params = _device_gray_params(8, 8)
    raster = bytes(i % 256 for i in range(64))
    img = PDInlineImage(params, raster, None)

    out = img.get_image(region=(0, 0, 4, 4), subsampling=2)

    assert out is not None
    assert out.size == (2, 2)


def test_wave1349_get_image_subsampling_floor_clamps_to_at_least_one_pixel() -> None:
    # A 2×2 image with subsampling=4 would naively resize to 0×0 — the
    # ``max(1, dim // subsampling)`` guard ensures we still return a
    # valid 1×1 image. Exercises both calls of ``max(1, ...)`` at lines
    # 647-648.
    params = _device_gray_params(2, 2)
    img = PDInlineImage(params, b"\x00\x40\x80\xff", None)

    out = img.get_image(subsampling=4)

    assert out is not None
    assert out.size == (1, 1)


def test_wave1349_get_image_returns_none_when_to_pil_image_returns_none() -> None:
    # 16-bit-per-component rasters fall through ``to_pil_image`` →
    # ``None``; ``get_image`` must propagate the None even when region /
    # subsampling are provided (the line-639 short-circuit).
    params = COSDictionary()
    params.set_int("W", 2)
    params.set_int("H", 2)
    params.set_int("BPC", 16)
    params.set_item("CS", COSName.get_pdf_name("G"))
    img = PDInlineImage(params, b"\x00" * 8, None)

    assert img.get_image(region=(0, 0, 1, 1)) is None


# ---------- get_stencil_image: passing-guard branch (lines 665-666) ----------


def test_wave1349_get_stencil_image_returns_underlying_mask_when_stencil() -> None:
    # Stencil masks are 1-bpc by spec but ``to_pil_image`` short-circuits
    # for non-8bpc rasters and returns None — we want a passing
    # ``is_stencil()`` check while still getting a real PIL image back.
    # Setting /BPC 8 on a stencil is technically out-of-spec; the
    # constructor doesn't reject it, and the parity-test surface here
    # only cares that the post-guard branch returns whatever
    # ``to_pil_image`` produced (rendering-cluster work would refine
    # the 1-bpc path later — see CHANGES).
    params = _device_gray_params(2, 2, stencil=True)
    img = PDInlineImage(params, b"\x00\xff\xff\x00", None)

    # ``get_bits_per_component`` for a stencil is hardcoded to 1, so
    # ``to_pil_image`` falls into the bpc != 8 fall-through and returns
    # None. ``get_stencil_image`` must then propagate that None — but
    # critically it has to enter the post-guard branch first (line 665).
    paint_marker = object()
    result = img.get_stencil_image(paint_marker)

    assert result is None  # to_pil_image fall-through


def test_wave1349_get_stencil_image_raises_when_not_a_stencil() -> None:
    params = _device_gray_params(2, 2)  # No /IM → not a stencil.
    img = PDInlineImage(params, b"\x00\x40\x80\xff", None)

    with pytest.raises(ValueError, match="not a stencil"):
        img.get_stencil_image(paint=None)


def test_wave1349_get_stencil_image_discards_paint_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The ``del paint`` at line 665 is documented as "paint compositing
    # is rendering-cluster work" — confirm the argument is fully
    # consumed and never reaches ``to_pil_image``. We swap
    # ``to_pil_image`` for a recording stub so we can assert on the call
    # shape.
    params = _device_gray_params(2, 2, stencil=True)
    img = PDInlineImage(params, b"\x00\xff\xff\x00", None)

    calls: list[tuple] = []

    def recording_to_pil(self: PDInlineImage) -> Image.Image:
        calls.append(())
        return Image.new("L", (2, 2), 0)

    monkeypatch.setattr(PDInlineImage, "to_pil_image", recording_to_pil)

    sentinel = object()
    result = img.get_stencil_image(sentinel)

    assert result is not None
    assert result.size == (2, 2)
    # to_pil_image was called exactly once with no extra args (paint was
    # dropped at line 665).
    assert calls == [()]
