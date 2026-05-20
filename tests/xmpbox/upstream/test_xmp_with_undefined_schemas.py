"""Port of xmpbox/src/test/java/org/apache/xmpbox/TestXMPWithUndefinedSchemas.java

Upstream baseline: PDFBox 3.0.x. Fixture bundled under
``tests/fixtures/xmpbox/undefinedxmp/``.

Parametrised round-trip parsing of XMP packets carrying schemas not
known to xmpbox — the parser must still expose the unknown namespace,
property, and value in non-strict mode.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.xmpbox import DomXmpParser

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "xmpbox" / "undefinedxmp"


@pytest.mark.parametrize(
    "path,namespace,property_name,property_value",
    [
        (
            "prism.xmp",
            "http://prismstandard.org/namespaces/basic/2.0/",
            "aggregationType",
            "journal",
        ),
    ],
)
def test_main(path: str, namespace: str, property_name: str, property_value: str) -> None:
    builder = DomXmpParser()
    builder.set_strict_parsing(False)
    fixture_path = _FIXTURES / path
    with fixture_path.open("rb") as is_:
        rxmp = builder.parse(is_)
    # ensure basic parsing was OK
    assert rxmp.get_all_schemas(), "There should be a least one schema"
    schema = rxmp.get_schema(namespace)
    assert schema is not None, f"The schema for {{{namespace}}} should be available"
    prop = schema.get_property(property_name)
    assert prop is not None, (
        f"The schema for {{{namespace}}} should have a property {{{property_name}}} "
    )
    # Upstream returns an ``AbstractField`` whose ``getPropertyName()``
    # equals ``property_name``. pypdfbox stores property values as raw
    # strings on the ``XMPSchema``; the property-name parity check is
    # therefore expressed as a ``has_property`` lookup.
    assert schema.has_property(property_name), (
        f"The schema for {{{namespace}}} should have a property {{{property_name}}} "
    )
    assert schema.get_unqualified_text_property_value(property_name) == property_value, (
        f"The property {{{property_name}}} should have a value of {{{property_value}}}"
    )
