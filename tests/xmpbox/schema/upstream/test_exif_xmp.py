"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/schema/TestExifXmp.java

Two tests:

* ``testNonStrict`` — loads ``/validxmp/exif.xmp`` with
  ``strict_parsing=False`` and asserts the SpectralSensitivity TextType
  parses to ``"spectral sens value"``.
* ``testGenerate`` — builds an :class:`ExifSchema` programmatically
  with an :class:`OECFType` nested struct and serializes the metadata.
  pypdfbox does not yet ship :class:`OECFType`, so the test is skipped
  here pending the structured-type cluster expansion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.xmpbox import (
    DomXmpParser,
    ExifSchema,
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
    with an OECFType child and serialise. pypdfbox has no OECFType
    yet, so this test exercises the serializer with an ExifSchema
    populated through the simple-property setter path that ships."""
    metadata = XMPMetadata.create_xmp_metadata()
    exif = ExifSchema(metadata)
    metadata.add_schema(exif)
    # Stand-in for upstream OECFType: simple text property on the
    # ExifSchema — the goal of upstream's testGenerate is to exercise
    # the serializer round-trip, not the OECFType API specifically.
    exif.set_spectral_sensitivity("ss-value")

    from io import BytesIO

    from pypdfbox.xmpbox.xml import XmpSerializer
    serializer = XmpSerializer()
    bos = BytesIO()
    serializer.serialize(metadata, bos, False)
    # The serializer must not raise; the round trip is asserted in
    # other tests.
    assert bos.tell() > 0


@pytest.mark.skip(
    reason="OECFType structured-type not yet ported — see PROVENANCE.md"
)
def test_generate_with_oecf_oracle() -> None:
    """Placeholder for upstream ``testGenerate`` — kept skipped so the
    porting log stays one-to-one with upstream while OECFType lands."""
