from __future__ import annotations

import pytest

from tests.pdmodel.font.test_pd_cid_font_types_wave436 import _FakeCFF, _FakeTTF


def test_wave436_fake_cff_unknown_property_raises_key_error() -> None:
    with pytest.raises(KeyError):
        _FakeCFF().get_property("NotFontBBox")


def test_wave436_fake_ttf_exposes_advance_widths_property() -> None:
    widths = [0, 250, 500]

    assert _FakeTTF(advance_widths=widths).advance_widths is widths
