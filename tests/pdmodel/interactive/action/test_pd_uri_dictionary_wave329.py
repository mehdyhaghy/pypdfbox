from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDURIDictionary

_BASE = COSName.get_pdf_name("Base")


def test_wave329_uri_dictionary_base_decodes_utf8_without_bom() -> None:
    raw = COSDictionary()
    raw.set_item(_BASE, COSString(b"https://example.test/caf\xc3\xa9/"))

    uri_dict = PDURIDictionary(raw)

    assert uri_dict.get_base() == "https://example.test/café/"


def test_wave329_uri_dictionary_base_decodes_utf16_with_bom() -> None:
    raw = COSDictionary()
    payload = "https://example.test/é/".encode("utf-16-be")
    raw.set_item(_BASE, COSString(b"\xfe\xff" + payload))

    uri_dict = PDURIDictionary(raw)

    assert uri_dict.get_base() == "https://example.test/é/"
