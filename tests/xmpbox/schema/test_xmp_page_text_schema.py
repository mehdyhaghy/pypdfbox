"""Hand-written tests for ``pypdfbox.xmpbox.schema.XMPPageTextSchema``.

Verbatim upstream-named mirror of ``org.apache.xmpbox.schema.XMPPageTextSchema``
(the double-P class), distinct from the typo'd ``XMPageTextSchema``.
"""

from __future__ import annotations

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.schema import XMPPageTextSchema


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_namespace_and_prefix() -> None:
    assert XMPPageTextSchema.NAMESPACE == "http://ns.adobe.com/xap/1.0/t/pg/"
    assert XMPPageTextSchema.PREFERRED_PREFIX == "xmpTPg"


def test_property_local_name_constants() -> None:
    assert XMPPageTextSchema.MAX_PAGE_SIZE == "MaxPageSize"
    assert XMPPageTextSchema.N_PAGES == "NPages"
    assert XMPPageTextSchema.PLATENAMES == "PlateNames"
    assert XMPPageTextSchema.COLORANTS == "Colorants"
    assert XMPPageTextSchema.FONTS == "Fonts"


def test_default_constructor_uses_preferred_prefix() -> None:
    schema = XMPPageTextSchema(_metadata())
    assert schema.get_namespace() == XMPPageTextSchema.NAMESPACE
    assert schema.get_prefix() == XMPPageTextSchema.PREFERRED_PREFIX


def test_prefix_constructor_overrides_prefix() -> None:
    schema = XMPPageTextSchema(_metadata(), "myPrefix")
    assert schema.get_namespace() == XMPPageTextSchema.NAMESPACE
    assert schema.get_prefix() == "myPrefix"


def test_namespace_declaration_registered() -> None:
    schema = XMPPageTextSchema(_metadata())
    namespaces = schema.get_namespaces()
    assert namespaces.get(XMPPageTextSchema.PREFERRED_PREFIX) == XMPPageTextSchema.NAMESPACE


def test_is_distinct_class_from_typo_variant() -> None:
    from pypdfbox.xmpbox import XMPageTextSchema

    assert XMPPageTextSchema is not XMPageTextSchema
    # Same namespace, different class identity.
    assert XMPPageTextSchema.NAMESPACE == XMPageTextSchema.NAMESPACE
