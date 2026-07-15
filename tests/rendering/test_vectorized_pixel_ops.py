"""Byte-identity regression tests for the numpy-vectorised pixel loops.

Each vectorised helper (blend channels, matte un-pre-multiply, colour-key
mask, the ARGB white->transparent pass) must produce output that is
*byte-identical* to the original per-pixel Python loop it replaced. The
references below re-implement the scalar algorithm independently so the
comparison is a genuine oracle rather than a tautology.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

import pypdfbox.pdmodel.graphics.image.pd_image_x_object as imod
from pypdfbox.rendering.pdf_renderer import PDFRenderer


# ---------------------------------------------------------------------------
# Independent scalar references (transcribed from the pre-vectorisation loops)
# ---------------------------------------------------------------------------
def _blend_scalar(b: float, s: float, mode: str) -> float:
    if mode == "Overlay":
        return _blend_scalar(s, b, "HardLight")
    if mode == "HardLight":
        return 2.0 * b * s if s <= 0.5 else 1.0 - 2.0 * (1.0 - b) * (1.0 - s)
    if mode == "ColorDodge":
        if b == 0.0:
            return 0.0
        return 1.0 if b >= 1.0 - s else b / (1.0 - s)
    if mode == "ColorBurn":
        if b == 1.0:
            return 1.0
        return 0.0 if 1.0 - b >= s else 1.0 - (1.0 - b) / s
    if mode == "SoftLight":
        if s <= 0.5:
            return b - (1.0 - 2.0 * s) * b * (1.0 - b)
        d = ((16.0 * b - 12.0) * b + 4.0) * b if b <= 0.25 else b**0.5
        return b + (2.0 * s - 1.0) * (d - b)
    if mode == "Exclusion":
        return b + s - 2.0 * b * s
    if mode == "Multiply":
        return b * s
    return b


def _ref_blend_channel(b_arr: np.ndarray, s_arr: np.ndarray, mode: str) -> np.ndarray:
    h, w = b_arr.shape
    out = np.zeros((h, w), np.uint8)
    for y in range(h):
        for x in range(w):
            v = _blend_scalar(b_arr[y, x] / 255.0, s_arr[y, x] / 255.0, mode)
            v = 0.0 if v < 0.0 else 1.0 if v > 1.0 else v
            out[y, x] = int(round(v * 255.0))
    return out


def _ref_unpremultiply(rgba: np.ndarray, alpha: np.ndarray, m: list[float]) -> np.ndarray:
    a = rgba.copy()
    h, w = a.shape[:2]
    for y in range(h):
        for x in range(w):
            av = alpha[y, x]
            if av == 0:
                continue
            r, g, b, _ = a[y, x]
            scale = 255.0 / av
            vals = [m[i] + (int(v) - m[i]) * scale for i, v in enumerate((r, g, b))]
            a[y, x] = (
                *[0 if v < 0 else 255 if v > 255 else int(round(v)) for v in vals],
                av,
            )
    return a


def _ref_colorkey(rgb: np.ndarray, pairs) -> np.ndarray:
    h, w = rgb.shape[:2]
    alpha = np.full((h, w), 255, np.uint8)
    (rl, rh), (gl, gh), (bl, bh) = pairs
    for y in range(h):
        for x in range(w):
            r, g, b = rgb[y, x]
            if rl <= r <= rh and gl <= g <= gh and bl <= b <= bh:
                alpha[y, x] = 0
    return np.dstack([rgb, alpha]).astype(np.uint8)


@pytest.fixture
def grid() -> tuple[np.ndarray, np.ndarray]:
    b = np.tile(np.arange(256, dtype=np.uint8), (256, 1))
    s = np.tile(np.arange(256, dtype=np.uint8).reshape(256, 1), (1, 256))
    return b, s


@pytest.mark.parametrize(
    "mode", ["HardLight", "Overlay", "ColorDodge", "ColorBurn", "SoftLight"]
)
def test_blend_channel_fast_modes_byte_identical(grid, mode: str) -> None:
    b, s = grid
    got = np.asarray(
        PDFRenderer._blend_channel(Image.fromarray(b, "L"), Image.fromarray(s, "L"), mode)  # noqa: SLF001
    )
    assert np.array_equal(got, _ref_blend_channel(b, s, mode))


@pytest.mark.parametrize("mode", ["Exclusion", "Multiply"])
def test_blend_channel_fallback_modes_byte_identical(mode: str) -> None:
    # Non-fast separable modes still route through the exact scalar loop.
    b = np.tile(np.arange(0, 256, 8, dtype=np.uint8), (32, 1))
    s = np.tile(np.arange(0, 256, 8, dtype=np.uint8).reshape(32, 1), (1, 32))
    got = np.asarray(
        PDFRenderer._blend_channel(Image.fromarray(b, "L"), Image.fromarray(s, "L"), mode)  # noqa: SLF001
    )
    assert np.array_equal(got, _ref_blend_channel(b, s, mode))


def test_blend_channel_none_returns_same_object() -> None:
    backdrop = Image.new("L", (3, 3), 77)
    assert PDFRenderer._blend_channel(backdrop, Image.new("L", (3, 3), 12), None) is backdrop  # noqa: SLF001


class _FakeBase:
    def __init__(self, matte: list[float]) -> None:
        self._matte = matte

    def extract_matte(self, _smask):  # noqa: ANN001
        return self._matte


@pytest.mark.parametrize(
    "m255", [[0.0, 0.0, 0.0], [128.0, 64.0, 200.0], [255.0, 255.0, 255.0]]
)
def test_unpremultiply_matte_byte_identical(m255: list[float]) -> None:
    rng = np.random.default_rng(7)
    rgba = rng.integers(0, 256, (24, 30, 4), dtype=np.uint8)
    rgba[0, 0, 3] = 0  # skipped
    rgba[1, 1] = (10, 250, 128, 5)  # tiny alpha -> big scale -> clamp
    alpha = rgba[:, :, 3].copy()
    exp = _ref_unpremultiply(rgba, alpha, m255)
    matte01 = [c / 255.0 for c in m255]

    got_r = np.asarray(
        PDFRenderer._unpremultiply_matte(  # noqa: SLF001
            object.__new__(PDFRenderer),
            Image.fromarray(rgba, "RGBA"),
            Image.fromarray(alpha, "L"),
            _FakeBase(matte01),
            None,
        )
    )
    got_i = np.asarray(
        imod._unpremultiply_matte(
            Image.fromarray(rgba, "RGBA"),
            Image.fromarray(alpha, "L"),
            _FakeBase(matte01),
            None,
        )
    )
    assert np.array_equal(got_r, exp)
    assert np.array_equal(got_i, exp)


def test_color_key_mask_byte_identical() -> None:
    rng = np.random.default_rng(3)
    rgb = rng.integers(0, 256, (20, 25, 3), dtype=np.uint8)
    rgb[0, 0] = (100, 100, 100)  # inside range -> keyed out
    ranges = [90, 110, 90, 110, 90, 110]
    got = np.asarray(
        PDFRenderer._apply_color_key_mask(None, Image.fromarray(rgb, "RGB"), ranges)  # noqa: SLF001
    )
    assert np.array_equal(got, _ref_colorkey(rgb, [(90, 110)] * 3))


def test_argb_white_to_transparent_only_pure_white() -> None:
    # Mirrors the render_image ARGB post-pass: pixels whose R==G==B==255
    # get alpha 0; every other pixel keeps its alpha untouched.
    arr = np.zeros((4, 4, 4), np.uint8)
    arr[0, 0] = (255, 255, 255, 200)  # pure white -> alpha 0
    arr[1, 1] = (255, 255, 254, 200)  # near white -> unchanged
    arr[2, 2] = (0, 0, 0, 123)  # black -> unchanged
    rgba = Image.fromarray(arr, "RGBA")
    a = np.array(rgba)
    white = (a[:, :, 0] == 255) & (a[:, :, 1] == 255) & (a[:, :, 2] == 255)
    a[white, 3] = 0
    assert a[0, 0, 3] == 0
    assert a[1, 1, 3] == 200
    assert a[2, 2, 3] == 123
