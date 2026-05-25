"""Wave 1397 branch-coverage tests for ``XmpSerializer``.

Closes False-branch arrows where ``serialize_schema`` and ``serialize_fields``
walk an unusual schema / array shape:

* ``serialize_schema`` 65->67 — schema returns no prefix and/or no namespace
* ``serialize_fields`` 242->249 — array child is neither simple nor
  complex/structured (e.g. a bare ``AbstractField`` subclass)
* ``serialize_fields`` 251->258 — top-level field is neither simple nor
  array nor complex/structured
"""

from __future__ import annotations

from xml.dom.minidom import Document

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type.abstract_field import AbstractField
from pypdfbox.xmpbox.type.array_property import ArrayProperty, Cardinality
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer


class _StubSchema:
    """Schema that provides only the bare minimum surface — no
    ``get_prefix`` / ``get_namespace`` overrides → both return None."""

    def __init__(self, md: XMPMetadata) -> None:
        self._metadata = md

    def get_about_value(self) -> str:
        return ""

    def get_all_properties(self) -> list[object]:
        return []

    def get_prefix(self) -> None:
        return None

    def get_namespace(self) -> None:
        return None


class _BareField(AbstractField):
    """An AbstractField that is NOT a simple / array / complex /
    structured type — exercises the fall-through path in
    ``serialize_fields`` that drops straight to ``parent.appendChild``."""

    def __init__(self, md: XMPMetadata, prop_name: str) -> None:
        # AbstractField is abstract; concrete subclasses provide
        # get_namespace + get_prefix. We add them here so the serialiser
        # can build a fully-qualified tag.
        super().__init__(md, prop_name)

    def get_namespace(self) -> str | None:
        return "http://example.org/bare/"

    def get_prefix(self) -> str | None:
        return "p"


def test_serialize_schema_without_prefix_or_namespace_skips_xmlns() -> None:
    """Closes 65->67: a schema whose get_prefix() returns None — the
    ``selem.setAttributeNS(xmlns:...)`` branch is skipped."""
    md = XMPMetadata.create_xmp_metadata()
    serializer = XmpSerializer()
    doc = Document()
    selem = serializer.serialize_schema(doc, _StubSchema(md))
    # The synthesized Description element exists.
    assert selem.tagName == "rdf:Description"
    # No xmlns attribute was set on it (since prefix is None).
    has_xmlns = any(
        attr.startswith("xmlns:")
        for attr in (selem.attributes.keys() if selem.attributes else [])
    )
    assert has_xmlns is False


def test_serialize_fields_array_with_non_simple_non_complex_child() -> None:
    """Closes 242->249: an ArrayProperty whose ``li`` is a plain
    AbstractField (neither simple, nor complex/structured) — the
    serialiser must still emit the li element."""
    md = XMPMetadata.create_xmp_metadata()
    serializer = XmpSerializer()
    doc = Document()
    parent = doc.createElement("parent")

    array = ArrayProperty(md, "http://example/", "ex", "BareBag", Cardinality.Bag)
    array.add_property(_BareField(md, "entry"))

    serializer.serialize_fields(doc, parent, [array], None, None, True)
    # The array element was appended; its single <rdf:li> child has no
    # text content (neither simple text node nor sub-properties were
    # added — the branch fell through cleanly).
    assert parent.getElementsByTagName("ex:BareBag")
    li_elements = parent.getElementsByTagName("rdf:li")
    assert len(li_elements) == 1
    # No text content was added — the simple/complex branches both skipped.
    assert li_elements[0].firstChild is None


def test_serialize_fields_top_level_bare_field_falls_through() -> None:
    """Closes 251->258: a top-level AbstractField that isn't simple /
    array / complex / structured — the serialiser appends an empty
    element and skips the text/sub-field branches."""
    md = XMPMetadata.create_xmp_metadata()
    serializer = XmpSerializer()
    doc = Document()
    parent = doc.createElement("parent")

    serializer.serialize_fields(doc, parent, [_BareField(md, "bare")], None, None, True)
    # The bare element was appended (under prefix ``p`` because that's
    # what _BareField declares).
    children = parent.getElementsByTagName("p:bare")
    assert len(children) == 1
    # No text node was attached.
    assert children[0].firstChild is None
