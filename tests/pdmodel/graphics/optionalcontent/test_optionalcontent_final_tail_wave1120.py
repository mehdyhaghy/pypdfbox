from __future__ import annotations

from pypdfbox.cos import COSName
from tests.pdmodel.graphics.optionalcontent.test_optionalcontent_final_tail_wave831 import (
    _NoneBaseStateDictionary,
)


def test_wave1120_none_base_state_dictionary_delegates_other_names() -> None:
    dictionary = _NoneBaseStateDictionary()
    intent = COSName.get_pdf_name("Intent")
    dictionary.set_name(intent, "View")

    assert dictionary.get_name(intent) == "View"
    assert dictionary.get_name(COSName.get_pdf_name("Missing"), "Fallback") == "Fallback"
