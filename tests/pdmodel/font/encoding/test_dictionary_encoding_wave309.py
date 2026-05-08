from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.encoding import DictionaryEncoding


def test_set_base_encoding_rejects_unknown_string_and_preserves_state() -> None:
    enc = DictionaryEncoding(base_encoding=COSName.get_pdf_name("WinAnsiEncoding"))
    enc.set_differences({0x41: "Aacute"})
    before = enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("BaseEncoding")
    )

    with pytest.raises(ValueError, match="Invalid encoding: /BogusEncoding"):
        enc.set_base_encoding("BogusEncoding")

    assert enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("BaseEncoding")
    ) is before
    assert enc.get_base_encoding_name() == "WinAnsiEncoding"
    assert enc.get_name(0x41) == "Aacute"
    assert enc.get_name(0x61) == "a"


def test_set_base_encoding_rejects_unknown_cos_name_and_preserves_type3() -> None:
    enc = DictionaryEncoding()
    enc.set_differences({0x41: "Aacute"})

    with pytest.raises(ValueError, match="Invalid encoding: /BogusEncoding"):
        enc.set_base_encoding(COSName.get_pdf_name("BogusEncoding"))

    assert enc.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("BaseEncoding")
    ) is None
    assert enc.is_type3() is True
    assert enc.get_name(0x41) == "Aacute"
    assert enc.get_name(0x61) == ".notdef"
