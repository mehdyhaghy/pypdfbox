"""Coverage boost for :mod:`pypdfbox.pdmodel.fdf.fdf_annotation_stamp`.

Targets the XFDF appearance-XML helpers (``parse_*_element`` /
``parse_stamp_annotation_appearance_xml``) which the original test
module does not exercise.
"""

from __future__ import annotations

import base64
from xml.etree.ElementTree import Element, SubElement

from pypdfbox.cos import COSArray, COSDictionary, COSStream
from pypdfbox.pdmodel.fdf import FDFAnnotationStamp


def test_parse_stamp_annotation_appearance_xml_empty_returns_none() -> None:
    stamp = FDFAnnotationStamp()
    assert stamp.parse_stamp_annotation_appearance_xml("") is None


def test_parse_stamp_annotation_appearance_xml_invalid_base64_returns_none() -> None:
    stamp = FDFAnnotationStamp()
    # Single char is an invalid base64 length; b64decode raises
    # binascii.Error (subclass of ValueError) which the helper catches.
    assert stamp.parse_stamp_annotation_appearance_xml("A") is None


def test_parse_stamp_annotation_appearance_xml_decodes_payload() -> None:
    stamp = FDFAnnotationStamp()
    payload = b"<xml/>"
    encoded = base64.b64encode(payload).decode("utf-8")
    result = stamp.parse_stamp_annotation_appearance_xml(encoded)
    assert isinstance(result, COSDictionary)
    normal = result.get_dictionary_object("N")
    assert isinstance(normal, COSStream)


def test_parse_dict_element_none_returns_none() -> None:
    stamp = FDFAnnotationStamp()
    assert stamp.parse_dict_element(None) is None


def test_parse_dict_element_text_children() -> None:
    stamp = FDFAnnotationStamp()
    root = Element("dict")
    child = SubElement(root, "string", {"KEY": "Foo"})
    child.text = "hello"
    # Child without a KEY attribute should be skipped silently.
    SubElement(root, "string").text = "ignored"
    result = stamp.parse_dict_element(root)
    assert isinstance(result, COSDictionary)
    assert result.get_dictionary_object("Foo") == "hello"


def test_parse_dict_element_nested_dict_and_array() -> None:
    stamp = FDFAnnotationStamp()
    root = Element("dict")
    inner_dict = SubElement(root, "dict", {"KEY": "Inner"})
    SubElement(inner_dict, "string", {"KEY": "Bar"}).text = "baz"
    inner_array = SubElement(root, "array", {"KEY": "List"})
    SubElement(inner_array, "string").text = "one"
    SubElement(inner_array, "string").text = "two"
    result = stamp.parse_dict_element(root)
    assert isinstance(result, COSDictionary)
    inner = result.get_dictionary_object("Inner")
    assert isinstance(inner, COSDictionary)
    arr = result.get_dictionary_object("List")
    assert isinstance(arr, COSArray)


def test_parse_dict_element_stream_child() -> None:
    stamp = FDFAnnotationStamp()
    root = Element("dict")
    stream_el = SubElement(root, "stream", {"KEY": "Body"})
    stream_el.text = base64.b64encode(b"abc").decode("utf-8")
    result = stamp.parse_dict_element(root)
    assert isinstance(result, COSDictionary)
    body = result.get_dictionary_object("Body")
    assert isinstance(body, COSStream)


def test_parse_array_element_none_returns_none() -> None:
    stamp = FDFAnnotationStamp()
    assert stamp.parse_array_element(None) is None


def test_parse_array_element_mixed_children() -> None:
    stamp = FDFAnnotationStamp()
    root = Element("array")
    SubElement(root, "string").text = "alpha"
    inner_dict = SubElement(root, "dict")
    SubElement(inner_dict, "string", {"KEY": "K"}).text = "v"
    inner_array = SubElement(root, "array")
    SubElement(inner_array, "string").text = "nested"
    stream_el = SubElement(root, "stream")
    stream_el.text = base64.b64encode(b"xx").decode("utf-8")
    result = stamp.parse_array_element(root)
    assert isinstance(result, COSArray)
    assert len(result) == 4


def test_parse_stream_element_none_returns_none() -> None:
    stamp = FDFAnnotationStamp()
    assert stamp.parse_stream_element(None) is None


def test_parse_stream_element_empty_text_returns_empty_stream() -> None:
    stamp = FDFAnnotationStamp()
    el = Element("stream")
    el.text = None
    result = stamp.parse_stream_element(el)
    assert isinstance(result, COSStream)


def test_parse_stream_element_invalid_base64_returns_none() -> None:
    stamp = FDFAnnotationStamp()
    el = Element("stream")
    el.text = "A"  # invalid base64 length
    assert stamp.parse_stream_element(el) is None


def test_parse_stream_element_decodes_payload() -> None:
    stamp = FDFAnnotationStamp()
    el = Element("stream")
    el.text = base64.b64encode(b"payload").decode("utf-8")
    result = stamp.parse_stream_element(el)
    assert isinstance(result, COSStream)


def test_constructor_with_existing_subtype_preserves_it() -> None:
    annot = COSDictionary()
    from pypdfbox.cos import COSName

    annot.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Stamp"))
    stamp = FDFAnnotationStamp(annot)
    assert stamp.get_cos_object().get_name_as_string("Subtype") == "Stamp"
