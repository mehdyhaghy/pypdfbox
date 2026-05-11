from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import FDFPageInfo


def test_default_constructor_empty_dict() -> None:
    info = FDFPageInfo()
    assert isinstance(info.get_cos_object(), COSDictionary)
    assert info.get_cos_object().size() == 0


def test_existing_dictionary_preserved() -> None:
    dictionary = COSDictionary()
    dictionary.set_name("Hint", "x")
    info = FDFPageInfo(dictionary)
    assert info.get_cos_object() is dictionary
