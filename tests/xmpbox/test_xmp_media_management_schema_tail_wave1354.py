"""Wave 1354 tail-sweep: cover ``get_manager_variant_property``.

Targets line 367 in ``xmp_media_management_schema.py`` (the typed-getter
companion to ``set_manager_variant_property``). The setter is exercised
in existing tests but the matching getter was never called.
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMediaManagementSchema, XMPMetadata
from pypdfbox.xmpbox.type.text_type import TextType


def test_get_manager_variant_property_after_set_returns_typed() -> None:
    schema = XMPMediaManagementSchema(XMPMetadata.create_xmp_metadata())
    typed = TextType(
        schema._metadata,  # noqa: SLF001
        schema._namespace,  # noqa: SLF001
        schema._prefix,  # noqa: SLF001
        "ManagerVariant",
        "enterprise",
    )
    schema.set_manager_variant_property(typed)
    assert schema.get_manager_variant_property() is typed


def test_get_manager_variant_property_returns_none_when_missing() -> None:
    schema = XMPMediaManagementSchema(XMPMetadata.create_xmp_metadata())
    assert schema.get_manager_variant_property() is None
