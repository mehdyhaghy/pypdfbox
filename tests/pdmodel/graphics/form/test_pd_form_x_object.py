from __future__ import annotations

import datetime as _dt

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form import (
    PDFormXObject,
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


_FORM = COSName.get_pdf_name("Form")
_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_BBOX = COSName.get_pdf_name("BBox")
_MATRIX = COSName.get_pdf_name("Matrix")
_RESOURCES = COSName.get_pdf_name("Resources")
_FORMTYPE = COSName.get_pdf_name("FormType")
_GROUP = COSName.get_pdf_name("Group")
_OC = COSName.get_pdf_name("OC")
_PIECE_INFO = COSName.get_pdf_name("PieceInfo")
_LAST_MODIFIED = COSName.get_pdf_name("LastModified")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_METADATA = COSName.get_pdf_name("Metadata")


def _new_form() -> PDFormXObject:
    return PDFormXObject(COSStream())


# ---------- inheritance / typing ----------


def test_extends_pd_x_object() -> None:
    form = _new_form()
    assert isinstance(form, PDXObject)


def test_constructor_stamps_type_and_subtype() -> None:
    form = _new_form()
    cos = form.get_cos_object()
    # /Type /XObject /Subtype /Form must be stamped on the underlying stream
    # dictionary so writers serialise a conformant form X-Object.
    assert cos.get_name(_TYPE) == "XObject"
    assert cos.get_name(_SUBTYPE) == "Form"
    assert form.get_subtype() == "Form"


def test_constructor_accepts_pd_stream() -> None:
    pds = PDStream(COSStream())
    form = PDFormXObject(pds)
    assert form.get_stream() is pds
    # Subtype is still stamped even when wrapping an existing PDStream.
    assert form.get_subtype() == "Form"


# ---------- /BBox ----------


def test_bbox_round_trip_writes_cos_array() -> None:
    form = _new_form()
    rect = PDRectangle(10, 20, 110, 220)
    form.set_b_box(rect)

    raw = form.get_cos_object().get_dictionary_object(_BBOX)
    assert isinstance(raw, COSArray)
    assert raw.size() == 4

    got = form.get_b_box()
    assert got is not None
    assert got.get_lower_left_x() == 10
    assert got.get_lower_left_y() == 20
    assert got.get_upper_right_x() == 110
    assert got.get_upper_right_y() == 220


def test_bbox_aliases_resolve_to_same_value() -> None:
    form = _new_form()
    rect = PDRectangle.from_width_height(50, 75)
    form.set_bbox(rect)
    a = form.get_b_box()
    b = form.get_bbox()
    assert a is not None and b is not None
    assert a.get_width() == b.get_width() == 50
    assert a.get_height() == b.get_height() == 75


# ---------- /Matrix ----------


def test_matrix_default_identity_when_absent() -> None:
    form = _new_form()
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_matrix_set_writes_six_floats_to_cos_array() -> None:
    form = _new_form()
    form.set_matrix([2, 0, 0, 2, 100, 200])

    raw = form.get_cos_object().get_dictionary_object(_MATRIX)
    assert isinstance(raw, COSArray)
    assert raw.size() == 6
    assert form.get_matrix() == [2.0, 0.0, 0.0, 2.0, 100.0, 200.0]


def test_matrix_accepts_raw_cos_array() -> None:
    form = _new_form()
    arr = COSArray([COSFloat(1), COSFloat(0), COSFloat(0), COSFloat(1),
                    COSFloat(5), COSFloat(7)])
    form.set_matrix(arr)
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 5.0, 7.0]
    # Should be the same object (set_item stores the array as-is).
    assert form.get_cos_object().get_dictionary_object(_MATRIX) is arr


def test_matrix_clear_removes_key() -> None:
    form = _new_form()
    form.set_matrix([1, 0, 0, 1, 0, 0])
    form.set_matrix(None)
    assert not form.get_cos_object().contains_key(_MATRIX)
    # And the getter still defaults to identity.
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_matrix_rejects_wrong_length() -> None:
    form = _new_form()
    try:
        form.set_matrix([1, 2, 3])
    except ValueError:
        pass
    else:
        raise AssertionError("set_matrix should reject non-6-element sequences")


# ---------- /FormType ----------


def test_form_type_default_one() -> None:
    form = _new_form()
    assert form.get_form_type() == 1
    # Default is implicit — the key must NOT be written until set explicitly.
    assert not form.get_cos_object().contains_key(_FORMTYPE)


def test_form_type_round_trip() -> None:
    form = _new_form()
    form.set_form_type(1)
    assert form.get_form_type() == 1
    assert form.get_cos_object().contains_key(_FORMTYPE)


# ---------- /Resources ----------


def test_resources_round_trip_typed() -> None:
    form = _new_form()
    assert form.get_resources() is None

    res = PDResources()
    form.set_resources(res)

    got = form.get_resources()
    assert got is not None
    assert isinstance(got, PDResources)
    assert got.get_cos_object() is res.get_cos_object()


def test_resources_accepts_raw_cos_dictionary() -> None:
    form = _new_form()
    raw = COSDictionary()
    form.set_resources(raw)
    got = form.get_resources()
    assert got is not None
    assert got.get_cos_object() is raw


def test_resources_clear_removes_key() -> None:
    form = _new_form()
    form.set_resources(PDResources())
    form.set_resources(None)
    assert form.get_resources() is None
    assert not form.get_cos_object().contains_key(_RESOURCES)


def test_resources_self_reference_returns_empty(
    # PDFBOX-4372: when /Resources is present but not a dict (e.g. an
    # indirect-reference loop where the form points to itself), upstream
    # returns an empty PDResources instead of None or raising.
) -> None:
    form = _new_form()
    cos = form.get_cos_object()
    # Inject a non-dictionary value under /Resources to simulate the broken
    # self-reference case.
    cos.set_item(_RESOURCES, COSName.get_pdf_name("BogusValue"))
    got = form.get_resources()
    assert got is not None
    # Empty resources dictionary.
    assert got.get_cos_object().size() == 0


# ---------- /Group ----------


def test_group_round_trip_raw_dict() -> None:
    form = _new_form()
    group = COSDictionary()
    group.set_name(COSName.get_pdf_name("S"), "Transparency")
    form.set_group(group)
    assert form.get_group() is group
    form.set_group(None)
    assert form.get_group() is None
    assert not form.get_cos_object().contains_key(_GROUP)


# ---------- /Group typed attributes (mirrors upstream getGroup/setGroup) ----------


def test_group_attributes_none_when_absent() -> None:
    form = _new_form()
    assert form.get_group_attributes() is None


def test_group_attributes_round_trip_typed() -> None:
    form = _new_form()
    attrs = PDTransparencyGroupAttributes()
    form.set_group_attributes(attrs)
    got = form.get_group_attributes()
    # set_group_attributes caches the typed instance; the second call
    # returns the same wrapper object.
    assert got is attrs
    # The dictionary is also installed on the underlying form stream.
    assert form.get_cos_object().get_dictionary_object(_GROUP) is attrs.get_cos_object()


def test_group_attributes_clear_removes_key() -> None:
    form = _new_form()
    form.set_group_attributes(PDTransparencyGroupAttributes())
    assert form.get_cos_object().contains_key(_GROUP)
    form.set_group_attributes(None)
    assert form.get_group_attributes() is None
    assert not form.get_cos_object().contains_key(_GROUP)


def test_group_attributes_wraps_existing_dict_lazily() -> None:
    # When the form already has a /Group raw dictionary (e.g. parsed from
    # disk), get_group_attributes should wrap and cache it on first call.
    form = _new_form()
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "Transparency")
    form.set_group(raw)

    first = form.get_group_attributes()
    assert first is not None
    assert isinstance(first, PDTransparencyGroupAttributes)
    assert first.get_cos_object() is raw
    # Caching: the second call returns the same wrapper.
    assert form.get_group_attributes() is first


def test_set_group_raw_dict_invalidates_typed_cache() -> None:
    # If a caller installs a typed wrapper, then later overwrites the
    # /Group entry with a raw dict, the typed cache must drop so a
    # subsequent get_group_attributes wraps the new dict.
    form = _new_form()
    form.set_group_attributes(PDTransparencyGroupAttributes())

    other = COSDictionary()
    other.set_name(COSName.get_pdf_name("S"), "Transparency")
    form.set_group(other)

    rewrapped = form.get_group_attributes()
    assert rewrapped is not None
    assert rewrapped.get_cos_object() is other


# ---------- /StructParents ----------


def test_struct_parents_default_minus_one_when_absent() -> None:
    form = _new_form()
    assert form.get_struct_parents() == -1
    assert not form.get_cos_object().contains_key(_STRUCT_PARENTS)


def test_struct_parents_round_trip() -> None:
    form = _new_form()
    form.set_struct_parents(42)
    assert form.get_struct_parents() == 42
    assert form.get_cos_object().get_int(_STRUCT_PARENTS) == 42


def test_struct_parent_singular_alias_matches_plural_default() -> None:
    form = _new_form()
    # Default identical to the plural getter (mirrors -1 when absent).
    assert form.get_struct_parent() == form.get_struct_parents() == -1


def test_struct_parent_singular_alias_round_trip() -> None:
    form = _new_form()
    form.set_struct_parent(7)
    # Singular setter writes the same /StructParents (plural) key — the
    # singular spelling is purely a call-site alias.
    assert form.get_struct_parent() == 7
    assert form.get_struct_parents() == 7
    assert form.get_cos_object().get_int(_STRUCT_PARENTS) == 7


# ---------- /Metadata (inherited from PDXObject) ----------


def test_metadata_round_trip_typed() -> None:
    form = _new_form()
    assert form.get_metadata() is None

    md = PDMetadata(b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    form.set_metadata(md)

    got = form.get_metadata()
    assert got is not None
    assert isinstance(got, PDMetadata)
    assert got.get_cos_object() is md.get_cos_object()
    assert form.get_cos_object().contains_key(_METADATA)

    form.set_metadata(None)
    assert form.get_metadata() is None
    assert not form.get_cos_object().contains_key(_METADATA)


# ---------- /OC ----------


def test_oc_round_trip_typed() -> None:
    form = _new_form()
    assert form.get_oc() is None

    ocg = PDOptionalContentGroup("Layer A")
    form.set_oc(ocg)

    got = form.get_oc()
    assert isinstance(got, PDPropertyList)
    assert got.get_cos_object() is ocg.get_cos_object()

    form.set_oc(None)
    assert form.get_oc() is None
    assert not form.get_cos_object().contains_key(_OC)


# ---------- /PieceInfo ----------


def test_piece_info_snake_case_round_trip() -> None:
    form = _new_form()
    assert form.get_piece_info() is None

    pi = COSDictionary()
    form.set_piece_info(pi)
    assert form.get_piece_info() is pi
    assert form.get_cos_object().get_dictionary_object(_PIECE_INFO) is pi

    form.set_piece_info(None)
    assert form.get_piece_info() is None
    assert not form.get_cos_object().contains_key(_PIECE_INFO)


def test_piece_info_alias_matches_canonical() -> None:
    # Earlier ports used the all-lowercase spelling — keep both alive.
    form = _new_form()
    pi = COSDictionary()
    form.set_pieceinfo(pi)
    assert form.get_pieceinfo() is pi
    assert form.get_piece_info() is pi


# ---------- /LastModified ----------


def test_last_modified_round_trip() -> None:
    form = _new_form()
    assert form.get_last_modified() is None

    when = _dt.datetime(2025, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc)
    form.set_last_modified(when)
    assert form.get_last_modified() == when
    assert form.get_cos_object().contains_key(_LAST_MODIFIED)

    form.set_last_modified(None)
    assert form.get_last_modified() is None
    assert not form.get_cos_object().contains_key(_LAST_MODIFIED)


# ---------- PDDocument constructor (mirrors upstream PDFormXObject(PDDocument)) ----------


def test_constructor_accepts_pd_document_for_writing() -> None:
    # Upstream provides ``PDFormXObject(PDDocument)`` to allocate a blank
    # form-XObject stream owned by the document. Verify we mirror that.
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    form = PDFormXObject(document)
    cos = form.get_cos_object()
    # /Type /XObject /Subtype /Form must still be stamped on the new stream.
    assert cos.get_name(_TYPE) == "XObject"
    assert cos.get_name(_SUBTYPE) == "Form"
    # The stream is empty / freshly allocated.
    assert form.get_form_type() == 1


# ---------- ResourceCache constructor parameter ----------


def test_constructor_threads_resource_cache_into_resources() -> None:
    # Upstream's PDFormXObject(stream, ResourceCache) wires the cache into
    # any PDResources returned by getResources(). We mirror that.
    from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

    cache = DefaultResourceCache()
    form = PDFormXObject(COSStream(), cache=cache)
    res = PDResources()
    form.set_resources(res)

    got = form.get_resources()
    assert got is not None
    assert got.get_resource_cache() is cache


def test_constructor_defaults_resource_cache_to_none() -> None:
    form = PDFormXObject(COSStream())
    form.set_resources(PDResources())
    got = form.get_resources()
    assert got is not None
    # No cache was supplied — upstream wires None.
    assert got.get_resource_cache() is None


# ---------- PDContentStream interface — stream parsing ----------


def test_get_contents_for_stream_parsing_delegates_to_random_access() -> None:
    # Mirrors upstream PDContentStream's default getContentsForStreamParsing()
    # which delegates to getContentsForRandomAccess(). Forms have a single
    # content stream so the two should yield equivalent bytes.
    stream = COSStream()
    payload = b"q 1 0 0 1 0 0 cm Q"
    with stream.create_output_stream() as out:
        out.write(payload)

    form = PDFormXObject(stream)

    parser_view = form.get_contents_for_stream_parsing()
    random_view = form.get_contents_for_random_access()
    try:
        assert parser_view.length() == random_view.length()
        assert parser_view.length() == len(payload)
    finally:
        parser_view.close()
        random_view.close()


# ---------- /Matrix graceful degradation (parity with Matrix.createMatrix) ----------


def test_matrix_returns_identity_when_array_too_short() -> None:
    # Upstream Matrix.createMatrix returns the identity matrix when the
    # /Matrix array has fewer than 6 entries — never raises.
    form = _new_form()
    short = COSArray([COSFloat(1), COSFloat(0), COSFloat(0)])
    form.get_cos_object().set_item(_MATRIX, short)
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_matrix_returns_identity_when_entry_non_numeric() -> None:
    # Upstream Matrix.createMatrix returns the identity matrix when any
    # of the first six /Matrix entries is not a COSNumber. We must
    # graceful-degrade rather than raise so partially-broken PDFs read.
    form = _new_form()
    bogus = COSArray([
        COSFloat(1),
        COSFloat(0),
        COSFloat(0),
        COSFloat(1),
        COSName.get_pdf_name("NotANumber"),  # type: ignore[arg-type]
        COSFloat(0),
    ])
    form.get_cos_object().set_item(_MATRIX, bogus)
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_matrix_uses_first_six_entries_when_array_oversized() -> None:
    # When /Matrix has more than 6 entries (some encoders are sloppy),
    # upstream's `array.size() >= 6` check still allows it. We mirror —
    # take the first 6 numeric entries verbatim.
    form = _new_form()
    arr = COSArray([
        COSFloat(2), COSFloat(0), COSFloat(0), COSFloat(2),
        COSFloat(10), COSFloat(20), COSFloat(99),  # extra
    ])
    form.get_cos_object().set_item(_MATRIX, arr)
    assert form.get_matrix() == [2.0, 0.0, 0.0, 2.0, 10.0, 20.0]


# ---------- predicate helpers ----------


def test_has_b_box_round_trip() -> None:
    form = _new_form()
    assert not form.has_b_box()
    assert not form.has_bbox()
    form.set_b_box(PDRectangle.from_width_height(10, 20))
    assert form.has_b_box()
    assert form.has_bbox()
    form.set_b_box(None)
    assert not form.has_b_box()


def test_has_matrix_only_true_when_array_has_six_entries() -> None:
    form = _new_form()
    # Identity is the *default*; the key isn't present so has_matrix is False.
    assert not form.has_matrix()
    form.set_matrix([1, 0, 0, 1, 0, 0])
    assert form.has_matrix()

    # Short or non-array values count as absent for the predicate.
    short = COSArray([COSFloat(1), COSFloat(0)])
    form.get_cos_object().set_item(_MATRIX, short)
    assert not form.has_matrix()

    form.set_matrix(None)
    assert not form.has_matrix()


def test_has_resources_round_trip() -> None:
    form = _new_form()
    assert not form.has_resources()
    form.set_resources(PDResources())
    assert form.has_resources()
    # PDFBOX-4372: even when /Resources holds a non-dict (broken
    # self-reference), the *key* is present, so has_resources is True.
    form.get_cos_object().set_item(_RESOURCES, COSName.get_pdf_name("Bogus"))
    assert form.has_resources()
    form.set_resources(None)
    assert not form.has_resources()


def test_has_group_round_trip() -> None:
    form = _new_form()
    assert not form.has_group()
    form.set_group(COSDictionary())
    assert form.has_group()
    form.set_group(None)
    assert not form.has_group()


def test_has_ref_round_trip() -> None:
    form = _new_form()
    assert not form.has_ref()
    form.set_ref(COSDictionary())
    assert form.has_ref()
    form.set_ref(None)
    assert not form.has_ref()


def test_has_oc_round_trip() -> None:
    form = _new_form()
    assert not form.has_oc()
    assert not form.has_optional_content()
    form.set_oc(PDOptionalContentGroup("Layer A"))
    assert form.has_oc()
    assert form.has_optional_content()
    form.set_oc(None)
    assert not form.has_oc()
    assert not form.has_optional_content()


def test_has_piece_info_round_trip() -> None:
    form = _new_form()
    assert not form.has_piece_info()
    assert not form.has_pieceinfo()
    form.set_piece_info(COSDictionary())
    assert form.has_piece_info()
    assert form.has_pieceinfo()
    form.set_piece_info(None)
    assert not form.has_piece_info()


def test_has_last_modified_round_trip() -> None:
    form = _new_form()
    assert not form.has_last_modified()
    form.set_last_modified(_dt.datetime(2025, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc))
    assert form.has_last_modified()
    form.set_last_modified(None)
    assert not form.has_last_modified()


def test_has_name_round_trip() -> None:
    form = _new_form()
    assert not form.has_name()
    form.set_name("MyForm")
    assert form.has_name()
    form.set_name(None)
    assert not form.has_name()


def test_has_struct_parents_round_trip() -> None:
    form = _new_form()
    assert not form.has_struct_parents()
    form.set_struct_parents(0)  # 0 is a valid key — predicate still True
    assert form.has_struct_parents()
    # Setting via the singular alias must also flip the predicate.
    form.get_cos_object().remove_item(_STRUCT_PARENTS)
    assert not form.has_struct_parents()
    form.set_struct_parent(3)
    assert form.has_struct_parents()


def test_has_form_type_round_trip() -> None:
    form = _new_form()
    # /FormType defaults to 1 when absent — has_form_type tells the implicit
    # default apart from an explicit write.
    assert not form.has_form_type()
    assert form.get_form_type() == 1
    form.set_form_type(1)
    assert form.has_form_type()
    assert form.get_form_type() == 1
