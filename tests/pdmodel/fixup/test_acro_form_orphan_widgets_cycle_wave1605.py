"""PDFBOX-6227 — ``AcroFormOrphanWidgetsProcessor`` must not loop forever on a
cyclic ``/Parent`` chain.

Upstream added a visited set to ``resolveNonRootField``; before the fix a
widget whose ``/Parent`` pointed back into the chain (in the degenerate case,
at itself) spun the ``while (parent.containsKey(PARENT))`` loop forever. The
field is abandoned instead and a warning is logged.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor import (
    AcroFormOrphanWidgetsProcessor,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.pd_page import PDPage

_PARENT = COSName.PARENT
_T = COSName.get_pdf_name("T")


def _widget(name: str) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_name("Type", "Annot")
    dictionary.set_name("Subtype", "Widget")
    dictionary.set_name("FT", "Tx")
    dictionary.set_string(_T, name)
    return dictionary


def test_resolve_non_root_field_self_cycle_returns_none() -> None:
    """A dictionary whose ``/Parent`` is itself terminates and yields nothing."""
    document = PDDocument()
    acro_form = PDAcroForm(document)
    processor = AcroFormOrphanWidgetsProcessor(document)

    node = _widget("self")
    node.set_item(_PARENT, node)

    assert processor.resolve_non_root_field(acro_form, node, {}) is None
    document.close()


def test_resolve_non_root_field_two_node_cycle_returns_none() -> None:
    """A -> B -> A is caught on the second visit of A."""
    document = PDDocument()
    acro_form = PDAcroForm(document)
    processor = AcroFormOrphanWidgetsProcessor(document)

    a = _widget("a")
    b = _widget("b")
    a.set_item(_PARENT, b)
    b.set_item(_PARENT, a)

    assert processor.resolve_non_root_field(acro_form, a, {}) is None
    document.close()


def test_resolve_non_root_field_cycle_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Upstream logs ``"Field ignored: " + parent`` when it bails out."""
    document = PDDocument()
    acro_form = PDAcroForm(document)
    processor = AcroFormOrphanWidgetsProcessor(document)

    node = _widget("self")
    node.set_item(_PARENT, node)

    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.fixup.processor.acro_form_orphan_widgets_processor",
    ):
        assert processor.resolve_non_root_field(acro_form, node, {}) is None

    assert any("Field ignored" in record.getMessage() for record in caplog.records)
    document.close()


def test_resolve_non_root_field_acyclic_chain_still_resolves() -> None:
    """Guard regression check: a well-formed chain still reaches its root."""
    document = PDDocument()
    acro_form = PDAcroForm(document)
    processor = AcroFormOrphanWidgetsProcessor(document)

    root = COSDictionary()
    root.set_string(_T, "root")
    root.set_item(COSName.get_pdf_name("Kids"), COSArray())

    child = _widget("child")
    child.set_item(_PARENT, root)

    resolved = processor.resolve_non_root_field(acro_form, child, {})
    assert resolved is not None
    assert resolved.get_cos_object() is root
    document.close()


def test_orphan_widget_rebuild_with_self_referencing_parent_terminates() -> None:
    """End-to-end: the no-arg ``get_acro_form()`` fixup drops the cyclic field.

    Mirrors upstream ``PDAcroFormTest.testCycle`` at the fixup level — the
    rebuild runs to completion and produces no fields.
    """
    document = PDDocument()
    page = PDPage()
    document.add_page(page)

    acro_form = PDAcroForm(document)
    acro_form.set_need_appearances(True)
    document.get_document_catalog().set_acro_form(acro_form)

    widget = _widget("cyclic")
    widget.set_item(_PARENT, widget)  # the cycle
    annots = COSArray()
    annots.add(widget)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    rebuilt = document.get_document_catalog().get_acro_form()
    assert rebuilt is not None
    assert rebuilt.get_fields() == []
    document.close()
