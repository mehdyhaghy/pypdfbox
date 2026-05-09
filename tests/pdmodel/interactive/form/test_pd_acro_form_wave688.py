from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDNonTerminalField
from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _num_array(*values: float) -> COSArray:
    return COSArray([COSFloat(value) for value in values])


def _appearance() -> COSStream:
    stream = COSStream()
    stream.set_item("BBox", _num_array(0.0, 0.0, 10.0, 10.0))
    stream.set_raw_data(b"q Q\n")
    return stream


class _OddField(PDField):
    def __init__(self, form: PDAcroForm, *, terminal: bool) -> None:
        super().__init__(form)
        self._terminal = terminal

    def is_terminal(self) -> bool:
        return self._terminal


def test_wave688_append_field_subtree_stops_for_non_terminal_non_node_field() -> None:
    form = PDAcroForm()
    field = _OddField(form, terminal=False)
    out: list[PDField] = []

    form._append_field_subtree(field, out)  # noqa: SLF001

    assert out == [field]


@pytest.mark.parametrize("terminal", [True, False])
def test_wave688_collect_terminals_ignores_fields_outside_expected_classes(
    terminal: bool,
) -> None:
    form = PDAcroForm()
    field = _OddField(form, terminal=terminal)

    assert form._collect_terminals(field) == []  # noqa: SLF001


def test_wave688_flatten_with_no_targets_returns_without_mutating_form() -> None:
    form = PDAcroForm()

    form.flatten()

    assert form.get_cos_object().contains_key("Fields") is True


def test_wave688_flatten_loop_skips_collected_non_terminal_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    form = PDAcroForm()
    field = PDNonTerminalField(form)
    field.set_partial_name("group")
    monkeypatch.setattr(form, "_collect_terminals", lambda _: [field])

    form.flatten(fields=[field])

    assert form.get_cos_object().contains_key("Fields") is True


def test_wave688_flatten_widget_skips_valid_appearance_without_page() -> None:
    form = PDAcroForm()
    widget = COSDictionary()
    widget.set_item("Rect", _num_array(0.0, 0.0, 10.0, 10.0))
    ap = COSDictionary()
    ap.set_item("N", _appearance())
    widget.set_item("AP", ap)

    form._flatten_widget(widget)  # noqa: SLF001

    assert widget.get_dictionary_object("AP") is ap


def test_wave688_resolve_widget_page_scans_pages_without_match() -> None:
    doc = PDDocument()
    try:
        first = PDPage()
        second = PDPage()
        doc.add_page(first)
        doc.add_page(second)
        annots = COSArray()
        annots.add(COSDictionary())
        second.get_cos_object().set_item("Annots", annots)

        assert PDAcroForm(doc)._resolve_widget_page(COSDictionary()) is None  # noqa: SLF001
    finally:
        doc.close()


def test_wave688_read_form_geometry_treats_non_numeric_bbox_as_missing() -> None:
    stream = COSStream()
    stream.set_item(
        "BBox",
        COSArray(
            [
                COSFloat(0.0),
                COSFloat(0.0),
                COSName.get_pdf_name("bad"),
                COSFloat(10.0),
            ]
        ),
    )

    bbox, matrix = PDAcroForm._read_form_geometry(stream)  # noqa: SLF001

    assert bbox is None
    assert matrix == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_wave688_remove_acro_form_from_catalog_is_noop_without_document() -> None:
    PDAcroForm()._remove_acro_form_from_catalog()  # noqa: SLF001
