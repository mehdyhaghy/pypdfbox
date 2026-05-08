from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSNull, COSObject
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaClip,
    PDMediaClipData,
    PDMediaRendition,
    PDRendition,
)

_S = COSName.get_pdf_name("S")


def test_wave344_rendition_factory_dereferences_indirect_dictionary() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDMediaRendition.SUB_TYPE)

    rendition = PDRendition.create(COSObject(344, 0, resolved=raw))

    assert isinstance(rendition, PDMediaRendition)
    assert rendition.get_cos_object() is raw


def test_wave344_media_clip_factory_dereferences_indirect_dictionary() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDMediaClipData.SUB_TYPE)

    clip = PDMediaClip.create(COSObject(344, 1, resolved=raw))

    assert isinstance(clip, PDMediaClipData)
    assert clip.get_cos_object() is raw


def test_wave344_rendition_factory_treats_unresolved_indirect_as_absent() -> None:
    assert PDRendition.create(COSObject(344, 2)) is None


def test_wave344_media_clip_factory_treats_indirect_null_as_absent() -> None:
    assert PDMediaClip.create(COSObject(344, 3, resolved=COSNull.NULL)) is None
