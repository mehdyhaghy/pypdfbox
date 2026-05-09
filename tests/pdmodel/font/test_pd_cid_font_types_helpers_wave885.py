from __future__ import annotations

import pytest

from tests.pdmodel.font import test_pd_cid_font_types_wave476 as cid_mod


def test_wave885_ttf_inner_reports_glyf_presence_and_order() -> None:
    inner = cid_mod._TTInner()  # noqa: SLF001

    assert "glyf" in inner
    assert "cmap" not in inner
    assert inner.getGlyphOrder() == [".notdef"]


def test_wave885_ttf_inner_getitem_rejects_non_glyf_table() -> None:
    inner = cid_mod._TTInner()  # noqa: SLF001

    with pytest.raises(KeyError, match="head"):
        inner["head"]


def test_wave885_ttf_inner_glyf_table_contains_box_metrics() -> None:
    inner = cid_mod._TTInner()  # noqa: SLF001

    glyf = inner["glyf"]

    assert glyf[".notdef"].yMin == -10
    assert glyf[".notdef"].yMax == 50
