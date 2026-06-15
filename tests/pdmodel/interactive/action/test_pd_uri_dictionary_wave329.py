from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDURIDictionary

_BASE = COSName.get_pdf_name("Base")


def test_wave329_uri_dictionary_base_decodes_non_bom_as_pdfdocencoding() -> None:
    # Wave 1530: upstream ``PDURIDictionary.getBase`` delegates to
    # ``COSDictionary.getString(Base)`` → ``COSString.getString()`` (PDFDocEncoding
    # for a non-BOM byte string), NOT the UTF-8 tolerance ``PDActionURI.getURI``
    # applies to ``/URI``. The live PDFBox 3.0.7 oracle confirms the high bytes
    # 0xC3 0xA9 decode per-byte to "Ã©" (PDFDocEncoding), not the UTF-8 "é".
    raw = COSDictionary()
    raw.set_item(_BASE, COSString(b"https://example.test/caf\xc3\xa9/"))

    uri_dict = PDURIDictionary(raw)

    assert uri_dict.get_base() == "https://example.test/cafÃ©/"


def test_wave329_uri_dictionary_base_decodes_utf16_with_bom() -> None:
    raw = COSDictionary()
    payload = "https://example.test/é/".encode("utf-16-be")
    raw.set_item(_BASE, COSString(b"\xfe\xff" + payload))

    uri_dict = PDURIDictionary(raw)

    assert uri_dict.get_base() == "https://example.test/é/"
