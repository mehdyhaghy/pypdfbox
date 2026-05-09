from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaClip,
    PDMediaClipData,
    PDRendition,
)

_D = COSName.get_pdf_name("D")
_TYPE = COSName.TYPE  # type: ignore[attr-defined]


def test_media_clip_base_name_round_trip_and_clear() -> None:
    clip = PDMediaClip()
    assert clip.get_cos_object().get_name(_TYPE) == "MediaClip"
    assert clip.get_n() is None

    clip.set_n("preview")
    assert clip.get_n() == "preview"

    clip.set_n(None)
    assert clip.get_n() is None


def test_media_clip_data_d_round_trip_and_clear() -> None:
    clip = PDMediaClipData()
    payload = COSString("movie-bytes")

    assert clip.get_d() is None
    clip.set_d(payload)
    assert clip.get_d() is payload

    clip.set_d(None)
    assert clip.get_d() is None
    assert not clip.get_cos_object().contains_key(_D)


def test_media_clip_create_rejects_non_dictionary_base() -> None:
    with pytest.raises(TypeError, match="PDMediaClip.create expects COSDictionary"):
        PDMediaClip.create(COSString("not-a-dictionary"))


def test_media_clip_create_stops_on_indirect_cycle() -> None:
    indirect = COSObject(751, 0)
    indirect.set_object(indirect)

    assert PDMediaClip.create(indirect) is None


def test_rendition_create_rejects_non_dictionary_base() -> None:
    with pytest.raises(TypeError, match="PDRendition.create expects COSDictionary"):
        PDRendition.create(COSString("not-a-dictionary"))


def test_rendition_create_stops_on_indirect_cycle() -> None:
    indirect = COSObject(752, 0)
    indirect.set_object(indirect)

    assert PDRendition.create(indirect) is None


def test_media_clip_does_not_overwrite_existing_type() -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "Other")

    clip = PDMediaClip(raw)

    assert clip.get_cos_object() is raw
    assert raw.get_name(_TYPE) == "Other"
