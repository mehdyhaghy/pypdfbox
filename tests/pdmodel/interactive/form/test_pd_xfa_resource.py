from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from pypdfbox.cos import COSArray, COSStream, COSString
from pypdfbox.pdmodel.interactive.form.pd_xfa_resource import PDXFAResource


def _stream(body: bytes) -> COSStream:
    s = COSStream()
    s.set_raw_data(body)
    return s


def test_get_bytes_from_cos_stream() -> None:
    body = b"<xfa>...</xfa>"
    xfa = PDXFAResource(_stream(body))

    assert xfa.get_bytes() == body
    assert xfa.get_cos_object().__class__.__name__ == "COSStream"


def test_get_bytes_from_tagged_packet_array() -> None:
    arr = COSArray()
    arr.add(COSString("preamble"))
    arr.add(_stream(b"<a/>"))
    arr.add(COSString("config"))
    arr.add(_stream(b"<b/>"))

    xfa = PDXFAResource(arr)

    assert xfa.get_bytes() == b"<a/><b/>"
    assert xfa.get_cos_object() is arr


def test_get_bytes_returns_empty_for_unsupported_cos_type() -> None:
    xfa = PDXFAResource(COSString("just a string"))
    assert xfa.get_bytes() == b""


def test_is_dynamic_detects_marker() -> None:
    xfa = PDXFAResource(_stream(b'<xdp:xdp xmlns:xdp="..."><xfa:datasets/></xdp:xdp>'))
    assert xfa.is_dynamic() is True


def test_is_dynamic_false_for_plain_payload() -> None:
    xfa = PDXFAResource(_stream(b"<plain/>"))
    assert xfa.is_dynamic() is False


def test_is_dynamic_false_for_empty_xfa() -> None:
    xfa = PDXFAResource(COSArray())
    assert xfa.is_dynamic() is False


def test_get_document_from_cos_stream() -> None:
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><foo/></xdp:xdp>'
    xfa = PDXFAResource(_stream(body))

    root = xfa.get_document()

    assert isinstance(root, ET.Element)
    assert root.tag == "{http://ns.adobe.com/xdp/}xdp"
    assert len(list(root)) == 1
    assert root[0].tag == "foo"


def test_get_document_from_tagged_packet_array() -> None:
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(_stream(b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">'))
    arr.add(COSString("datasets"))
    arr.add(_stream(b"<template/>"))
    arr.add(COSString("form"))
    arr.add(_stream(b"<datasets/>"))
    arr.add(COSString("config"))
    arr.add(_stream(b"</xdp:xdp>"))
    xfa = PDXFAResource(arr)

    root = xfa.get_document()

    assert root.tag == "{http://ns.adobe.com/xdp/}xdp"
    child_tags = [child.tag for child in root]
    assert child_tags == ["template", "datasets"]


def test_get_document_is_cached() -> None:
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><foo/></xdp:xdp>'
    xfa = PDXFAResource(_stream(body))

    first = xfa.get_document()
    second = xfa.get_document()

    assert first is second


def test_get_document_propagates_parse_error_on_malformed_xml() -> None:
    xfa = PDXFAResource(_stream(b"<not-closed>"))

    with pytest.raises(ET.ParseError):
        xfa.get_document()


def test_get_document_as_xml_returns_decoded_payload() -> None:
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><foo/></xdp:xdp>'
    xfa = PDXFAResource(_stream(body))

    assert xfa.get_document_as_xml() == body.decode(encoding="utf-8")


def test_get_document_as_xml_concatenates_array_form() -> None:
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(_stream(b"<a>"))
    arr.add(COSString("datasets"))
    arr.add(_stream(b"<b/></a>"))
    xfa = PDXFAResource(arr)

    assert xfa.get_document_as_xml() == "<a><b/></a>"
