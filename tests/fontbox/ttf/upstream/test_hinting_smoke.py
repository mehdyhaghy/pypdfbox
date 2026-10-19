"""Tests ported from upstream PDFBox 3.0 (3.0.9-SNAPSHOT)
``fontbox/src/test/java/org/apache/fontbox/ttf/HintingSmokeTest.java``.

Hints every glyph of each TrueType test font at a range of sizes and
requires that none fails. A failure (malformed-looking bytecode, an
exhausted execution budget, an unimplemented opcode) falls back to the raw
outline silently, so without this a whole font can lose its hinting
unnoticed. Glyphs that are legitimately not hinted (no instructions,
excluded by gasp or lowestRecPPEM) are not failures. Correctness of the
result is ``test_golden_hinting``'s job; this only checks that the programs
run.
"""

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TTFParser
from pypdfbox.fontbox.ttf.glyph_hinter import GlyphHinter

_TTF = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "ttf"
PPEMS = (9, 12, 16, 24, 48)

_NOT_BUNDLED_OFL = "SIL OFL 1.1, not bundled per the wave 1360 fixture policy"
_NOT_BUNDLED_DOWNLOAD = "downloaded by upstream's Maven build; not bundled"

FONTS = [
    pytest.param(_TTF / "LiberationSans-Regular.ttf", id="LiberationSans-Regular"),
    pytest.param(
        None, id="JosefinSans-Italic", marks=pytest.mark.skip(reason=_NOT_BUNDLED_OFL)
    ),
    pytest.param(None, id="Lohit-Bengali", marks=pytest.mark.skip(reason=_NOT_BUNDLED_OFL)),
    pytest.param(
        None, id="Lohit-Devanagari", marks=pytest.mark.skip(reason=_NOT_BUNDLED_OFL)
    ),
    pytest.param(None, id="Lohit-Gujarati", marks=pytest.mark.skip(reason=_NOT_BUNDLED_OFL)),
    pytest.param(None, id="Lohit-Tamil", marks=pytest.mark.skip(reason=_NOT_BUNDLED_OFL)),
    # upstream downloads DejaVuSansMono; pypdfbox bundles it
    pytest.param(_TTF / "DejaVuSansMono.ttf", id="DejaVuSansMono"),
    pytest.param(None, id="Keyboard", marks=pytest.mark.skip(reason=_NOT_BUNDLED_DOWNLOAD)),
    pytest.param(
        None, id="NotoEmoji-Regular", marks=pytest.mark.skip(reason=_NOT_BUNDLED_DOWNLOAD)
    ),
    pytest.param(
        None, id="NotoMono-Regular", marks=pytest.mark.skip(reason=_NOT_BUNDLED_DOWNLOAD)
    ),
    pytest.param(None, id="ipag", marks=pytest.mark.skip(reason=_NOT_BUNDLED_DOWNLOAD)),
]


@pytest.mark.parametrize("path", FONTS)
def test_every_glyph_hints_without_failure(path: Path) -> None:
    font = TTFParser(True).parse(path)
    try:
        hinter = GlyphHinter(font)
        glyphs = font.get_number_of_glyphs()
        assert glyphs > 0, path
        for ppem in PPEMS:
            for gid in range(glyphs):
                hinter.get_hinted_points_f26_dot6(gid, ppem)
        assert hinter.get_failure_count() == 0, (
            f"{path}: {hinter.get_failure_count()} failures, first {hinter.get_first_failure()}"
        )
        # none of these fonts builds its glyphs with bytecode, so none may get full control
        assert not hinter.is_full_control(), f"{path} probed as needing full bytecode control"
    finally:
        font.close()
