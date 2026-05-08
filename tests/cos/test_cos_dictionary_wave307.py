from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSObject, COSString


def test_get_name_as_string_accepts_names_and_strings() -> None:
    dictionary = COSDictionary(
        [
            ("Type", COSName.get_pdf_name("Page")),
            ("Title", COSString("Chapter 1")),
        ]
    )

    assert dictionary.get_name_as_string("Type") == "Page"
    assert dictionary.get_name_as_string("Title") == "Chapter 1"


def test_get_name_as_string_resolves_indirect_values() -> None:
    dictionary = COSDictionary(
        [
            ("Subtype", COSObject(1, 0, resolved=COSName.get_pdf_name("Widget"))),
            ("Alternate", COSObject(2, 0, resolved=COSString("Print"))),
        ]
    )

    assert dictionary.get_name_as_string("Subtype") == "Widget"
    assert dictionary.get_name_as_string("Alternate") == "Print"


def test_get_name_as_string_defaults_for_missing_or_wrong_shape() -> None:
    dictionary = COSDictionary([("Count", COSInteger.get(3))])

    assert dictionary.get_name_as_string("Missing") is None
    assert dictionary.get_name_as_string("Missing", "fallback") == "fallback"
    assert dictionary.get_name_as_string("Count", "fallback") == "fallback"


def test_camelcase_get_name_as_string_alias_delegates() -> None:
    dictionary = COSDictionary([("Type", COSString("Annot"))])

    assert dictionary.getNameAsString("Type") == "Annot"
    assert dictionary.getNameAsString("Missing", "fallback") == "fallback"
