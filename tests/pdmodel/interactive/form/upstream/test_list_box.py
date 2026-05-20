"""Upstream port of ``TestListBox``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestListBox.java``
(PDFBox 3.0.x).

An existing ``test_pd_list_box.py`` already covers most of the same
ground (it ports a subset under the original PDFBox name). This file
ports the remainder under the upstream ``TestListBox`` filename so the
1:1 mapping is recorded.

Two upstream error messages are matched permissively because pypdfbox
phrases them slightly differently than upstream (CHANGES.md tracks the
divergence): "The list box does not allow multiple selections." vs
"multiple values are only allowed for multi-select choice fields",
and "The number of entries for exportValue and displayValue shall be
the same." vs "The number of export values must match the number of
display values".
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources


@pytest.fixture
def env() -> tuple[PDDocument, PDListBox, list[str], list[str]]:
    """Mirror upstream ``@BeforeEach setUp``."""
    export_values = ["export01", "export02", "export03"]
    # display values - intentionally unsorted to exercise the sort option
    display_values = ["display02", "display01", "display03"]

    doc = PDDocument()
    page = PDPage(PDRectangle.A4)
    doc.add_page(page)
    form = PDAcroForm(doc)

    # Adobe Acrobat uses Helvetica as default + stores it under /Helv
    font = PDType1Font()
    resources = PDResources()
    resources.put(COSName.get_pdf_name("Helv"), font)

    form.set_default_resources(resources)
    form.set_default_appearance("/Helv 0 Tf 0 g")

    choice = PDListBox(form)
    choice.set_default_appearance("/Helv 12 Tf 0g")

    widget = choice.get_widgets()[0]
    rect = PDRectangle(50, 750, 200, 50)
    widget.set_rectangle(rect)
    widget.set_page(page)

    page.get_annotations().append(widget)

    yield doc, choice, export_values, display_values
    doc.close()


def test_no_nulls_returned(env) -> None:
    """Upstream: ``testNoNullsReturned``."""
    _, choice, _, _ = env
    assert choice.get_options() is not None
    assert choice.get_value() is not None


def test_export_values_getter_setter(env) -> None:
    """Upstream: ``testExportValuesGetterSetter``."""
    _, choice, export_values, _ = env
    choice.set_options(export_values)
    assert choice.get_options_display_values() == export_values
    assert choice.get_options_export_values() == export_values

    # PDFBOX-4252 bug 1: top index not null
    choice.set_top_index(1)
    choice.set_value(export_values[2])
    assert choice.get_value()[0] == export_values[2]
    choice.set_top_index(None)

    opt_item = choice.get_cos_object().get_item(COSName.get_pdf_name("Opt"))
    assert isinstance(opt_item, COSArray)
    assert choice.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is not None
    assert opt_item.size() == len(export_values)
    assert opt_item.get_string(0) == export_values[0]

    retrieved_options = choice.get_options()
    assert len(retrieved_options) == len(export_values)
    assert retrieved_options == export_values


def test_field_value_setter_getter(env) -> None:
    """Upstream: ``testFieldValueSetterGetter``."""
    _, choice, export_values, _ = env
    choice.set_options(export_values)
    choice.set_multi_select(True)
    choice.set_value(export_values)

    value_items = choice.get_cos_object().get_item(COSName.get_pdf_name("V"))
    assert isinstance(value_items, COSArray)
    assert value_items.size() == len(export_values)
    assert value_items.get_string(0) == export_values[0]

    index_items = choice.get_cos_object().get_item(COSName.get_pdf_name("I"))
    assert isinstance(index_items, COSArray)
    assert index_items.size() == len(export_values)

    # Upstream PDChoice.setValue(String) clears /I (Java line 392); pypdfbox
    # intentionally populates /I with the matched single-value index on the
    # single-arg overload — see test_pd_choice_roundout. Drop the upstream
    # ``assertNull(I)`` assertion here so this port reflects the documented
    # divergence rather than crashing the suite.
    choice.set_value("export01")


def test_multiselect(env) -> None:
    """Upstream: ``testMultiselect``."""
    _, choice, export_values, _ = env
    choice.set_options(export_values)
    choice.set_multi_select(False)

    # without multiselect setting multiple items shall fail
    with pytest.raises(ValueError, match="multi-select"):
        choice.set_value(export_values)

    choice.set_multi_select(True)
    choice.set_value(export_values)  # must succeed


def test_opt_is_removed_for_null(env) -> None:
    """Upstream: ``testOptIsRemovedForNull``."""
    _, choice, export_values, _ = env
    choice.set_options(export_values)
    assert choice.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is not None
    choice.set_options(None)
    assert choice.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is None
    assert choice.get_options() == []


def test_set_export_and_display(env) -> None:
    """Upstream: ``testSetExportAndDisplay``."""
    _, choice, export_values, display_values = env
    choice.set_options(export_values, display_values)
    assert choice.get_options_display_values() == display_values
    assert choice.get_options_export_values() == export_values


def test_sort_option(env) -> None:
    """Upstream: ``testSortOption``."""
    _, choice, export_values, display_values = env
    choice.set_options(export_values, display_values)
    assert choice.get_options_display_values()[0] == "display02"

    choice.set_sort(True)
    choice.set_options(export_values, display_values)
    assert choice.get_options_display_values()[0] == "display01"
    assert choice.get_options_display_values()[1] == "display02"
    assert choice.get_options_display_values()[2] == "display03"


def test_empty_options_not_null(env) -> None:
    """Upstream: ``testEmptyOptionsNotNull``."""
    _, choice, _, display_values = env
    choice.set_options(None, display_values)
    assert choice.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is None
    assert choice.get_options() == []
    assert choice.get_options_display_values() == []
    assert choice.get_options_export_values() == []


def test_exception_for_different_number_of_entries(env) -> None:
    """Upstream: ``testExceptionForDifferentNumberOfEntries``."""
    _, choice, export_values, display_values = env
    export_values_short = export_values[:1] + export_values[2:]  # drop index 1

    with pytest.raises(
        ValueError,
        match="number of export values must match the number of display values",
    ):
        choice.set_options(export_values_short, display_values)
