"""Wave 1370 — structured-type round-trip: ResourceRef + Thumbnail + Job.

These types underpin the nested ``stRef:ResourceRef`` / ``xmpGImg:Thumbnail``
/ ``stJob:Job`` structures referenced from XMP Media Management, XMP Basic,
and Basic Job Ticket. The tests pin field accessors, ``_FIELD_TYPES``
introspection, and basic XmpSerializer behaviour when a structured type
sits as a property value.
"""

from __future__ import annotations

import io

from pypdfbox.xmpbox.type.job_type import JobType
from pypdfbox.xmpbox.type.resource_ref_type import ResourceRefType
from pypdfbox.xmpbox.type.thumbnail_type import ThumbnailType
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

# ---------------------------------------------------------------------------
# ResourceRefType — full field surface.
# ---------------------------------------------------------------------------


def test_resource_ref_round_trip_all_string_fields() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    ref = ResourceRefType(meta)
    ref.set_document_id("uuid:doc:1")
    ref.set_instance_id("uuid:inst:1")
    ref.set_file_path("/tmp/x.pdf")
    ref.set_version_id("v1")
    ref.set_manage_to("uri:mt")
    ref.set_manage_ui("uri:mu")
    ref.set_manager("Adobe XMP")
    ref.set_manager_variant("Plus")
    ref.set_part_mapping("plate")
    ref.set_rendition_params("p=1")
    ref.set_mask_markers("All")
    ref.set_rendition_class("default")
    ref.set_from_part("/X")
    ref.set_to_part("/Y")

    assert ref.get_document_id() == "uuid:doc:1"
    assert ref.get_instance_id() == "uuid:inst:1"
    assert ref.get_file_path() == "/tmp/x.pdf"
    assert ref.get_version_id() == "v1"
    assert ref.get_manage_to() == "uri:mt"
    assert ref.get_manage_ui() == "uri:mu"
    assert ref.get_manager() == "Adobe XMP"
    assert ref.get_manager_variant() == "Plus"
    assert ref.get_part_mapping() == "plate"
    assert ref.get_rendition_params() == "p=1"
    assert ref.get_mask_markers() == "All"
    assert ref.get_rendition_class() == "default"
    assert ref.get_from_part() == "/X"
    assert ref.get_to_part() == "/Y"


def test_resource_ref_namespace_and_preferred_prefix() -> None:
    assert (
        ResourceRefType.NAMESPACE
        == "http://ns.adobe.com/xap/1.0/sType/ResourceRef#"
    )
    assert ResourceRefType.PREFERRED_PREFIX == "stRef"


def test_resource_ref_alternate_paths_round_trip() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    ref = ResourceRefType(meta)
    ref.add_alternate_path("/path/a")
    ref.add_alternate_path("/path/b")
    paths = ref.get_alternate_paths()
    assert paths == ["/path/a", "/path/b"]


def test_resource_ref_alternate_paths_property_none_when_empty() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    ref = ResourceRefType(meta)
    assert ref.get_alternate_paths_property() is None
    assert ref.get_alternate_paths() is None


def test_resource_ref_field_types_complete() -> None:
    """Field-type table includes every public field constant."""
    expected = {
        ResourceRefType.DOCUMENT_ID,
        ResourceRefType.FILE_PATH,
        ResourceRefType.INSTANCE_ID,
        ResourceRefType.LAST_MODIFY_DATE,
        ResourceRefType.MANAGE_TO,
        ResourceRefType.MANAGE_UI,
        ResourceRefType.MANAGER,
        ResourceRefType.MANAGER_VARIANT,
        ResourceRefType.PART_MAPPING,
        ResourceRefType.RENDITION_PARAMS,
        ResourceRefType.VERSION_ID,
        ResourceRefType.MASK_MARKERS,
        ResourceRefType.RENDITION_CLASS,
        ResourceRefType.FROM_PART,
        ResourceRefType.TO_PART,
    }
    assert set(ResourceRefType._FIELD_TYPES.keys()) >= expected


# ---------------------------------------------------------------------------
# ThumbnailType.
# ---------------------------------------------------------------------------


def test_thumbnail_full_round_trip() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    thumb = ThumbnailType(meta)
    thumb.set_height(96)
    thumb.set_width(128)
    thumb.set_format("JPEG")
    thumb.set_image("/9j/4AAQSkZJRgABAQEASA==")

    assert thumb.get_height() == 96
    assert thumb.get_width() == 128
    assert thumb.get_format() == "JPEG"
    assert thumb.get_image() == "/9j/4AAQSkZJRgABAQEASA=="


def test_thumbnail_unset_fields_are_none() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    thumb = ThumbnailType(meta)
    assert thumb.get_height() is None
    assert thumb.get_width() is None
    assert thumb.get_format() is None
    assert thumb.get_image() is None


def test_thumbnail_parse_type_resource_attribute_present() -> None:
    """ThumbnailType emits ``rdf:parseType="Resource"`` per upstream."""
    meta = XMPMetadata.create_xmp_metadata()
    thumb = ThumbnailType(meta)
    attrs = thumb.get_all_attributes()
    parse_type = next(
        (a for a in attrs if a.get_name() == "parseType"), None
    )
    assert parse_type is not None
    assert parse_type.get_value() == "Resource"


def test_thumbnail_namespace_and_prefix() -> None:
    assert ThumbnailType.NAMESPACE == "http://ns.adobe.com/xap/1.0/g/img/"
    assert ThumbnailType.PREFERRED_PREFIX == "xmpGImg"


# ---------------------------------------------------------------------------
# JobType.
# ---------------------------------------------------------------------------


def test_job_round_trip() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    job = JobType(meta)
    job.set_id("J-1")
    job.set_name("PressRun")
    job.set_url("https://example.com/jobs/1")

    assert job.get_id() == "J-1"
    assert job.get_name() == "PressRun"
    assert job.get_url() == "https://example.com/jobs/1"


def test_job_namespace_and_field_types() -> None:
    assert JobType.NAMESPACE == "http://ns.adobe.com/xap/1.0/sType/Job#"
    assert JobType.PREFERRED_PREFIX == "stJob"
    assert set(JobType._FIELD_TYPES.keys()) == {"id", "name", "url"}


def test_job_field_prefix_constructor_propagates() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    job = JobType(meta, field_prefix="stJob")
    # The prefix flows into the structured type's prefix slot for nested
    # property serialisation.
    assert job.get_prefix() == "stJob"


# ---------------------------------------------------------------------------
# Serialise smoke: a ResourceRef nested under an XMPMediaManagement schema
# emits the structured-type element under rdf:Description.
# ---------------------------------------------------------------------------


def test_xmp_serializer_emits_structured_resource_ref_as_nested_child() -> None:
    meta = XMPMetadata.create_xmp_metadata()
    mm = meta.create_and_add_xmp_media_management_schema()
    ref = ResourceRefType(meta)
    ref.set_document_id("uuid:doc:42")
    ref.set_instance_id("uuid:inst:42")
    mm.set_derived_from(ref)

    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=False)
    blob = out.getvalue()
    # The ResourceRef structured fields appear in the output.
    assert b"uuid:doc:42" in blob
    assert b"uuid:inst:42" in blob


def test_xmp_serializer_emits_thumbnail_field_values() -> None:
    """Smoke: a Thumbnail-typed property serialises its primitive fields.

    Note: schema-side storage for thumbnails goes through the
    XMPBasicSchema; here we install the structured type directly on a
    plain schema's internal slot so we don't depend on the basic schema's
    typed wrapping path. Goal is just to assert the serialiser walks
    structured-type fields and emits them as text values.
    """
    meta = XMPMetadata.create_xmp_metadata()
    basic = meta.create_and_add_xmp_basic_schema()
    thumb = ThumbnailType(meta)
    thumb.set_height(64)
    thumb.set_width(64)
    thumb.set_format("PNG")
    thumb.set_property_name("Thumbnails")
    # Bypass the schema's get_value duck-typing; install directly.
    basic._properties["Thumbnails"] = thumb

    out = io.BytesIO()
    XmpSerializer().serialize(meta, out, with_xpacket=False)
    blob = out.getvalue()
    # Structured fields propagate as primitive text inside the element.
    assert b"64" in blob
    assert b"PNG" in blob
