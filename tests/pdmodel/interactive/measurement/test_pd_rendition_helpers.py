from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import (
    PDMediaPlayParameters,
    PDMediaRendition,
    PDRendition,
    PDSelectorRendition,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_MH = COSName.get_pdf_name("MH")
_BE = COSName.get_pdf_name("BE")


def test_pd_rendition_get_type_reports_default_type_name() -> None:
    media = PDMediaRendition()
    assert media.get_type() == "Rendition"


def test_pd_rendition_get_type_returns_existing_type_when_provided() -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "Rendition")
    raw.set_name(COSName.get_pdf_name("S"), "MR")
    rendition = PDRendition.create(raw)
    assert rendition is not None
    assert rendition.get_type() == "Rendition"


def test_pd_rendition_get_or_create_mh_creates_when_missing() -> None:
    media = PDMediaRendition()
    assert media.get_mh() is None

    mh = media.get_or_create_mh()
    assert isinstance(mh, COSDictionary)
    # Stored on the underlying dict
    assert media.get_cos_object().get_dictionary_object(_MH) is mh
    # Subsequent calls return the same instance
    assert media.get_or_create_mh() is mh


def test_pd_rendition_get_or_create_be_creates_when_missing() -> None:
    selector = PDSelectorRendition()
    assert selector.get_be() is None

    be = selector.get_or_create_be()
    assert isinstance(be, COSDictionary)
    assert selector.get_cos_object().get_dictionary_object(_BE) is be
    assert selector.get_or_create_be() is be


def test_pd_rendition_get_or_create_mh_returns_existing_dict() -> None:
    media = PDMediaRendition()
    explicit = COSDictionary()
    media.set_mh(explicit)
    assert media.get_or_create_mh() is explicit


def test_pd_rendition_repr_includes_subtype_and_n() -> None:
    media = PDMediaRendition()
    media.set_n("clip-x")
    text = repr(media)
    assert "PDMediaRendition" in text
    assert "MR" in text
    assert "clip-x" in text


def test_pd_media_play_parameters_get_or_create_mh() -> None:
    params = PDMediaPlayParameters()
    assert params.get_mh() is None

    mh = params.get_or_create_mh()
    assert isinstance(mh, COSDictionary)
    assert params.get_cos_object().get_dictionary_object(_MH) is mh
    assert params.get_or_create_mh() is mh


def test_pd_media_play_parameters_get_or_create_be() -> None:
    params = PDMediaPlayParameters()
    be = params.get_or_create_be()
    assert isinstance(be, COSDictionary)
    assert params.get_be() is be


def test_pd_media_play_parameters_repr_reports_set_state() -> None:
    params = PDMediaPlayParameters()
    assert "MH=unset" in repr(params)
    assert "BE=unset" in repr(params)

    params.set_mh(COSDictionary())
    assert "MH=set" in repr(params)
