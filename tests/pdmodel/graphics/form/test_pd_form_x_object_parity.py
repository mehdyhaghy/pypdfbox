from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _new_form() -> PDFormXObject:
    return PDFormXObject(COSStream())


# ---------- /BBox round-trip ----------


def test_b_box_round_trip() -> None:
    form = _new_form()
    assert form.get_b_box() is None

    rect = PDRectangle.from_width_height(120, 80)
    form.set_b_box(rect)

    got = form.get_b_box()
    assert got is not None
    assert got.get_width() == 120
    assert got.get_height() == 80

    form.set_b_box(None)
    assert form.get_b_box() is None
    assert not form.get_cos_object().contains_key(COSName.get_pdf_name("BBox"))


# ---------- /Matrix default identity ----------


def test_matrix_default_is_identity() -> None:
    form = _new_form()
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_matrix_round_trip() -> None:
    form = _new_form()
    form.set_matrix([3, 0, 0, 3, 25, 50])
    assert form.get_matrix() == [3.0, 0.0, 0.0, 3.0, 25.0, 50.0]
    form.set_matrix(None)
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------- /FormType default 1 ----------


def test_form_type_default_is_one() -> None:
    form = _new_form()
    assert form.get_form_type() == 1


def test_form_type_round_trip() -> None:
    form = _new_form()
    form.set_form_type(1)
    assert form.get_form_type() == 1
    # PDF only defines value 1 today, but the API must accept any int.
    form.set_form_type(2)
    assert form.get_form_type() == 2


# ---------- /StructParents default -1 ----------


def test_struct_parents_default_minus_one() -> None:
    form = _new_form()
    assert form.get_struct_parents() == -1


def test_struct_parents_round_trip() -> None:
    form = _new_form()
    form.set_struct_parents(7)
    assert form.get_struct_parents() == 7


# ---------- /Metadata typed PDMetadata ----------


def test_metadata_round_trip_typed() -> None:
    form = _new_form()
    assert form.get_metadata() is None

    metadata = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    form.set_metadata(metadata)

    got = form.get_metadata()
    assert got is not None
    assert isinstance(got, PDMetadata)
    assert got.get_cos_object() is metadata.get_cos_object()
    assert got.export_xmp_metadata() == b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>"

    form.set_metadata(None)
    assert form.get_metadata() is None


# ---------- /OC typed PDPropertyList ----------


def test_oc_round_trip_typed() -> None:
    form = _new_form()
    assert form.get_oc() is None

    ocg = PDOptionalContentGroup("Layer 1")
    form.set_oc(ocg)

    got = form.get_oc()
    assert isinstance(got, PDPropertyList)
    assert isinstance(got, PDOptionalContentGroup)
    assert got.get_cos_object() is ocg.get_cos_object()

    form.set_oc(None)
    assert form.get_oc() is None


# ---------- /Group, /Ref, /PieceInfo (raw COSDictionary) ----------


def test_group_round_trip_raw_dict() -> None:
    form = _new_form()
    assert form.get_group() is None

    grp = COSDictionary()
    grp.set_name(COSName.get_pdf_name("S"), "Transparency")
    form.set_group(grp)

    got = form.get_group()
    assert got is grp

    form.set_group(None)
    assert form.get_group() is None


def test_ref_round_trip_raw_dict() -> None:
    form = _new_form()
    assert form.get_ref() is None

    ref = COSDictionary()
    form.set_ref(ref)
    assert form.get_ref() is ref

    form.set_ref(None)
    assert form.get_ref() is None


def test_pieceinfo_round_trip_raw_dict() -> None:
    form = _new_form()
    assert form.get_pieceinfo() is None

    pi = COSDictionary()
    form.set_pieceinfo(pi)
    assert form.get_pieceinfo() is pi

    form.set_pieceinfo(None)
    assert form.get_pieceinfo() is None


# ---------- /LastModified ----------


def test_last_modified_round_trip() -> None:
    form = _new_form()
    assert form.get_last_modified() is None

    when = _dt.datetime(2024, 6, 15, 12, 34, 56, tzinfo=_dt.UTC)
    form.set_last_modified(when)

    got = form.get_last_modified()
    assert got == when

    form.set_last_modified(None)
    assert form.get_last_modified() is None


# ---------- /Name ----------


def test_name_round_trip() -> None:
    form = _new_form()
    assert form.get_name() is None

    form.set_name("MyForm")
    assert form.get_name() == "MyForm"

    form.set_name(None)
    assert form.get_name() is None
