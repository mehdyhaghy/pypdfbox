from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem

_C = COSName.C  # type: ignore[attr-defined]


def test_get_text_color_returns_none_for_three_item_array_with_non_number() -> None:
    item = PDOutlineItem()
    item.get_cos_object().set_item(
        _C,
        COSArray([COSFloat(0.1), COSString("not-a-number"), COSFloat(0.3)]),
    )

    assert item.get_text_color() is None
