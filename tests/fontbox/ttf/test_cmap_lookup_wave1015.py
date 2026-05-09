from __future__ import annotations

from tests.fontbox.ttf import test_cmap_lookup as cmap_mod


def test_partial_subclass_implemented_methods_remain_callable() -> None:
    cmap_mod.test_cmap_lookup_subclass_missing_get_char_codes_cannot_instantiate()
    cmap_mod.test_cmap_lookup_subclass_missing_get_glyph_id_cannot_instantiate()

    missing_get_char_codes = cmap_mod._MissingGetCharCodesPartial
    missing_get_glyph_id = cmap_mod._MissingGetGlyphIdPartial

    assert missing_get_char_codes is not None
    assert missing_get_glyph_id is not None
    assert missing_get_char_codes.get_glyph_id(object(), 123) == 0
    assert missing_get_glyph_id.get_char_codes(object(), 4) is None
