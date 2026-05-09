from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from pypdfbox.pdmodel.pd_javascript_name_tree_node import PDJavascriptNameTreeNode
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pdfa_flavour import PDFAFlavour
from pypdfbox.pdmodel.pdfua_flavour import PDFUAFlavour


class _Metadata:
    def __init__(self, packet: bytes | None = None, *, raises: bool = False) -> None:
        self._packet = packet
        self._raises = raises

    def export_xmp_metadata(self) -> bytes:
        if self._raises:
            raise OSError("broken metadata stream")
        assert self._packet is not None
        return self._packet


class _Catalog:
    def __init__(self, metadata: _Metadata) -> None:
        self._metadata = metadata

    def get_metadata(self) -> _Metadata:
        return self._metadata


class _Document:
    def __init__(self, metadata: _Metadata) -> None:
        self._catalog = _Catalog(metadata)

    def get_document_catalog(self) -> _Catalog:
        return self._catalog


def test_page_tail_parent_absent_list_contents_private_fallback_and_eq() -> None:
    page = PDPage()
    stream = COSStream()
    fallback = PDRectangle(1, 2, 3, 4)

    page.set_contents([stream])

    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)

    assert page.get_cos_parent() is None
    assert isinstance(contents, COSArray)
    assert contents.size() == 1
    assert page._get_box(COSName.get_pdf_name("MissingBox"), fallback) is fallback
    assert (page == object()) is False


def test_document_information_invalid_date_and_repr_tail() -> None:
    info = PDDocumentInformation()
    info.set_title("A Title")
    info.set_author("An Author")
    info.set_property_string_value("CreationDate", "D:20261301000000Z")

    assert info.get_creation_date() is None
    assert repr(info) == "PDDocumentInformation(title='A Title', author='An Author')"


def test_pdfa_from_document_returns_none_for_broken_or_empty_metadata() -> None:
    assert PDFAFlavour.from_document(_Document(_Metadata(raises=True))) is None
    assert PDFAFlavour.from_document(_Document(_Metadata(b""))) is None


def test_pdfua_from_document_returns_none_for_broken_or_empty_metadata() -> None:
    assert PDFUAFlavour.from_document(_Document(_Metadata(raises=True))) is None
    assert PDFUAFlavour.from_document(_Document(_Metadata(b""))) is None


def test_javascript_name_tree_reads_stream_values_and_rejects_bad_shapes() -> None:
    tree = PDJavascriptNameTreeNode()
    action = COSDictionary()
    stream = COSStream()
    stream.set_data(b"app.alert('hello')")
    action.set_item(COSName.get_pdf_name("JS"), stream)

    assert tree.convert_cos_to_value(action) == "app.alert('hello')"

    with pytest.raises(OSError, match="expected a COSDictionary"):
        tree.convert_cos_to_value(COSString("not an action"))

    bad_action = COSDictionary()
    bad_action.set_item(COSName.get_pdf_name("JS"), COSName.get_pdf_name("NotScript"))
    with pytest.raises(OSError, match="Expected /JS"):
        tree.convert_cos_to_value(bad_action)
