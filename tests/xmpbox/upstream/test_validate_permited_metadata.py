"""
Ported from Apache PDFBox 3.0:
  xmpbox/src/test/java/org/apache/xmpbox/TestValidatePermitedMetadata.java

Upstream walks ``permited_metadata.txt`` and for each ``namespace +
prefix + field`` triple confirms the corresponding ``XMPSchema``
subclass is registered with the TypeMapping and that the field's
local name is declared as a Java ``@PropertyType``-annotated static
field on the schema class.

The Python port:

* Reuses the upstream ``permited_metadata.txt`` fixture verbatim
  (copied to ``tests/fixtures/xmpbox/permited_metadata.txt``).
* Walks the same triples and looks up the schema factory via
  :meth:`TypeMapping.get_schema_factory`.
* Asserts the schema's :attr:`PREFERRED_PREFIX` matches the upstream
  expectation.
* Asserts the field's local name appears as an upper-case ``str``
  class attribute on the schema (pypdfbox's ``PropertyType``-equivalent
  is a plain class constant, e.g. ``DublinCoreSchema.CONTRIBUTOR =
  "contributor"``).

Pypdfbox does not ship every PDF/A 1 permitted schema yet (XMP Rights,
PDF/X, MM history etc.), so missing schema factories are skipped on a
per-line basis rather than failing the whole suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    DublinCoreSchema,
    ExifSchema,
    PDFAExtensionSchema,
    PDFAIdentificationSchema,
    PhotoshopSchema,
    TiffSchema,
    XMPageTextSchema,
    XMPBasicJobTicketSchema,
    XMPBasicSchema,
    XMPMediaManagementSchema,
    XMPRightsManagementSchema,
)

_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "xmpbox"

# Schemas pypdfbox currently ports. Mirrors the upstream eager
# ``addNameSpace(Class)`` registrations in TypeMapping#initialize.
_REGISTERED_SCHEMAS: tuple[type, ...] = (
    AdobePDFSchema,
    DublinCoreSchema,
    ExifSchema,
    PDFAExtensionSchema,
    PDFAIdentificationSchema,
    PhotoshopSchema,
    TiffSchema,
    XMPBasicJobTicketSchema,
    XMPBasicSchema,
    XMPMediaManagementSchema,
    XMPRightsManagementSchema,
    XMPageTextSchema,
)


def _load_parameters() -> list[tuple[str, str, str]]:
    """Mirror upstream ``initializeParameters()`` — walk the text file
    and parse ``namespace/prefix:field`` lines."""
    params: list[tuple[str, str, str]] = []
    with (_FIXTURES / "permited_metadata.txt").open(
        encoding="iso-8859-1"
    ) as fh:
        for line in fh:
            line = line.rstrip("\n").rstrip("\r")
            if not line.startswith("http://"):
                continue
            pos = line.rfind(":")
            spos = line.rfind("/", 0, pos)
            namespace = line[: spos + 1]
            preferred = line[spos + 1 : pos]
            field_name = line[pos + 1 :]
            params.append((namespace, preferred, field_name))
    return params


@pytest.mark.parametrize(
    ("namespace", "preferred", "field_name"),
    _load_parameters(),
)
def test_check_existence(
    namespace: str, preferred: str, field_name: str
) -> None:
    """Translated from upstream ``checkExistence``.

    Upstream uses the rich ``XMPSchemaFactory`` (which instantiates an
    actual schema), then reflects over Java fields with ``@PropertyType``
    annotations. pypdfbox's TypeMapping ships a minimal internal
    ``_SchemaFactory`` keyed by namespace only (it carries the
    ``PropertiesDescription`` lookup but does not own schema
    construction); the rich factory lives at
    :mod:`pypdfbox.xmpbox.schema.xmp_schema_factory` and is not
    auto-registered by ``TypeMapping``.

    So this port:

    * Resolves the schema class from a namespace → class table built
      from the public surface (matches upstream's eager
      ``addNameSpace(Class)`` calls).
    * Asserts the schema's :attr:`PREFERRED_PREFIX` matches.
    * Asserts the field's local name appears as an upper-case ``str``
      class attribute on the schema (the pypdfbox equivalent of
      Java's ``@PropertyType``-annotated static fields).
    """
    cls_by_ns = {cls.NAMESPACE: cls for cls in _REGISTERED_SCHEMAS}
    schema_cls = cls_by_ns.get(namespace)
    # Every namespace in ``permited_metadata.txt`` resolves to a registered
    # schema port. Assertion replaces the wave-1377-era ``pytest.skip``
    # placeholder, which was inherited from the period when several PDF/A 1
    # schemas were unported.
    assert schema_cls is not None, (
        f"Schema namespace {namespace!r} has no port in _REGISTERED_SCHEMAS"
    )

    # Mirror upstream's ``getPreferedPrefix()`` check.
    assert preferred == schema_cls.PREFERRED_PREFIX

    # Mirror upstream's reflection loop.
    found = False
    for attr_name in dir(schema_cls):
        if not attr_name.isupper():
            continue
        if attr_name.startswith("_"):
            continue
        value = getattr(schema_cls, attr_name, None)
        if isinstance(value, str) and value == field_name:
            found = True
            break

    # Every field listed for a registered schema is declared as a class-level
    # constant in the pypdfbox port (matches upstream's
    # ``@PropertyType``-annotated static fields). Assertion replaces the
    # previously dead ``pytest.skip`` placeholder.
    assert found, (
        f"Schema {schema_cls.__name__} does not declare {field_name!r} "
        "as a class-level constant"
    )
