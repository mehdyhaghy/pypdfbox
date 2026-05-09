from __future__ import annotations

from tests.pdmodel.font.test_pd_font_remaining_wave717 import _FakeCFF


def test_wave993_fake_cff_path_and_charset_accessors_are_exercised() -> None:
    path = [("curveto", 1, 2, 3, 4, 5, 6)]
    charset = [".notdef", "WaveGlyph"]
    font = _FakeCFF(path=path, charset=charset)

    assert font.get_path("WaveGlyph") is path
    assert font.get_charset() is charset
