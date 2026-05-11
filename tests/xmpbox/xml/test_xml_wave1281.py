"""Hand-written tests for ``pypdfbox.xmpbox.xml``."""

from __future__ import annotations

import io
from xml.dom.minidom import parseString

import pytest

from pypdfbox.xmpbox.xml.dom_helper import DomHelper
from pypdfbox.xmpbox.xml.namespace_finder import NamespaceFinder
from pypdfbox.xmpbox.xml.pdfa_extension_helper import PdfaExtensionHelper
from pypdfbox.xmpbox.xml.xmp_serializer import XmpSerializer


def test_dom_helper_first_and_unique_child() -> None:
    doc = parseString("<root><a/><b/></root>")
    root = doc.documentElement
    first = DomHelper.get_first_child_element(root)
    assert first is not None
    assert first.localName == "a"
    children = DomHelper.get_element_children(root)
    assert [c.localName for c in children] == ["a", "b"]


def test_dom_helper_unique_child_rejects_two() -> None:
    doc = parseString("<root><a/><b/></root>")
    root = doc.documentElement
    with pytest.raises(OSError):
        DomHelper.get_unique_element_child(root)


def test_dom_helper_unique_child_returns_singleton() -> None:
    doc = parseString("<root><a/></root>")
    root = doc.documentElement
    only = DomHelper.get_unique_element_child(root)
    assert only is not None and only.localName == "a"


def test_dom_helper_is_rdf_description() -> None:
    xml = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description/></rdf:RDF>'
    )
    doc = parseString(xml)
    desc = doc.documentElement.firstChild
    assert DomHelper.is_rdf_description(desc)


def test_dom_helper_is_parse_type_resource() -> None:
    xml = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<x:val rdf:parseType="Resource" xmlns:x="urn:x"/>'
        '</rdf:RDF>'
    )
    doc = parseString(xml)
    val = doc.documentElement.firstChild
    assert DomHelper.is_parse_type_resource(val)


def test_namespace_finder_stack() -> None:
    xml = (
        '<root xmlns:a="urn:a" xmlns:b="urn:b"><inner xmlns:c="urn:c"/></root>'
    )
    doc = parseString(xml)
    finder = NamespaceFinder()
    finder.push(doc.documentElement)
    assert finder.contains_namespace("urn:a")
    finder.push(doc.documentElement.firstChild)
    assert finder.contains_namespace("urn:c")
    popped = finder.pop()
    assert "c" in popped
    assert not finder.contains_namespace("urn:c")


def test_pdfa_extension_helper_constants() -> None:
    assert PdfaExtensionHelper.CLOSED_CHOICE == "closed Choice of "
    assert PdfaExtensionHelper.OPEN_CHOICE_U == "Open Choice of "


def test_pdfa_extension_helper_validate_naming_ok() -> None:
    xml = (
        '<rdf:Description '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"/>'
    )
    doc = parseString(xml)
    PdfaExtensionHelper.validate_naming(None, doc.documentElement)


def test_pdfa_extension_helper_validate_naming_bad_prefix() -> None:
    xml = (
        '<rdf:Description '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:bogus="http://www.aiim.org/pdfa/ns/extension/"/>'
    )
    doc = parseString(xml)
    with pytest.raises(OSError):
        PdfaExtensionHelper.validate_naming(None, doc.documentElement)


def test_xmp_serializer_writes_packet() -> None:
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata

    metadata = XMPMetadata.create_xmp_metadata()
    output = io.BytesIO()
    XmpSerializer().serialize(metadata, output, with_xpacket=True)
    blob = output.getvalue()
    assert b"xmpmeta" in blob
    assert b"rdf:RDF" in blob
