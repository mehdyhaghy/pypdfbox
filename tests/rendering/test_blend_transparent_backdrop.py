"""Blend modes over a backdrop with transparency (a transparency-group
canvas) follow upstream ``BlendComposite.compose``: the blend result is
weighted by the backdrop alpha, and pixels the paint does not reach keep
their alpha."""

import numpy as np
import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState

# (mode, backdrop RGBA, source RGBA, result RGBA). Results come from
# PDFBox 3.0.8: Graphics2D with BlendComposite.getInstance(mode, 1f)
# drawing a 1x1 TYPE_INT_ARGB source onto a TYPE_INT_ARGB backdrop.
_JAVA_CASES = [
    ("Multiply", (0, 255, 0, 128), (255, 0, 0, 255), (127, 0, 0, 255)),
    ("Multiply", (0, 255, 0, 128), (255, 0, 0, 100), (71, 112, 0, 178)),
    ("Screen", (10, 200, 30, 60), (200, 50, 90, 180), (183, 98, 89, 198)),
    ("Screen", (128, 254, 1, 1), (31, 203, 1, 1), (80, 229, 1, 2)),
    ("Overlay", (60, 92, 254, 60), (190, 255, 0, 254), (166, 238, 60, 254)),
    ("Lighten", (37, 128, 127, 254), (128, 39, 160, 179), (101, 128, 150, 255)),
    ("ColorDodge", (233, 0, 242, 200), (33, 255, 228, 128), (218, 31, 246, 228)),
    ("HardLight", (128, 70, 142, 0), (183, 194, 77, 1), (183, 194, 77, 1)),
    ("SoftLight", (6, 93, 0, 1), (254, 163, 27, 200), (253, 163, 27, 200)),
    ("Exclusion", (186, 36, 192, 1), (127, 186, 59, 238), (127, 186, 59, 238)),
    ("Hue", (43, 255, 135, 128), (82, 105, 185, 254), (118, 141, 220, 255)),
    ("Color", (116, 128, 14, 1), (143, 99, 176, 178), (143, 99, 176, 178)),
    ("Luminosity", (0, 1, 247, 60), (0, 176, 43, 61), (12, 90, 159, 107)),
    ("Difference", (255, 255, 255, 0), (40, 80, 120, 200), (40, 80, 120, 200)),
]


@pytest.mark.parametrize(
    ("mode", "backdrop", "source", "expected"),
    _JAVA_CASES,
    ids=[f"{c[0]}-{i}" for i, c in enumerate(_JAVA_CASES)],
)
def test_blend_matches_upstream_on_transparent_backdrop(
    mode: str, backdrop: tuple, source: tuple, expected: tuple
) -> None:
    blend_mode = BlendMode.get_instance(COSName.get_pdf_name(mode))
    dst = Image.new("RGBA", (1, 1), backdrop)
    src = Image.new("RGBA", (1, 1), source)
    assert PDFRenderer._blend(src, dst, blend_mode).getpixel((0, 0)) == expected


def test_blended_clip_paint_keeps_backdrop_alpha_outside_paint() -> None:
    w, h = 40, 30
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [_GState()]
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    r._resources = None
    r._text_clip_paths = []
    r._transparency_group_depth = 0
    rng = np.random.default_rng(3)
    canvas = rng.integers(0, 256, (h, w, 4), dtype=np.uint8)
    r._image = Image.fromarray(canvas, "RGBA")
    r._draw = aggdraw.Draw(r._image)
    r._draw.setantialias(True)
    r._gs.fill_rgb = (200, 40, 90)
    r._subpaths = [[("M", 5.0, 5.0), ("L", 15.0, 5.0), ("L", 15.0, 15.0),
                    ("L", 5.0, 15.0), ("Z",)]]

    r._paint_through_clip_full(
        stroke=False, fill=True, even_odd=False,
        clip_mask=Image.new("L", (w, h), 255),
        blend_mode=BlendMode.MULTIPLY,
    )
    r._draw.flush()

    after = np.asarray(r._image)
    # Far from the painted square nothing changes, alpha included.
    assert np.array_equal(after[20:, 20:], canvas[20:, 20:])
    # Inside it the result alpha is opaque (source alpha 1).
    assert (after[8:12, 8:12, 3] == 255).all()
