from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.encoding import DictionaryEncoding


def test_reader_symbolic_without_built_in_encoding_raises() -> None:
    font_enc = COSDictionary()
    font_enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))

    with pytest.raises(
        ValueError, match="Symbolic fonts must have a built-in encoding"
    ):
        DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=False)


def test_reader_symbolic_unknown_base_without_built_in_encoding_raises() -> None:
    font_enc = COSDictionary()
    font_enc.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding"))
    font_enc.set_item(
        COSName.get_pdf_name("BaseEncoding"),
        COSName.get_pdf_name("BogusEncoding"),
    )

    with pytest.raises(
        ValueError, match="Symbolic fonts must have a built-in encoding"
    ):
        DictionaryEncoding(font_encoding=font_enc, is_non_symbolic=False)
