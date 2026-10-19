"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``fontbox/src/test/java/org/apache/fontbox/ttf/SystemFontHintingTest.java``.

Hinting checks against fonts that cannot be committed but are installed on
many machines. Each test is skipped when its font is missing.

Different releases of the same font carry different bytecode, so the exact
expected points are keyed by the file's ``head.checkSumAdjustment``. For a
release without an entry only the version-independent checks run.
"""

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TTFParser
from pypdfbox.fontbox.ttf.glyph_hinter import GlyphHinter

ARIAL = (
    "c:/windows/fonts/arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

# FreeType 2.13.2 grid-fitted points of Arial 'n' (gid 81) at 13ppem, per font release.
ARIAL_N_13: dict[int, tuple[list[int], list[int]]] = {
    # Arial 2.82 (Microsoft core fonts for the web)
    0x7B86E499: (
        [55, 55, 121, 121, 168, 258, 297, 362, 394, 401, 405, 405, 405, 332, 332, 332, 315, 272,
         242, 196, 128, 128, 128],
        [0, 448, 448, 387, 448, 448, 448, 420, 373, 342, 321, 269, 0, 0, 267, 312, 357, 384,
         384, 384, 324, 240, 0],
    ),
}  # fmt: skip


def _first_existing(*paths: str) -> Path | None:
    for path in paths:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
    return None


def test_arial_n() -> None:
    """Arial 'n' at 13ppem: hinted without failure, baseline and x-height on whole pixels, and,
    for a known release, every point matches FreeType."""
    file = _first_existing(*ARIAL)
    if file is None:
        pytest.skip("Arial not installed")
    font = TTFParser().parse(file)
    try:
        gid = 81
        ppem = 13
        lookup = font.get_unicode_cmap_lookup()
        assert lookup is not None
        assert lookup.get_glyph_id(ord("n")) == gid, "gid 81 should be 'n'"

        assert font.get_hinted_path(gid, ppem) is not None, "'n' should be hinted at 13ppem"

        hinter = GlyphHinter(font)
        points = hinter.get_hinted_points_f26_dot6(gid, ppem)
        assert points is not None
        assert hinter.get_failure_count() == 0, hinter.get_first_failure()

        # the baseline and the x-height are grid-fitted to whole pixels
        min_y = min(points[1])
        max_y = max(points[1])
        assert min_y == 0, "baseline"
        assert max_y % 64 == 0, f"x-height {max_y} should be on a whole pixel"

        expected = ARIAL_N_13.get(font.get_header().get_check_sum_adjustment() & 0xFFFFFFFF)
        if expected is not None:
            assert points[0] == expected[0], f"x, {file}"
            assert points[1] == expected[1], f"y, {file}"
    finally:
        font.close()
