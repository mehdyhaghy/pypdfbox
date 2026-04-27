from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import (
    PDActionRendition,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.measurement.pd_media_rendition import (
    PDMediaRendition,
)
from pypdfbox.pdmodel.interactive.measurement.pd_rendition import PDRendition


def _screen_annotation_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Screen"))
    return d


def _media_rendition_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Rendition"))
    d.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("MR"))
    return d


def test_get_annotation_returns_none_when_an_absent() -> None:
    action = PDActionRendition()
    assert action.get_annotation() is None


def test_get_annotation_returns_typed_wrapper_for_screen_subtype() -> None:
    action = PDActionRendition()
    raw = _screen_annotation_dict()
    action.set_an(raw)

    typed = action.get_annotation()
    assert typed is not None
    assert isinstance(typed, PDAnnotation)
    # /Subtype /Screen has no dedicated subclass yet — falls back through
    # PDAnnotation.create. The underlying COSDictionary must round-trip.
    assert typed.get_cos_object() is raw


def test_set_annotation_round_trip() -> None:
    action = PDActionRendition()
    annotation = PDAnnotation.create(_screen_annotation_dict())

    action.set_annotation(annotation)
    assert action.get_an() is annotation.get_cos_object()

    fetched = action.get_annotation()
    assert fetched is not None
    assert fetched.get_cos_object() is annotation.get_cos_object()


def test_get_rendition_returns_none_when_r_absent() -> None:
    action = PDActionRendition()
    assert action.get_rendition() is None


def test_get_rendition_wraps_existing_media_rendition_dict() -> None:
    action = PDActionRendition()
    raw = _media_rendition_dict()
    action.set_r(raw)

    typed = action.get_rendition()
    assert typed is not None
    assert isinstance(typed, PDMediaRendition)
    assert typed.get_cos_object() is raw
    assert typed.get_subtype() == "MR"


def test_set_rendition_round_trip() -> None:
    action = PDActionRendition()
    rendition = PDRendition.create(_media_rendition_dict())
    assert rendition is not None

    action.set_rendition(rendition)
    assert action.get_r() is rendition.get_cos_object()

    fetched = action.get_rendition()
    assert fetched is not None
    assert fetched.get_cos_object() is rendition.get_cos_object()


def test_set_annotation_none_and_set_rendition_none_clear_entries() -> None:
    action = PDActionRendition()
    action.set_an(_screen_annotation_dict())
    action.set_r(_media_rendition_dict())
    assert action.get_an() is not None
    assert action.get_r() is not None

    action.set_annotation(None)
    action.set_rendition(None)
    assert action.get_an() is None
    assert action.get_r() is None
    assert action.get_annotation() is None
    assert action.get_rendition() is None
