from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink


def test_has_destination_ignores_malformed_dest_entry() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("Dest"), COSInteger.get(7))
    annotation = PDAnnotationLink(dictionary)

    assert annotation.has_destination() is False
    with pytest.raises(OSError, match="Cannot convert to PDDestination"):
        annotation.get_destination()


def test_has_destination_accepts_named_string_without_factory_dispatch() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("Dest"), COSString("Chapter1"))
    annotation = PDAnnotationLink(dictionary)

    assert annotation.has_destination() is True
