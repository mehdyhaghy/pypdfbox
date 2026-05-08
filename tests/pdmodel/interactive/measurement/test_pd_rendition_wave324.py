from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaClip,
    PDMediaClipData,
    PDMediaRendition,
    PDRendition,
)

_S = COSName.get_pdf_name("S")


def test_wave324_rendition_factory_accepts_string_subtype() -> None:
    raw = COSDictionary()
    raw.set_item(_S, COSString(PDMediaRendition.SUB_TYPE))

    rendition = PDRendition.create(raw)

    assert isinstance(rendition, PDMediaRendition)
    assert rendition.get_subtype() == PDMediaRendition.SUB_TYPE


def test_wave324_media_clip_factory_accepts_string_subtype() -> None:
    raw = COSDictionary()
    raw.set_item(_S, COSString(PDMediaClipData.SUB_TYPE))

    clip = PDMediaClip.create(raw)

    assert isinstance(clip, PDMediaClipData)
    assert clip.get_subtype() == PDMediaClipData.SUB_TYPE
