from __future__ import annotations

from pypdfbox.cos import COSName
from tests.pdmodel.graphics.optionalcontent.test_optionalcontent_tail_wave802 import (
    _NoneNameDictionary,
)


def test_wave1119_none_name_dictionary_delegates_other_names() -> None:
    dictionary = _NoneNameDictionary()
    intent = COSName.get_pdf_name("Intent")
    dictionary.set_name(intent, "View")

    assert dictionary.get_name(intent) == "View"
    assert dictionary.get_name(COSName.get_pdf_name("Missing"), "Fallback") == "Fallback"
