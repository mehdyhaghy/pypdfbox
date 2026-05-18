"""Coverage-boost test (wave 1351) for ``XMPSchemaFactory``.

The wave-1281 tests only exercise the ``schema_class is XMPSchema`` arm
of ``create_xmp_schema``. The ``elif prefix and len(params) >= 2`` branch
(lines 55-56 of ``xmp_schema_factory.py``) — used when a real
:class:`XMPSchema` subclass is registered — was never covered.

We instantiate :class:`AdobePDFSchema` (init signature
``(self, metadata, own_prefix=None)``, two parameters after ``self``)
with an explicit prefix so the factory routes through ``args =
[metadata, prefix]`` rather than the bare ``[metadata]`` fallback.
"""
from __future__ import annotations

from pypdfbox.xmpbox.adobe_pdf_schema import AdobePDFSchema
from pypdfbox.xmpbox.schema.xmp_schema_factory import XMPSchemaFactory
from pypdfbox.xmpbox.type.type_mapping import PropertiesDescription
from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


def test_factory_routes_subclass_with_prefix_through_two_arg_init() -> None:
    """Subclass + explicit prefix → ``args = [metadata, prefix]`` arm."""
    pd = PropertiesDescription()
    factory = XMPSchemaFactory(AdobePDFSchema.NAMESPACE, AdobePDFSchema, pd)
    metadata = XMPMetadata.create_xmp_metadata()
    schema = factory.create_xmp_schema(metadata, "customprefix")
    assert isinstance(schema, AdobePDFSchema)
    # The two-arg init forwarded the prefix through ``super().__init__``.
    assert schema.get_prefix() == "customprefix"
    assert schema in metadata.get_all_schemas()


def test_factory_routes_subclass_without_prefix_through_single_arg_init() -> None:
    """Subclass + no prefix → falls through both ``if`` branches and
    uses the default ``args = [metadata]`` path; the subclass default
    prefix kicks in."""
    pd = PropertiesDescription()
    factory = XMPSchemaFactory(AdobePDFSchema.NAMESPACE, AdobePDFSchema, pd)
    metadata = XMPMetadata.create_xmp_metadata()
    schema = factory.create_xmp_schema(metadata, None)
    assert isinstance(schema, AdobePDFSchema)
    assert schema.get_prefix() == AdobePDFSchema.PREFERRED_PREFIX
