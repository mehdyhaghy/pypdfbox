from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaClipData,
    PDMediaClipSection,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_S = COSName.get_pdf_name("S")
_D = COSName.get_pdf_name("D")


def test_wave367_media_clip_section_initializes_media_clip_subtype() -> None:
    section = PDMediaClipSection()

    assert section.get_cos_object().get_name(_TYPE) == "MediaClip"
    assert section.get_subtype() == PDMediaClipSection.SUB_TYPE


def test_wave367_media_clip_section_d_round_trips_nested_clip_data() -> None:
    section = PDMediaClipSection()
    nested = PDMediaClipData()
    nested.set_ct("audio/mpeg")

    section.set_d(nested)

    assert section.get_cos_object().get_dictionary_object(_D) is nested.get_cos_object()
    resolved = section.get_d()
    assert isinstance(resolved, PDMediaClipData)
    assert resolved.get_ct() == "audio/mpeg"


def test_wave367_media_clip_section_d_dispatches_nested_section_dictionary() -> None:
    nested_raw = COSDictionary()
    nested_raw.set_name(_S, PDMediaClipSection.SUB_TYPE)
    raw = COSDictionary()
    raw.set_name(_S, PDMediaClipSection.SUB_TYPE)
    raw.set_item(_D, nested_raw)

    resolved = PDMediaClipSection(raw).get_d()

    assert isinstance(resolved, PDMediaClipSection)
    assert resolved.get_cos_object() is nested_raw


def test_wave367_media_clip_section_ignores_non_dictionary_or_unknown_d() -> None:
    section = PDMediaClipSection()
    section.get_cos_object().set_item(_D, COSString("not a media clip"))
    assert section.get_d() is None

    unknown = COSDictionary()
    unknown.set_name(_S, "unknown")
    section.get_cos_object().set_item(_D, unknown)
    assert section.get_d() is None


def test_wave367_media_clip_section_set_d_none_removes_existing_entry() -> None:
    section = PDMediaClipSection()
    section.set_d(PDMediaClipData())
    assert section.get_cos_object().contains_key(_D)

    section.set_d(None)

    assert not section.get_cos_object().contains_key(_D)
    assert section.get_d() is None
