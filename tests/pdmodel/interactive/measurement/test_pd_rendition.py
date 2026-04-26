from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaClip,
    PDMediaClipData,
    PDMediaClipSection,
    PDMediaPlayParameters,
    PDMediaRendition,
    PDRendition,
    PDSelectorRendition,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_S = COSName.get_pdf_name("S")


def test_media_rendition_subtype_and_n_round_trip() -> None:
    media = PDMediaRendition()
    assert media.get_subtype() == PDMediaRendition.SUB_TYPE == "MR"
    assert media.get_cos_object().get_name(_TYPE) == "Rendition"

    media.set_n("clip-1")
    assert media.get_n() == "clip-1"

    media.set_n(None)
    assert media.get_n() is None


def test_selector_rendition_subtype_and_set_r_round_trip() -> None:
    selector = PDSelectorRendition()
    assert selector.get_subtype() == PDSelectorRendition.SUB_TYPE == "SR"
    assert selector.get_r() == []

    a = PDMediaRendition()
    a.set_n("alt-a")
    b = PDMediaRendition()
    b.set_n("alt-b")
    selector.set_r([a, b])

    resolved = selector.get_r()
    assert len(resolved) == 2
    assert all(isinstance(r, PDMediaRendition) for r in resolved)
    assert [r.get_n() for r in resolved] == ["alt-a", "alt-b"]

    selector.set_r(None)
    assert selector.get_r() == []


def test_pd_rendition_create_dispatches_on_subtype() -> None:
    mr_raw = COSDictionary()
    mr_raw.set_name(_TYPE, "Rendition")
    mr_raw.set_name(_S, "MR")
    assert isinstance(PDRendition.create(mr_raw), PDMediaRendition)

    sr_raw = COSDictionary()
    sr_raw.set_name(_TYPE, "Rendition")
    sr_raw.set_name(_S, "SR")
    assert isinstance(PDRendition.create(sr_raw), PDSelectorRendition)

    assert PDRendition.create(None) is None

    unknown = COSDictionary()
    unknown.set_name(_S, "ZZ")
    assert PDRendition.create(unknown) is None


def test_pd_media_clip_create_dispatches_on_subtype() -> None:
    mcd_raw = COSDictionary()
    mcd_raw.set_name(_S, "MCD")
    assert isinstance(PDMediaClip.create(mcd_raw), PDMediaClipData)

    mcs_raw = COSDictionary()
    mcs_raw.set_name(_S, "MCS")
    assert isinstance(PDMediaClip.create(mcs_raw), PDMediaClipSection)

    assert PDMediaClip.create(None) is None


def test_media_rendition_c_and_p_round_trip() -> None:
    media = PDMediaRendition()

    clip = PDMediaClipData()
    clip.set_ct("video/mp4")
    media.set_c(clip)

    resolved = media.get_c()
    assert isinstance(resolved, PDMediaClipData)
    assert resolved.get_ct() == "video/mp4"

    params = PDMediaPlayParameters()
    mh = COSDictionary()
    params.set_mh(mh)
    media.set_p(params)

    resolved_p = media.get_p()
    assert isinstance(resolved_p, PDMediaPlayParameters)
    assert resolved_p.get_mh() is mh

    media.set_c(None)
    media.set_p(None)
    assert media.get_c() is None
    assert media.get_p() is None


def test_pd_rendition_mh_and_be_round_trip() -> None:
    media = PDMediaRendition()
    mh = COSDictionary()
    be = COSDictionary()
    media.set_mh(mh)
    media.set_be(be)
    assert media.get_mh() is mh
    assert media.get_be() is be

    media.set_mh(None)
    media.set_be(None)
    assert media.get_mh() is None
    assert media.get_be() is None
