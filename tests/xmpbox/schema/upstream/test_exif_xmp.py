"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/TestExifXmp.java

Two tests:

* ``testNonStrict`` — loads ``/validxmp/exif.xmp`` with
  ``strict_parsing=False`` and asserts the SpectralSensitivity TextType
  parses to ``"spectral sens value"``.
* ``testGenerate`` — builds an :class:`ExifSchema` programmatically
  with an :class:`OECFType` nested struct and serializes the metadata.
  Wave 1371 ported :class:`OECFType`, so the upstream-faithful
  reproduction below now runs alongside the simpler pypdfbox stand-in
  exercise kept here for round-trip coverage.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.xmpbox import (
    DomXmpParser,
    ExifSchema,
    OECFType,
    TextType,
    XMPMetadata,
)

# Fixture lives at tests/fixtures/xmpbox/validxmp/exif.xmp — copied verbatim
# from upstream xmpbox/src/test/resources/validxmp/exif.xmp.
_FIXTURES = Path(__file__).parent.parent.parent.parent / "fixtures" / "xmpbox"


def test_non_strict() -> None:
    """Translated from upstream ``testNonStrict``."""
    data = (_FIXTURES / "validxmp" / "exif.xmp").read_bytes()
    builder = DomXmpParser()
    builder.set_strict_parsing(False)
    rxmp = builder.parse(data)
    schema = rxmp.get_schema(ExifSchema)
    assert schema is not None
    ss = schema.get_property(ExifSchema.SPECTRAL_SENSITIVITY)
    assert ss is not None
    # Upstream casts to TextType — pypdfbox stores the value as a
    # string on the schema's flat property map, so we read through the
    # typed-property accessor when available.
    if isinstance(ss, TextType):
        assert ss.get_value() == "spectral sens value"
    else:
        # Fall back to the schema-level typed getter.
        assert schema.get_spectral_sensitivity() == "spectral sens value"


def test_generate() -> None:
    """Translated from upstream ``testGenerate``: build an ExifSchema
    with an OECFType child and serialise. Wave 1371 ported OECFType so
    this test now matches upstream's structure exactly — a Columns
    integer is installed on the OECF struct, the struct's property
    name is set to ``ExifSchema.OECF``, and the schema serialises
    without raising."""
    metadata = XMPMetadata.create_xmp_metadata()
    tmapping = metadata.get_type_mapping()
    exif = ExifSchema(metadata)
    metadata.add_schema(exif)
    oecf = OECFType(metadata)
    oecf.add_property(
        tmapping.create_integer(
            oecf.get_namespace(),
            oecf.get_prefix(),
            OECFType.COLUMNS,
            14,
        )
    )
    oecf.set_property_name(ExifSchema.OECF)
    # Schema-level install: route the typed-struct setter at the OECF slot.
    exif.set_oecf_property(oecf)

    from io import BytesIO

    from pypdfbox.xmpbox.xml import XmpSerializer
    serializer = XmpSerializer()
    bos = BytesIO()
    serializer.serialize(metadata, bos, False)
    # The serializer must not raise; the round trip is asserted in
    # other tests. Mirror upstream's bare invocation — no assertion on
    # the output bytes beyond "something was written".
    assert bos.tell() > 0
    # Belt-and-suspenders: confirm the OECF struct round-trips through
    # the typed accessor (upstream test does not assert on read-back).
    assert exif.get_oecf_property() is oecf
    assert oecf.get_columns() == 14
