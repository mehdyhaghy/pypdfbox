from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem


def test_wave902_get_text_color_defensively_rejects_malformed_array(
    monkeypatch,
) -> None:
    item = PDOutlineItem()
    malformed = COSArray([COSFloat(0.1), COSString("bad"), COSFloat(0.3)])

    monkeypatch.setattr(item, "_get_text_color_array", lambda: malformed)

    assert item.get_text_color() is None
