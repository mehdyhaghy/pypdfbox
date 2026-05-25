"""Wave 1397 branch-coverage tests for the RightsManagement,
MediaManagement, and EXIF schemas.

Closes False-branch arrows where typed accessors filter heterogeneous
backing lists / build LangAlt arrays without the default-language slot:

* ``XMPRightsManagementSchema._build_owners_array`` 130->129 — skip non-str
* ``XMPRightsManagementSchema._build_usage_terms_lang_alt`` 158->161 —
  no ``x-default`` in keys (skip the prepend branch)
* ``XMPMediaManagementSchema.add_manifest`` 505->508 — existing list is
  reused (not allocated)
* ``XMPMediaManagementSchema.add_ingredient`` 636->639 — existing list
  reused
* ``ExifSchema._typed_struct_set`` 1401->1403 — value lacks
  ``set_property_name``
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.exif_schema import ExifSchema
from pypdfbox.xmpbox.type.resource_ref_type import ResourceRefType
from pypdfbox.xmpbox.xmp_media_management_schema import XMPMediaManagementSchema
from pypdfbox.xmpbox.xmp_rights_management_schema import (
    XMPRightsManagementSchema,
)


def _md() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_rights_build_owners_array_skips_non_string_items() -> None:
    """Closes 130->129: a heterogeneous Owner bag drops non-string
    entries on the way out."""
    schema = XMPRightsManagementSchema(_md())
    schema._properties["Owner"] = ["Alice", 42, "Bob"]  # noqa: SLF001
    arr = schema._build_owners_array()  # noqa: SLF001
    assert arr is not None
    # Only the two strings survive — the integer is dropped.
    serialized = [
        child.get_string_value() for child in arr.get_all_properties()
    ]
    assert serialized == ["Alice", "Bob"]


def test_rights_build_usage_terms_lang_alt_without_xdefault() -> None:
    """Closes 158->161: a UsageTerms dict that has no ``x-default``
    entry — the prepend branch is skipped."""
    schema = XMPRightsManagementSchema(_md())
    # Only non-default languages; ``x-default`` is absent.
    schema._properties["UsageTerms"] = {  # noqa: SLF001
        "en-US": "License A",
        "fr-FR": "License B",
    }
    la = schema._build_usage_terms_lang_alt()  # noqa: SLF001
    assert la is not None
    # Both alt values are present.
    texts = [child.get_string_value() for child in la.get_all_properties()]
    assert set(texts) == {"License A", "License B"}


def test_media_add_manifest_reuses_existing_list() -> None:
    """Closes 505->508: second add_manifest reuses the existing list."""
    schema = XMPMediaManagementSchema(_md())
    first = ResourceRefType(_md())
    second = ResourceRefType(_md())
    schema.add_manifest(first)
    schema.add_manifest(second)
    out = schema._properties["Manifest"]  # noqa: SLF001
    assert isinstance(out, list)
    assert out == [first, second]


def test_media_add_ingredient_reuses_existing_list() -> None:
    """Closes 636->639: second add_ingredient reuses the existing list."""
    schema = XMPMediaManagementSchema(_md())
    first = ResourceRefType(_md())
    second = ResourceRefType(_md())
    schema.add_ingredient(first)
    schema.add_ingredient(second)
    out = schema._properties["Ingredients"]  # noqa: SLF001
    assert isinstance(out, list)
    assert out == [first, second]


def test_exif_typed_struct_set_value_without_set_property_name() -> None:
    """Closes 1401->1403: stash a plain object (no
    ``set_property_name`` attr) under a typed-struct slot."""
    schema = ExifSchema(_md())
    sentinel: object = object()
    schema._typed_struct_set("OECF", sentinel)  # noqa: SLF001
    assert schema._properties["OECF"] is sentinel  # noqa: SLF001
