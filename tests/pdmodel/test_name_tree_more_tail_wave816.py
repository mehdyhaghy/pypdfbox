from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDFieldStub, PDFieldTree
from pypdfbox.pdmodel.pd_alternate_presentations_name_tree_node import (
    PDAlternatePresentationsNameTreeNode,
)
from pypdfbox.pdmodel.pd_ids_name_tree_node import PDIDSNameTreeNode
from pypdfbox.pdmodel.pd_pages_name_tree_node import PDPagesNameTreeNode
from pypdfbox.pdmodel.pd_renditions_name_tree_node import PDRenditionsNameTreeNode
from pypdfbox.pdmodel.pd_templates_name_tree_node import PDTemplatesNameTreeNode
from pypdfbox.pdmodel.pd_urls_name_tree_node import PDURLSNameTreeNode


class _NonTerminalStub(PDFieldStub):
    def is_terminal(self) -> bool:
        return False


class _FormWithRawFields:
    def __init__(self, fields: list[PDFieldStub]) -> None:
        self._fields = fields

    def get_fields(self) -> list[PDFieldStub]:
        return self._fields


def test_field_tree_keeps_non_terminal_field_that_is_not_non_terminal_wrapper() -> None:
    form = PDAcroForm()
    field = _NonTerminalStub(form)
    field.set_partial_name("looks-like-parent")
    tree = PDFieldTree(_FormWithRawFields([field]))  # type: ignore[arg-type]

    assert [item.get_fully_qualified_name() for item in tree] == ["looks-like-parent"]


@pytest.mark.parametrize(
    ("tree_cls", "expected"),
    [
        (PDAlternatePresentationsNameTreeNode, "AlternatePresentations"),
        (PDPagesNameTreeNode, "Pages"),
        (PDRenditionsNameTreeNode, "Renditions"),
        (PDTemplatesNameTreeNode, "Templates"),
        (PDURLSNameTreeNode, "URLS"),
    ],
)
def test_dictionary_name_tree_leaf_converters_reject_cos_strings(
    tree_cls: type[
        PDAlternatePresentationsNameTreeNode
        | PDPagesNameTreeNode
        | PDRenditionsNameTreeNode
        | PDTemplatesNameTreeNode
        | PDURLSNameTreeNode
    ],
    expected: str,
) -> None:
    tree = tree_cls()

    with pytest.raises(OSError, match=rf"Expected dictionary for /{expected}"):
        tree.convert_cos_to_value(COSString("wrong"))


def test_ids_name_tree_leaf_converter_rejects_non_string_values() -> None:
    tree = PDIDSNameTreeNode()

    with pytest.raises(OSError, match=r"Expected string for /IDS"):
        tree.convert_cos_to_value(COSDictionary())
