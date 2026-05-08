from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics.form import PDFormXObject

_METADATA = COSName.METADATA  # type: ignore[attr-defined]
_OPI = COSName.get_pdf_name("OPI")
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


def _new_form() -> PDFormXObject:
    return PDFormXObject(COSStream())


def test_subtype_constant_matches_stamped_form_subtype() -> None:
    form = _new_form()

    assert PDFormXObject.SUBTYPE == "Form"
    assert form.get_subtype() == PDFormXObject.SUBTYPE
    assert form.get_sub_type() == PDFormXObject.SUBTYPE
    assert form.get_cos_object().get_name(_SUBTYPE) == PDFormXObject.SUBTYPE


def test_opi_absent_returns_none_and_predicate_false() -> None:
    form = _new_form()

    assert form.get_opi() is None
    assert form.has_opi() is False
    assert not form.get_cos_object().contains_key(_OPI)


def test_opi_round_trip_raw_dictionary_and_clear() -> None:
    form = _new_form()
    opi = COSDictionary()
    opi_13 = COSDictionary()
    opi.set_item(COSName.get_pdf_name("1.3"), opi_13)

    form.set_opi(opi)

    assert form.get_opi() is opi
    assert form.has_opi() is True
    assert form.get_cos_object().get_dictionary_object(_OPI) is opi

    form.set_opi(None)

    assert form.get_opi() is None
    assert form.has_opi() is False
    assert not form.get_cos_object().contains_key(_OPI)


def test_opi_wrong_shape_is_not_reported_present() -> None:
    form = _new_form()
    form.get_cos_object().set_item(_OPI, COSName.get_pdf_name("NotADictionary"))

    assert form.get_opi() is None
    assert form.has_opi() is False
    assert form.get_cos_object().contains_key(_OPI)


def test_has_metadata_false_when_absent_or_wrong_shape() -> None:
    form = _new_form()
    assert form.get_metadata() is None
    assert form.has_metadata() is False

    form.get_cos_object().set_item(_METADATA, COSDictionary())

    assert form.get_metadata() is None
    assert form.has_metadata() is False


def test_has_metadata_tracks_typed_metadata_round_trip() -> None:
    form = _new_form()
    metadata = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")

    form.set_metadata(metadata)

    got = form.get_metadata()
    assert got is not None
    assert got.get_cos_object() is metadata.get_cos_object()
    assert form.has_metadata() is True

    form.set_metadata(None)

    assert form.get_metadata() is None
    assert form.has_metadata() is False
    assert not form.get_cos_object().contains_key(_METADATA)
