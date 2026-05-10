"""Parity tests for ``pypdfbox.pdmodel.graphics.form.PDFormXObject``.

There is no dedicated ``PDFormXObjectTest.java`` in the upstream PDFBox
test suite — the class is exercised indirectly through higher-level
content-stream / appearance / structure-tree tests. This file targets
the upstream public API surface directly so the form X-Object class has
its own first-class coverage.

Each test cites the upstream Java line(s) it mirrors.
"""

from __future__ import annotations

import datetime as _dt
from typing import BinaryIO

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.form.pd_transparency_group_attributes import (
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FORMTYPE = COSName.get_pdf_name("FormType")
_BBOX = COSName.get_pdf_name("BBox")
_MATRIX = COSName.get_pdf_name("Matrix")
_RESOURCES = COSName.get_pdf_name("Resources")
_GROUP = COSName.get_pdf_name("Group")
_OC = COSName.get_pdf_name("OC")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")


def _new_form() -> PDFormXObject:
    return PDFormXObject(COSStream())


# ---------- Constructors (upstream lines 67-103) ----------


def test_pd_stream_constructor_stamps_form_subtype() -> None:
    # Upstream lines 67-71: ``PDFormXObject(PDStream stream)`` calls
    # ``super(stream, COSName.FORM)`` which stamps /Type /XObject and
    # /Subtype /Form via the protected PDXObject ctor.
    pds = PDStream(COSStream())
    form = PDFormXObject(pds)
    cos = form.get_cos_object()
    assert cos.get_name(_TYPE) == "XObject"
    assert cos.get_name(_SUBTYPE) == "Form"
    assert form.get_stream() is pds


def test_cos_stream_constructor_stamps_form_subtype() -> None:
    # Upstream lines 77-81: ``PDFormXObject(COSStream stream)`` —
    # convenience overload that wraps the COSStream in a PDStream.
    stream = COSStream()
    form = PDFormXObject(stream)
    assert form.get_cos_object() is stream
    assert stream.get_name(_TYPE) == "XObject"
    assert stream.get_name(_SUBTYPE) == "Form"


def test_cos_stream_with_cache_constructor_threads_cache() -> None:
    # Upstream lines 89-93: ``PDFormXObject(COSStream, ResourceCache)``
    # stores the cache so ``getResources`` threads it through to the
    # returned PDResources.
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    cache = DefaultResourceCache()
    form = PDFormXObject(COSStream(), cache=cache)
    form.set_resources(PDResources())
    got = form.get_resources()
    assert got is not None
    assert got.get_resource_cache() is cache


def test_pd_document_constructor_creates_fresh_stream() -> None:
    # Upstream lines 99-103: ``PDFormXObject(PDDocument document)``
    # allocates a blank PDStream owned by the document.
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    try:
        form = PDFormXObject(document)
        cos = form.get_cos_object()
        assert cos.get_name(_TYPE) == "XObject"
        assert cos.get_name(_SUBTYPE) == "Form"
    finally:
        document.close()


# ---------- Inheritance (upstream line 58) ----------


def test_extends_pd_x_object() -> None:
    # ``public class PDFormXObject extends PDXObject implements PDContentStream``
    assert isinstance(_new_form(), PDXObject)


# ---------- /FormType (upstream lines 109-121) ----------


def test_get_form_type_defaults_to_one() -> None:
    # Upstream line 111: ``return getCOSObject().getInt(COSName.FORMTYPE, 1);``
    form = _new_form()
    assert form.get_form_type() == 1


def test_set_form_type_round_trip() -> None:
    # Upstream line 120: ``getCOSObject().setInt(COSName.FORMTYPE, formType);``
    form = _new_form()
    form.set_form_type(1)
    assert form.get_cos_object().get_int(_FORMTYPE) == 1
    assert form.get_form_type() == 1


# ---------- /Group typed (upstream lines 128-150) ----------


def test_get_group_attributes_returns_none_when_absent() -> None:
    # Upstream lines 130-138: lazily wraps /Group on first read.
    assert _new_form().get_group_attributes() is None


def test_get_group_attributes_lazily_wraps_existing_dict() -> None:
    # Upstream lines 132-137: when /Group is a dict, wrap it as
    # PDTransparencyGroupAttributes and cache.
    form = _new_form()
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "Transparency")
    form.get_cos_object().set_item(_GROUP, raw)
    typed = form.get_group_attributes()
    assert isinstance(typed, PDTransparencyGroupAttributes)
    assert typed.get_cos_object() is raw
    # Caching: second call returns the same wrapper.
    assert form.get_group_attributes() is typed


def test_set_group_attributes_writes_dict_to_cos() -> None:
    # Upstream lines 146-150: ``this.group = group; getCOSObject()
    # .setItem(COSName.GROUP, group);``
    form = _new_form()
    attrs = PDTransparencyGroupAttributes()
    form.set_group_attributes(attrs)
    assert form.get_cos_object().get_dictionary_object(_GROUP) is attrs.get_cos_object()
    assert form.get_group_attributes() is attrs


# ---------- /BBox (upstream lines 209-229) ----------


def test_get_b_box_returns_none_when_absent() -> None:
    # Upstream line 212: ``return array != null ? new PDRectangle(array) : null;``
    assert _new_form().get_b_box() is None


def test_get_b_box_round_trip() -> None:
    # Upstream lines 219-228: ``setItem(BBOX, bbox.getCOSArray())``.
    form = _new_form()
    rect = PDRectangle(0, 0, 612, 792)
    form.set_b_box(rect)
    got = form.get_b_box()
    assert got is not None
    assert got.get_lower_left_x() == 0
    assert got.get_upper_right_x() == 612
    assert got.get_upper_right_y() == 792


def test_set_b_box_none_removes_key() -> None:
    # Upstream lines 221-224: ``if (bbox == null) removeItem(BBOX)``.
    form = _new_form()
    form.set_b_box(PDRectangle.from_width_height(10, 20))
    form.set_b_box(None)
    assert not form.get_cos_object().contains_key(_BBOX)


# ---------- /Matrix (upstream lines 236-255) ----------


def test_get_matrix_default_identity_when_absent() -> None:
    # Upstream line 238: ``Matrix.createMatrix(...)`` returns identity for
    # a missing key.
    form = _new_form()
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_set_matrix_writes_six_floats() -> None:
    # Upstream lines 247-254: ``COSArray matrix = new COSArray(); ...``.
    form = _new_form()
    form.set_matrix([2, 0, 0, 2, 100, 200])
    raw = form.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(raw, COSArray)
    assert raw.size() == 6
    assert form.get_matrix() == [2.0, 0.0, 0.0, 2.0, 100.0, 200.0]


def test_get_matrix_identity_when_array_too_short() -> None:
    # Mirrors upstream Matrix.createMatrix: short arrays collapse to
    # identity rather than raising.
    form = _new_form()
    form.get_cos_object().set_item(_MATRIX, COSArray([COSFloat(1), COSFloat(0)]))
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_matrix_identity_when_entry_non_numeric() -> None:
    # Mirrors upstream Matrix.createMatrix: non-COSNumber entries
    # collapse to identity (graceful degradation).
    form = _new_form()
    form.get_cos_object().set_item(
        _MATRIX,
        COSArray([
            COSFloat(1), COSFloat(0), COSFloat(0), COSFloat(1),
            COSName.get_pdf_name("NotANumber"), COSFloat(0),
        ]),
    )
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_matrix_accepts_cos_integer_entries() -> None:
    # Mirrors upstream Matrix.createMatrix accepting COSNumber (both
    # COSInteger and COSFloat).
    form = _new_form()
    form.get_cos_object().set_item(
        _MATRIX,
        COSArray([
            COSInteger(1), COSInteger(0), COSInteger(0),
            COSInteger(1), COSInteger(0), COSInteger(0),
        ]),
    )
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


# ---------- /Resources (upstream lines 175-199) ----------


def test_get_resources_returns_none_when_absent() -> None:
    # Upstream line 189: ``return null;``
    assert _new_form().get_resources() is None


def test_get_resources_returns_typed_pd_resources() -> None:
    # Upstream line 180: ``return new PDResources(resources, cache);``
    form = _new_form()
    res = PDResources()
    form.set_resources(res)
    got = form.get_resources()
    assert isinstance(got, PDResources)
    assert got.get_cos_object() is res.get_cos_object()


def test_get_resources_pdfbox_4372_self_reference_returns_empty() -> None:
    # Upstream lines 182-188: when /Resources is present but not a dict,
    # return an empty PDResources to avoid a self-reference loop
    # (PDFBOX-4372).
    form = _new_form()
    form.get_cos_object().set_item(_RESOURCES, COSName.get_pdf_name("Loop"))
    got = form.get_resources()
    assert got is not None
    assert got.get_cos_object().size() == 0


def test_set_resources_writes_cos_object() -> None:
    # Upstream line 198: ``setItem(COSName.RESOURCES, resources);``
    form = _new_form()
    res = PDResources()
    form.set_resources(res)
    assert form.get_cos_object().get_dictionary_object(_RESOURCES) is res.get_cos_object()


# ---------- /StructParents (upstream lines 264-276) ----------


def test_get_struct_parents_default_minus_one() -> None:
    # Upstream line 266: ``return getCOSObject().getInt(STRUCT_PARENTS);``
    # — getInt without a default returns -1 when absent.
    assert _new_form().get_struct_parents() == -1


def test_set_struct_parents_round_trip() -> None:
    # Upstream line 275: ``getCOSObject().setInt(STRUCT_PARENTS, structParent);``
    form = _new_form()
    form.set_struct_parents(7)
    assert form.get_struct_parents() == 7
    assert form.get_cos_object().get_int(_STRUCT_PARENTS) == 7


# ---------- /OC = optional content (upstream lines 284-298) ----------


def test_get_optional_content_returns_none_when_absent() -> None:
    # Upstream line 287: ``return optionalContent != null ?
    # PDPropertyList.create(optionalContent) : null;``
    assert _new_form().get_optional_content() is None


def test_get_optional_content_returns_typed_property_list() -> None:
    # Upstream line 287: typed wrap via ``PDPropertyList.create``.
    form = _new_form()
    ocg = PDOptionalContentGroup("Layer 1")
    form.set_optional_content(ocg)
    got = form.get_optional_content()
    assert isinstance(got, PDPropertyList)
    assert got.get_cos_object() is ocg.get_cos_object()


def test_set_optional_content_round_trip() -> None:
    # Upstream line 297: ``getCOSObject().setItem(COSName.OC, oc);``
    form = _new_form()
    ocg = PDOptionalContentGroup("Layer A")
    form.set_optional_content(ocg)
    assert form.get_cos_object().get_dictionary_object(_OC) is ocg.get_cos_object()


# ---------- /Metadata (inherited from PDXObject) ----------


def test_metadata_round_trip_typed() -> None:
    form = _new_form()
    md = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    form.set_metadata(md)
    got = form.get_metadata()
    assert got is not None
    assert isinstance(got, PDMetadata)
    assert got.get_cos_object() is md.get_cos_object()


# ---------- PDContentStream interface (upstream lines 152-167) ----------


def test_get_content_stream_returns_pd_stream() -> None:
    # Upstream line 154: ``return new PDStream(getCOSObject());``
    form = _new_form()
    cs = form.get_content_stream()
    assert isinstance(cs, PDStream)
    assert cs.get_cos_object() is form.get_cos_object()


def test_get_contents_returns_input_stream() -> None:
    # Upstream lines 158-161: ``return new RandomAccessInputStream(
    # getContentsForRandomAccess());``
    stream = COSStream()
    payload = b"q 1 0 0 1 0 0 cm Q"
    with stream.create_output_stream() as out:
        out.write(payload)
    form = PDFormXObject(stream)
    contents: BinaryIO = form.get_contents()
    try:
        assert contents.read() == payload
    finally:
        contents.close()


def test_get_contents_for_random_access_returns_random_access_read() -> None:
    # Upstream lines 164-167: ``return getCOSObject().createView();``
    stream = COSStream()
    payload = b"BT /F1 12 Tf ET"
    with stream.create_output_stream() as out:
        out.write(payload)
    form = PDFormXObject(stream)
    view = form.get_contents_for_random_access()
    try:
        assert isinstance(view, RandomAccessRead)
        assert view.length() == len(payload)
    finally:
        view.close()


# ---------- /LastModified ----------


def test_last_modified_round_trip() -> None:
    form = _new_form()
    when = _dt.datetime(2024, 6, 15, 12, 34, 56, tzinfo=_dt.UTC)
    form.set_last_modified(when)
    assert form.get_last_modified() == when
