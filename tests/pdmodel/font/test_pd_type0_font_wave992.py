from __future__ import annotations

from tests.pdmodel.font import test_pd_type0_font_wave371 as wave371


def test_wave371_unicode_cmap_name_and_code_length_helpers() -> None:
    cmap = wave371._UnicodeCMap({})  # noqa: SLF001

    assert cmap.get_name() == "Custom-H"
    assert cmap.code_length_at(0) == 3
