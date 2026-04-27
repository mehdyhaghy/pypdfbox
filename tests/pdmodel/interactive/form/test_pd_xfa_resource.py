from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from pypdfbox.cos import COSArray, COSName, COSStream, COSString
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


def test_is_dynamic_false_for_static_position_layout() -> None:
    body = (
        b'<xdp xmlns="http://ns.adobe.com/xdp/">'
        b"<template>"
        b'<subform name="form1" layout="position"/>'
        b"</template>"
        b"</xdp>"
    )
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is False


def test_is_dynamic_true_for_tb_layout() -> None:
    body = (
        b'<xdp xmlns="http://ns.adobe.com/xdp/">'
        b"<template>"
        b'<subform name="form1" layout="tb"/>'
        b"</template>"
        b"</xdp>"
    )
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is True


def test_is_dynamic_true_for_namespaced_template_and_subform() -> None:
    body = (
        b'<xdp xmlns="http://ns.adobe.com/xdp/" '
        b'xmlns:tpl="http://www.xfa.org/schema/xfa-template/3.3/">'
        b"<tpl:template>"
        b'<tpl:subform name="form1" layout="lr-tb"/>'
        b"</tpl:template>"
        b"</xdp>"
    )
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is True


def test_is_dynamic_false_when_layout_attribute_absent() -> None:
    body = (
        b'<xdp xmlns="http://ns.adobe.com/xdp/">'
        b"<template>"
        b'<subform name="form1"/>'
        b"</template>"
        b"</xdp>"
    )
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is False


def test_is_dynamic_falls_back_to_substring_on_malformed_xml() -> None:
    # Unbalanced tags + an undeclared xfa: prefix make this a hard parse error,
    # but the legacy <xdp:xdp marker should still trigger the heuristic.
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><xfa:datasets/>'
    xfa = PDXFAResource(_stream(body))

    # Must not raise.
    assert xfa.is_dynamic() is True


def test_is_dynamic_falls_back_to_substring_when_no_template_packet() -> None:
    # Parses fine, but there is no <template> packet — the heuristic kicks in
    # and finds 'subform name="form1"' even though no layout was declared.
    body = b'<xdp xmlns="http://ns.adobe.com/xdp/"><config><subform name="form1"/></config></xdp>'
    xfa = PDXFAResource(_stream(body))

    assert xfa.is_dynamic() is True


def test_is_dynamic_is_cached() -> None:
    body = (
        b'<xdp xmlns="http://ns.adobe.com/xdp/">'
        b"<template>"
        b'<subform name="form1" layout="tb"/>'
        b"</template>"
        b"</xdp>"
    )
    xfa = PDXFAResource(_stream(body))

    first = xfa.is_dynamic()
    # Mutate the underlying stream after the first call: the cached result
    # must not be recomputed.
    xfa._xfa.set_raw_data(b"<plain/>")  # type: ignore[union-attr]
    second = xfa.is_dynamic()

    assert first is True
    assert second is True
    assert first == second


# ---------- get_xfa_packet ----------


def test_get_xfa_packet_returns_named_stream_body() -> None:
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(_stream(b"<template-body/>"))
    arr.add(COSString("datasets"))
    arr.add(_stream(b"<datasets-body/>"))
    arr.add(COSString("config"))
    arr.add(_stream(b"<config-body/>"))
    xfa = PDXFAResource(arr)

    assert xfa.get_xfa_packet("template") == b"<template-body/>"
    assert xfa.get_xfa_packet("datasets") == b"<datasets-body/>"
    assert xfa.get_xfa_packet("config") == b"<config-body/>"


def test_get_xfa_packet_accepts_cos_name_label() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("form"))
    arr.add(_stream(b"<form-body/>"))
    xfa = PDXFAResource(arr)

    assert xfa.get_xfa_packet("form") == b"<form-body/>"


def test_get_xfa_packet_returns_none_when_label_missing() -> None:
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(_stream(b"<template-body/>"))
    xfa = PDXFAResource(arr)

    assert xfa.get_xfa_packet("datasets") is None


def test_get_xfa_packet_returns_none_for_single_stream_form() -> None:
    xfa = PDXFAResource(_stream(b"<xdp/>"))

    assert xfa.get_xfa_packet("datasets") is None


def test_get_xfa_packet_returns_none_when_paired_entry_not_stream() -> None:
    # Malformed pair: label is correct but the slot after it is a string,
    # not a stream.
    arr = COSArray()
    arr.add(COSString("template"))
    arr.add(COSString("not-a-stream"))
    xfa = PDXFAResource(arr)

    assert xfa.get_xfa_packet("template") is None


def test_get_xfa_packet_handles_unpaired_trailing_label() -> None:
    arr = COSArray()
    arr.add(COSString("template"))  # no following stream — odd-length array
    xfa = PDXFAResource(arr)

    assert xfa.get_xfa_packet("template") is None


# ---------- get_dom_document ----------


def test_get_dom_document_returns_element_tree() -> None:
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><foo/></xdp:xdp>'
    xfa = PDXFAResource(_stream(body))

    tree = xfa.get_dom_document()

    assert isinstance(tree, ET.ElementTree)
    root = tree.getroot()
    assert root.tag == "{http://ns.adobe.com/xdp/}xdp"
    assert [child.tag for child in root] == ["foo"]


def test_get_dom_document_returns_none_for_empty_payload() -> None:
    xfa = PDXFAResource(COSArray())

    assert xfa.get_dom_document() is None


def test_get_dom_document_returns_none_for_malformed_xml() -> None:
    xfa = PDXFAResource(_stream(b"<not-closed>"))

    assert xfa.get_dom_document() is None


def test_get_dom_document_shares_root_with_get_document() -> None:
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><foo/></xdp:xdp>'
    xfa = PDXFAResource(_stream(body))

    tree = xfa.get_dom_document()
    assert tree is not None
    root_via_tree = tree.getroot()
    root_via_element = xfa.get_document()

    assert root_via_tree is root_via_element


def test_get_dom_document_after_get_document_uses_cached_root() -> None:
    body = b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/"><foo/></xdp:xdp>'
    xfa = PDXFAResource(_stream(body))

    cached = xfa.get_document()
    tree = xfa.get_dom_document()

    assert tree is not None
    assert tree.getroot() is cached
