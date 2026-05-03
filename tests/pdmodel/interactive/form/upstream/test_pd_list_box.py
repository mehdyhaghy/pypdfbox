"""Subset ported from upstream PDFBox 3.0 ``TestListBox``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestListBox.java``

Skipped upstream cases:
- PDF write/annotation resource setup — covered by pypdfbox appearance tests.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

_OPT: COSName = COSName.get_pdf_name("Opt")
_TI: COSName = COSName.get_pdf_name("TI")


@pytest.fixture
def export_values() -> list[str]:
    return ["export01", "export02", "export03"]


@pytest.fixture
def display_values() -> list[str]:
    return ["display02", "display01", "display03"]


@pytest.fixture
def choice() -> PDListBox:
    return PDListBox(PDAcroForm())


def test_no_nulls_returned(choice: PDListBox) -> None:
    """Upstream: ``testNoNullsReturned``."""
    assert choice.get_options() is not None
    assert choice.get_value() is not None


def test_top_index_getter_setter(choice: PDListBox) -> None:
    """Covers upstream ``getTopIndex`` / ``setTopIndex``."""
    assert "get_top_index" in PDListBox.__dict__
    assert "set_top_index" in PDListBox.__dict__
    assert choice.get_top_index() == 0

    choice.set_top_index(1)
    assert choice.get_top_index() == 1
    assert choice.get_cos_object().get_int(_TI, 0) == 1

    choice.set_top_index(None)
    assert choice.get_top_index() == 0
    assert choice.get_cos_object().get_dictionary_object(_TI) is None


def test_export_values_getter_setter(
    choice: PDListBox, export_values: list[str]
) -> None:
    """Subset of upstream ``testExportValuesGetterSetter``."""
    choice.set_options(export_values)
    assert choice.get_options_display_values() == export_values
    assert choice.get_options_export_values() == export_values

    # PDFBOX-4252 regression path: non-null /TI must not interfere with /V.
    choice.set_top_index(1)
    choice.set_value(export_values[2])
    assert choice.get_value()[0] == export_values[2]
    choice.set_top_index(None)

    opt_item = choice.get_cos_object().get_dictionary_object(_OPT)
    assert opt_item is not None
    assert opt_item.size() == len(export_values)
    assert opt_item.get_string(0) == export_values[0]
    assert choice.get_options() == export_values


def test_set_export_and_display(
    choice: PDListBox, export_values: list[str], display_values: list[str]
) -> None:
    """Upstream: ``testSetExportAndDisplay``."""
    choice.set_options(export_values, display_values)
    assert choice.get_options_display_values() == display_values
    assert choice.get_options_export_values() == export_values


def test_sort_option(
    choice: PDListBox, export_values: list[str], display_values: list[str]
) -> None:
    """Upstream: ``testSortOption``."""
    choice.set_options(export_values, display_values)
    assert choice.get_options_display_values()[0] == "display02"

    choice.set_sort(True)
    choice.set_options(export_values, display_values)
    assert choice.get_options_display_values() == [
        "display01",
        "display02",
        "display03",
    ]


def test_set_value_list_syncs_selected_indices(choice: PDListBox) -> None:
    """Subset of upstream list-box value selection behavior.

    Per PDF 32000-1 §12.7.4.4 and upstream
    ``PDChoice.updateSelectedOptionsIndex``, the ``/I`` array shall be
    sorted in ascending order regardless of the order callers pass the
    values to ``setValue``.
    """
    choice.set_options(["export01", "export02", "export03"])
    choice.set_multi_select(True)

    choice.set_value(["export03", "export01"])

    assert choice.get_value() == ["export03", "export01"]
    assert choice.get_selected_options_index() == [0, 2]


def test_set_value_rejects_missing_option(choice: PDListBox) -> None:
    """Subset of upstream ``setValue`` option validation."""
    choice.set_options(["export01", "export02"])

    with pytest.raises(ValueError):
        choice.set_value("missing")


def test_set_value_list_requires_multi_select(choice: PDListBox) -> None:
    """Subset of upstream ``setValue(List)`` multi-select validation."""
    choice.set_options(["export01", "export02"])

    with pytest.raises(ValueError):
        choice.set_value(["export01", "export02"])
