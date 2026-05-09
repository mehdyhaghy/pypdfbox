from __future__ import annotations

from pypdfbox.cos import COSInteger
from tests.pdmodel.font.test_pd_cid_font_wave435 import _ints, _MappedCIDFont


def test_wave435_helpers_are_exercised_directly() -> None:
    font = _MappedCIDFont()

    assert font.get_subtype() == "CIDFontType2"
    assert _ints(2, 4).to_list() == [COSInteger.get(2), COSInteger.get(4)]
