from __future__ import annotations

from pypdfbox.pdmodel.font.pd_font_descriptor import (
    PDPanose,
    PDPanoseClassification,
)


def test_wave317_panose_classification_pads_short_source_like_java_copy_of_range() -> None:
    panose = PDPanose(b"\x00\x08\x02\x0b\x06")

    classification = panose.get_panose()

    assert isinstance(classification, PDPanoseClassification)
    assert classification.get_bytes() == b"\x02\x0b\x06" + b"\x00" * 7
    assert len(classification) == PDPanoseClassification.LENGTH
    assert classification.get_family_kind() == 2
    assert classification.get_x_height() == 0
