"""Tests for the public field/link rect-map helpers on :class:`PagePane`.

Wave 1308 promoted upstream's ``initUI`` / ``initRectMap`` /
``collectLinkLocation`` / ``collectLinkLocations`` /
``collectFieldLocations`` to the public surface
(``init_ui`` / ``init_rect_map`` / ``collect_link_location`` /
``collect_link_locations`` / ``collect_field_locations``). These tests
exercise each helper in isolation and verify that calling
``init_rect_map`` twice does not double-map entries.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.debugger.pagepane.page_pane import PagePane
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


def _make_one_page_doc(
    content: bytes | None = None,
    page_size: tuple[float, float] = (60.0, 60.0),
) -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, page_size[0], page_size[1]))
    if content is not None:
        stream = COSStream()
        stream.set_data(content)
        page.set_contents(stream)
    doc.add_page(page)
    return doc


def _add_uri_link(
    page: PDPage,
    rect: tuple[float, float, float, float],
    uri: str,
) -> PDAnnotationLink:
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(*rect))
    action = PDActionURI()
    action.set_uri(uri)
    link.set_action(action)
    existing = list(page.get_annotations() or [])
    existing.append(link)
    page.set_annotations(existing)
    return link


def _build_acroform_text_field(
    doc: PDDocument,
    name: str,
    value: str,
    rect: tuple[float, float, float, float],
) -> tuple[PDAcroForm, PDAnnotationWidget]:
    """Build an AcroForm with one text field; the field dict doubles as
    the widget annotation (single-widget shortcut from the PDF spec)."""
    acroform = PDAcroForm(doc)
    field_dict = COSDictionary()
    field_dict.set_name(COSName.get_pdf_name("FT"), "Tx")
    field_dict.set_string(COSName.get_pdf_name("T"), name)
    field_dict.set_string(COSName.get_pdf_name("V"), value)
    field_dict.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    field_dict.set_item(
        COSName.get_pdf_name("Rect"), PDRectangle(*rect).get_cos_object()
    )
    field = PDTextField(acroform, field_dict, None)
    acroform.set_fields([field])
    doc.get_document_catalog().set_acro_form(acroform)
    return acroform, PDAnnotationWidget(field_dict)


# ---------------------------------------------------------------------------
# collect_field_locations
# ---------------------------------------------------------------------------


def test_collect_field_locations_populates_for_acroform_field(
    tk_root: tk.Tk,
) -> None:
    """A page with an AcroForm widget gets a non-empty field-label map."""
    doc = _make_one_page_doc()
    try:
        _, widget = _build_acroform_text_field(
            doc, name="fname", value="ada", rect=(5.0, 5.0, 25.0, 15.0)
        )
        page = doc.get_page(0)
        page.set_annotations([widget])
        pane = PagePane(tk_root, doc, page.get_cos_object(), statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert any("Field name: fname" in lbl and "value: ada" in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_empty_for_plain_page(tk_root: tk.Tk) -> None:
    """A page with no AcroForm field produces no ``Field name:`` labels."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# collect_link_location  (single annotation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("page_rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("page_size", [(60.0, 60.0), (120.0, 90.0)])
def test_collect_link_location_records_user_space_rect(
    tk_root: tk.Tk,
    page_rotation: int,
    page_size: tuple[float, float],
) -> None:
    """``collect_link_location`` stores the link's user-space ``/Rect``
    in :attr:`_rect_map` under the rectangle key, regardless of page
    rotation. Upstream does *not* transform the rect to screen space at
    collect time; the hover handler applies the zoom/rotation transform
    when checking ``rect.contains``.
    """
    doc = _make_one_page_doc(page_size=page_size)
    try:
        page = doc.get_page(0)
        page.set_rotation(page_rotation)
        pane = PagePane(tk_root, doc, page.get_cos_object(), statuslabel=None)
        pane.init()
        # The rectangle the link will use.
        rect = PDRectangle(10.0, 20.0, 30.0, 40.0)
        link = PDAnnotationLink()
        link.set_rectangle(rect)
        action = PDActionURI()
        action.set_uri("https://parity.example.com")
        link.set_action(action)
        before = dict(pane._rect_map)  # noqa: SLF001
        pane.collect_link_location(link)
        new_entries = {
            k: v for k, v in pane._rect_map.items() if k not in before  # noqa: SLF001
        }
        assert len(new_entries) == 1
        (stored_rect, stored_label), = new_entries.items()
        assert stored_label == "URI: https://parity.example.com"
        # User-space coords unchanged (no transform applied at collect time).
        assert stored_rect.get_lower_left_x() == pytest.approx(10.0)
        assert stored_rect.get_lower_left_y() == pytest.approx(20.0)
        assert stored_rect.get_upper_right_x() == pytest.approx(30.0)
        assert stored_rect.get_upper_right_y() == pytest.approx(40.0)
    finally:
        doc.close()


def test_collect_link_location_returns_when_rect_missing(tk_root: tk.Tk) -> None:
    """A link without ``/Rect`` is silently skipped."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        before = dict(pane._rect_map)  # noqa: SLF001
        link = PDAnnotationLink()  # no rect, no action
        pane.collect_link_location(link)
        assert pane._rect_map == before  # noqa: SLF001
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# collect_link_locations  (whole page)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_links", [1, 3, 5])
def test_collect_link_locations_counts_match(tk_root: tk.Tk, n_links: int) -> None:
    """A page with N link annotations produces N URI entries in the rect map."""
    doc = _make_one_page_doc()
    try:
        page = doc.get_page(0)
        for i in range(n_links):
            _add_uri_link(
                page,
                rect=(float(i), float(i), float(i + 10), float(i + 10)),
                uri=f"https://example.com/{i}",
            )
        pane = PagePane(tk_root, doc, page.get_cos_object(), statuslabel=None)
        pane.init()
        uri_labels = [
            v for v in pane._rect_map.values() if v.startswith("URI: ")  # noqa: SLF001
        ]
        assert len(uri_labels) == n_links
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# init_rect_map idempotence
# ---------------------------------------------------------------------------


def test_init_rect_map_does_not_double_map(tk_root: tk.Tk) -> None:
    """Calling ``init_rect_map`` twice yields the same entry count."""
    doc = _make_one_page_doc()
    try:
        page = doc.get_page(0)
        _add_uri_link(page, rect=(5.0, 5.0, 25.0, 25.0), uri="https://once.example.com")
        _add_uri_link(page, rect=(30.0, 30.0, 50.0, 50.0), uri="https://twice.example.com")
        pane = PagePane(tk_root, doc, page.get_cos_object(), statuslabel=None)
        pane.init()
        first_count = len(pane._rect_map)  # noqa: SLF001
        assert first_count == 2
        pane.init_rect_map()
        second_count = len(pane._rect_map)  # noqa: SLF001
        assert second_count == first_count
    finally:
        doc.close()


def test_init_rect_map_refresh_picks_up_new_link(tk_root: tk.Tk) -> None:
    """Adding a link annotation between two ``init_rect_map`` calls
    surfaces in the second map."""
    doc = _make_one_page_doc()
    try:
        page = doc.get_page(0)
        _add_uri_link(page, rect=(5.0, 5.0, 25.0, 25.0), uri="https://first.example.com")
        pane = PagePane(tk_root, doc, page.get_cos_object(), statuslabel=None)
        pane.init()
        assert len(pane._rect_map) == 1  # noqa: SLF001
        _add_uri_link(
            page, rect=(40.0, 40.0, 55.0, 55.0), uri="https://second.example.com"
        )
        pane.init_rect_map()
        assert len(pane._rect_map) == 2  # noqa: SLF001
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# init_ui smoke
# ---------------------------------------------------------------------------


def test_init_ui_smoke_widgets_exist(tk_root: tk.Tk) -> None:
    """``PagePane.init()`` (which delegates to ``init_ui``) wires up the
    expected child widgets without raising."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert pane.get_panel() is not None
        assert pane._page_label_widget is not None  # noqa: SLF001
        assert pane._canvas is not None  # noqa: SLF001
        # Upstream-named entry point should be invokable too.
        assert callable(pane.init_ui)
        assert callable(pane.init_rect_map)
        assert callable(pane.collect_field_locations)
        assert callable(pane.collect_link_locations)
        assert callable(pane.collect_link_location)
    finally:
        doc.close()


def test_init_ui_direct_call_does_not_raise(tk_root: tk.Tk) -> None:
    """Calling ``init_ui`` directly (the upstream-named entry point)
    builds the widget tree without errors."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        # Bypass the ``init()`` wrapper to drive the upstream method alone.
        pane.init_ui()
        assert pane._page_label_widget is not None  # noqa: SLF001
        assert pane._canvas is not None  # noqa: SLF001
    finally:
        doc.close()
