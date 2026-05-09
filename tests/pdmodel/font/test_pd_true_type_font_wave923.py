from __future__ import annotations

import pytest

from tests.pdmodel.font.test_pd_true_type_font_wave408 import _InnerStub, _TTFStub


def test_wave923_inner_stub_rejects_unknown_table_name() -> None:
    inner = _InnerStub()

    with pytest.raises(KeyError) as excinfo:
        inner["head"]

    assert excinfo.value.args == ("head",)


def test_wave923_ttf_stub_width_default_and_glyph_count() -> None:
    ttf = _TTFStub(advances={1: 250})

    assert ttf.get_advance_width(1) == 250
    assert ttf.get_advance_width(99) == 0
    assert ttf.get_number_of_glyphs() == 2
