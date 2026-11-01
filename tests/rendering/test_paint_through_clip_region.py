"""Region-restricted ``_paint_through_clip`` fast path.

The renderer composites clipped / soft-masked / blended fills and strokes
only over the path's device-space bounding box, straight into the live
draw's pixel buffer. These tests pin it pixel-for-pixel against the
full-canvas fallback (``_paint_through_clip_full``) across clip, alpha,
stroke-style, soft-mask and blend-mode combinations, on opaque (RGB) and
transparency-group (RGBA) canvases.
"""

import random
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _EMPTY_BBOX, PDFRenderer, _GState

W, H = 96, 72


def _renderer(mode: str, seed: int) -> PDFRenderer:
    from pypdfbox.rendering.render_destination import RenderDestination

    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    # A y-flip + scale device CTM, like a real page render.
    r._device_ctm = (1.5, 0.0, 0.0, -1.5, 0.0, float(H))
    r._resources = None
    r._default_destination = RenderDestination.VIEW
    r._text_clip_paths = []
    r._subpaths = []
    r._transparency_group_depth = 0
    rng = np.random.default_rng(seed)
    channels = 4 if mode == "RGBA" else 3
    pixels = rng.integers(0, 256, (H, W, channels), dtype=np.uint8)
    r._image = Image.fromarray(pixels, mode)
    r._draw = aggdraw.Draw(r._image)
    r._draw.setantialias(True)
    return r


def _clip_mask(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    mask = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(
        (rnd.randint(-10, 30), rnd.randint(-10, 20),
         rnd.randint(50, 110), rnd.randint(40, 90)),
        fill=255,
    )
    # Soft (anti-aliased) edges, like a skia-rasterised clip.
    return mask.filter(ImageFilter.GaussianBlur(2))


def _random_path(rnd: random.Random) -> list[list[tuple[Any, ...]]]:
    subpaths = []
    for _ in range(rnd.randint(1, 3)):
        sub: list[tuple[Any, ...]] = [
            ("M", rnd.uniform(-10, 70), rnd.uniform(-10, 55))
        ]
        for _ in range(rnd.randint(2, 5)):
            if rnd.random() < 0.5:
                sub.append(("L", rnd.uniform(-10, 70), rnd.uniform(-10, 55)))
            else:
                sub.append(
                    ("C", *(rnd.uniform(-10, 70) for _ in range(6)))
                )
        if rnd.random() < 0.7:
            sub.append(("Z",))
        subpaths.append(sub)
    return subpaths


def _configure(r: PDFRenderer, rnd: random.Random) -> None:
    gs = r._gs
    gs.fill_rgb = (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255))
    gs.stroke_rgb = (
        rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255),
    )
    gs.fill_alpha = rnd.choice([1.0, 0.6, 0.25])
    gs.stroke_alpha = rnd.choice([1.0, 0.5])
    gs.line_width = rnd.choice([0.0, 1.0, 3.5, 9.0])
    gs.line_cap = rnd.randint(0, 2)
    gs.line_join = rnd.randint(0, 2)
    gs.miter_limit = rnd.choice([10.0, 2.0, 0.5])
    gs.dash_pattern = rnd.choice([None, ([3.0, 2.0], 1.0), ([4.0], 0.0)])
    gs.ctm = rnd.choice([
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        (0.8, 0.3, -0.2, 1.1, 5.0, -3.0),
        (2.0, 0.0, 0.0, 0.7, -4.0, 2.0),
    ])


def _paint(r: PDFRenderer, method: str, **kwargs: Any) -> np.ndarray:
    getattr(r, method)(**kwargs)
    r._draw.flush()
    return np.asarray(r._image).copy()


def _pair(
    mode: str, seed: int, **paint_kwargs: Any
) -> tuple[np.ndarray, np.ndarray]:
    results = []
    for method in ("_paint_through_clip", "_paint_through_clip_full"):
        rnd = random.Random(seed)
        r = _renderer(mode, seed)
        _configure(r, rnd)
        r._subpaths = _random_path(rnd)
        results.append(_paint(r, method, **paint_kwargs))
    return results[0], results[1]


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
@pytest.mark.parametrize("seed", range(24))
def test_clip_fill_stroke_matches_full_canvas(mode: str, seed: int) -> None:
    rnd = random.Random(1000 + seed)
    kwargs = {
        "stroke": rnd.random() < 0.6,
        "fill": rnd.random() < 0.8,
        "even_odd": rnd.random() < 0.5,
        "clip_mask": _clip_mask(seed),
    }
    fast, full = _pair(mode, seed, **kwargs)
    assert np.array_equal(fast, full)


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
@pytest.mark.parametrize("seed", range(6))
def test_soft_mask_matches_full_canvas(
    mode: str, seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    rng = np.random.default_rng(seed)
    smask = Image.fromarray(rng.integers(0, 256, (H, W), dtype=np.uint8), "L")
    monkeypatch.setattr(
        PDFRenderer, "_render_soft_mask_alpha", lambda self, _sm, _size: smask,
    )
    fast, full = _pair(
        mode, seed, stroke=True, fill=True, even_odd=False,
        clip_mask=_clip_mask(seed) if seed % 2 else None, soft_mask=object(),
    )
    assert np.array_equal(fast, full)


@pytest.mark.parametrize(
    "blend",
    [BlendMode.MULTIPLY, BlendMode.SCREEN, BlendMode.DIFFERENCE,
     BlendMode.OVERLAY, BlendMode.LUMINOSITY],
    ids=lambda b: b.name,
)
@pytest.mark.parametrize("seed", range(3))
def test_blend_mode_on_rgb_matches_full_canvas(blend: Any, seed: int) -> None:
    fast, full = _pair(
        "RGB", seed, stroke=seed == 1, fill=True, even_odd=False,
        clip_mask=_clip_mask(seed) if seed else None, blend_mode=blend,
    )
    assert np.array_equal(fast, full)


def test_blend_mode_on_rgba_uses_full_canvas_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    original = PDFRenderer._paint_through_clip_full

    def _spy(self: PDFRenderer, **kwargs: Any) -> None:
        calls.append(True)
        original(self, **kwargs)

    monkeypatch.setattr(PDFRenderer, "_paint_through_clip_full", _spy)
    r = _renderer("RGBA", 0)
    r._subpaths = [[("M", 1.0, 1.0), ("L", 20.0, 1.0), ("L", 20.0, 20.0), ("Z",)]]
    r._paint_through_clip(
        stroke=False, fill=True, even_odd=False, clip_mask=None,
        blend_mode=BlendMode.MULTIPLY,
    )
    assert calls == [True]


def test_region_path_leaves_draw_identity_and_marks_dirty() -> None:
    r = _renderer("RGB", 3)
    draw = r._draw
    r._subpaths = [[("M", 5.0, 5.0), ("L", 30.0, 5.0), ("L", 30.0, 30.0), ("Z",)]]
    before = np.asarray(r._image).copy()
    r._paint_through_clip(
        stroke=False, fill=True, even_odd=False,
        clip_mask=Image.new("L", (W, H), 255),
    )
    # Composited into the live buffer: same draw object, image not yet
    # blitted until flush.
    assert r._draw is draw
    assert draw._dirty
    assert np.array_equal(np.asarray(r._image), before)
    draw.flush()
    assert not np.array_equal(np.asarray(r._image), before)


def test_off_canvas_and_empty_paths_change_nothing() -> None:
    r = _renderer("RGB", 4)
    before = np.asarray(r._image).copy()
    clip = Image.new("L", (W, H), 255)
    r._subpaths = [[("M", 500.0, 500.0), ("L", 600.0, 500.0), ("L", 600.0, 600.0)]]
    assert r._path_paint_device_bbox(stroke=True) == _EMPTY_BBOX
    r._paint_through_clip(stroke=True, fill=True, even_odd=False, clip_mask=clip)
    r._subpaths = [[("Z",)]]
    assert r._path_paint_device_bbox(stroke=False) == _EMPTY_BBOX
    r._paint_through_clip(stroke=False, fill=True, even_odd=False, clip_mask=clip)
    r._draw.flush()
    assert np.array_equal(np.asarray(r._image), before)


def test_non_finite_geometry_falls_back_to_full_canvas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []
    monkeypatch.setattr(
        PDFRenderer, "_paint_through_clip_full",
        lambda self, **kwargs: calls.append(True),
    )
    r = _renderer("RGB", 5)
    r._subpaths = [[("M", 0.0, 0.0), ("L", float("inf"), 3.0), ("Z",)]]
    assert r._path_paint_device_bbox(stroke=False) is None
    r._paint_through_clip(
        stroke=False, fill=True, even_odd=False, clip_mask=None,
    )
    assert calls == [True]


def test_stroke_bbox_covers_miter_spike() -> None:
    # A sharp miter join at a large width must stay inside the bbox, or the
    # fast path would crop the spike that the full-canvas path keeps.
    for mode in ("RGB", "RGBA"):
        results = []
        for method in ("_paint_through_clip", "_paint_through_clip_full"):
            r = _renderer(mode, 6)
            r._gs.line_width = 6.0
            r._gs.line_join = 0
            r._gs.miter_limit = 50.0
            r._subpaths = [[
                ("M", 10.0, 10.0), ("L", 40.0, 14.0), ("L", 10.0, 18.0),
            ]]
            results.append(_paint(
                r, method, stroke=True, fill=False, even_odd=False,
                clip_mask=Image.new("L", (W, H), 255),
            ))
        assert np.array_equal(results[0], results[1])


def test_glyph_through_clip_composites_into_buffer() -> None:
    for mode in ("RGB", "RGBA"):
        r = _renderer(mode, 7)
        r._gs.clip_mask = _clip_mask(7)
        r._gs.text_rendering_mode = 0
        path = aggdraw.Path()
        path.moveto(0.0, 0.0)
        path.lineto(1.0, 0.0)
        path.lineto(1.0, 1.0)
        path.close()
        ctm = (40.0, 0.0, 0.0, 40.0, 10.0, 10.0)
        expected_image = r._image.copy()
        r._paint_glyph_path(path, ctm, (200, 10, 30))
        draw = r._draw
        assert draw._dirty
        draw.flush()
        # Reference: full-canvas layer + masked paste (the original
        # through-clip glyph composite).
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ref_draw = aggdraw.Draw(layer)
        ref_draw.settransform((40.0, 0.0, 10.0, 0.0, 40.0, 10.0))
        ref_draw.path(path, None, aggdraw.Brush((200, 10, 30)))
        ref_draw.flush()
        from PIL import ImageChops

        combined = ImageChops.multiply(layer.getchannel("A"), r._gs.clip_mask)
        expected_image.paste(layer.convert("RGB"), (0, 0), combined)
        assert np.array_equal(np.asarray(r._image), np.asarray(expected_image))


def test_draw_region_helpers_round_trip() -> None:
    image = Image.new("RGB", (10, 8), (1, 2, 3))
    draw = aggdraw.Draw(image)
    bbox = (2, 3, 6, 7)
    region = draw.read_region(bbox)
    assert region == bytes((1, 2, 3, 255)) * 16
    draw.write_region(bbox, bytes((9, 8, 7, 255)) * 16)
    assert draw._dirty
    draw.flush()
    assert image.getpixel((2, 3)) == (9, 8, 7)
    assert image.getpixel((5, 6)) == (9, 8, 7)
    assert image.getpixel((1, 3)) == (1, 2, 3)
    assert image.getpixel((6, 6)) == (1, 2, 3)


def test_paint_region_bytes_clears_scratch() -> None:
    scratch = aggdraw.Draw(Image.new("RGBA", (12, 12), (0, 0, 0, 0)))

    def _fill(d: aggdraw.Draw) -> None:
        p = aggdraw.Path()
        p.moveto(0.0, 0.0)
        p.lineto(12.0, 0.0)
        p.lineto(12.0, 12.0)
        p.lineto(0.0, 12.0)
        p.close()
        d.settransform((1.0, 0.0, 0.0, 0.0, 1.0, 0.0))
        d.path(p, None, aggdraw.Brush((255, 0, 0)))
        d.settransform()

    region = scratch.paint_region_bytes((3, 3, 7, 7), _fill)
    assert region == bytes((255, 0, 0, 255)) * 16
    # Only the region was painted, and it is cleared again afterwards.
    assert scratch.read_region((0, 0, 12, 12)) == bytes(12 * 12 * 4)
