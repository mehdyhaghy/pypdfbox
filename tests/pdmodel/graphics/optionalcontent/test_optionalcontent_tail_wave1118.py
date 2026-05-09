from __future__ import annotations

from pypdfbox.cos import COSName
from tests.pdmodel.graphics.optionalcontent.test_optionalcontent_tail_wave821 import (
    _EXPORT,
    _NoneNameDictionary,
)


def test_wave1118_none_name_dictionary_delegates_unrelated_names() -> None:
    dictionary = _NoneNameDictionary()

    assert dictionary.get_name(_EXPORT, "fallback") == "fallback"

    dictionary.set_item(_EXPORT, COSName.get_pdf_name("Enabled"))

    assert dictionary.get_name(_EXPORT) == "Enabled"
