from __future__ import annotations

from pypdfbox.cos import COSName
from tests.pdmodel.graphics.optionalcontent.test_tail_sweep_wave842 import (
    _NoneBaseStateDictionary,
)


def test_wave1116_none_base_state_dictionary_delegates_non_base_state_names() -> None:
    dictionary = _NoneBaseStateDictionary()
    print_state = COSName.get_pdf_name("PrintState")
    dictionary.set_item(print_state, COSName.get_pdf_name("ON"))

    assert dictionary.get_name(print_state) == "ON"
