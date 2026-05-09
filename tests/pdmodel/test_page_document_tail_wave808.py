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


def test_format_number_normalizes_empty_formatted_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        content_stream_module,
        "format",
        lambda _value, _spec: "",
        raising=False,
    )

    assert content_stream_module._format_number(0.125) == b"0"


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
