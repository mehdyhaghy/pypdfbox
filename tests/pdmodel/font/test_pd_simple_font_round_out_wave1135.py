from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from tests.pdmodel.font import test_pd_simple_font_round_out as round_out


class _ZapfAliasFont:
    def __init__(self) -> None:
        self.base_name: str | None = None

    def get_cos_object(self) -> _ZapfAliasFont:
        return self

    def set_name(self, _key: object, value: str) -> None:
        self.base_name = value

    def is_standard14(self) -> bool:
        return True

    def get_glyph_list(self) -> GlyphList:
        return GlyphList.ZAPF_DINGBATS


def test_zapfdingbats_alias_test_executes_assertion_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[_ZapfAliasFont] = []

    def font_factory() -> _ZapfAliasFont:
        font = _ZapfAliasFont()
        created.append(font)
        return font

    monkeypatch.setattr(round_out, "PDType1Font", font_factory)

    round_out.test_get_glyph_list_returns_zapf_for_zapfdingbats_alias()

    assert created[0].base_name == "ITCZapfDingbats"
