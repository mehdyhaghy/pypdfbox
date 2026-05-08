from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def test_wave319_get_gid_map_includes_composite_components(
    liberation_sans: TrueTypeFont,
) -> None:
    import fontTools.ttLib as ttLib  # type: ignore[import-untyped]  # noqa: PLC0415

    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(0x00C1)  # Aacute, a composite glyph in the fixture.

    gid_map = subsetter.get_gid_map()
    subset_font = ttLib.TTFont(io.BytesIO(subsetter.to_bytes()))
    expected = {
        new_gid: liberation_sans.name_to_gid(glyph_name)
        for new_gid, glyph_name in enumerate(subset_font.getGlyphOrder())
    }

    assert gid_map == expected
    assert liberation_sans.name_to_gid("A") in gid_map.values()
    assert liberation_sans.name_to_gid("acute.uc") in gid_map.values()
