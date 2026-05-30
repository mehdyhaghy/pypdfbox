from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import PDDeveloperExtension, PDPageTree, PDRectangle
from pypdfbox.pdmodel import pd_page_content_stream as content_stream_module
from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
    PDDocumentNameDestinationDictionary,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary


def test_rectangle_repr_reports_all_four_coordinates() -> None:
    assert repr(PDRectangle(1.0, 2.0, 3.0, 4.0)) == (
        "PDRectangle(1.0, 2.0, 3.0, 4.0)"
    )


def test_page_tree_getitem_rejects_non_integer_index() -> None:
    tree = PDPageTree()

    with pytest.raises(TypeError, match="indices must be int"):
        tree["0"]  # type: ignore[index]


def test_format_number_matches_pdfbox_float_fast_path() -> None:
    # PDFBox formats operands through float32 + formatFloatFast (max 5 frac
    # digits, half-up on the narrowed fraction). 0.125 is exactly
    # representable, so it round-trips as "0.125".
    assert content_stream_module._format_number(0.125) == b"0.125"


def test_dictionary_wrappers_expose_cos_dictionary_aliases() -> None:
    names = COSDictionary()
    dests = COSDictionary()
    extension = COSDictionary()

    name_dictionary = PDDocumentNameDictionary(names=names)
    destination_dictionary = PDDocumentNameDestinationDictionary(dests)
    developer_extension = PDDeveloperExtension(extension)

    assert name_dictionary.get_cos_dictionary() is names
    assert destination_dictionary.get_cos_dictionary() is dests
    assert developer_extension.get_cos_dictionary() is extension
