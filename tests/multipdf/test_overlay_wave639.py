from __future__ import annotations

from collections.abc import Generator
from typing import cast

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.multipdf import Overlay
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

_OPEN_DOCS: list[PDDocument] = []


@pytest.fixture(autouse=True)
def _close_documents() -> Generator[None]:
    yield
    while _OPEN_DOCS:
        doc = _OPEN_DOCS.pop()
        if not doc.is_closed():
            doc.close()


def _doc_with_pages(count: int) -> PDDocument:
    doc = PDDocument()
    _OPEN_DOCS.append(doc)
    for _ in range(count):
        doc.add_page(PDPage(PDRectangle.from_width_height(300.0, 400.0)))
    return doc


def _overlay_doc(
    *,
    width: float = 100.0,
    height: float = 120.0,
    rotation: int = 0,
) -> PDDocument:
    doc = PDDocument()
    _OPEN_DOCS.append(doc)
    page = PDPage(PDRectangle.from_width_height(width, height))
    page.set_rotation(rotation)
    doc.add_page(page)
    return doc


def _xobject_streams(page: PDPage) -> list[COSStream]:
    resources = page.get_resources()
    if resources is None:
        return []
    xobjects = resources.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("XObject")
    )
    if not isinstance(xobjects, COSDictionary):
        return []
    streams: list[COSStream] = []
    for key in xobjects.key_set():
        value = xobjects.get_dictionary_object(key)
        assert isinstance(value, COSStream)
        streams.append(value)
    return streams


def test_overlay_documents_ignores_none_entries() -> None:
    base = _doc_with_pages(2)
    overlay = Overlay()
    overlay.set_input_pdf(base)

    overlay.overlay_documents({1: None, 2: _overlay_doc()})  # type: ignore[dict-item]

    assert not _xobject_streams(base.get_page(0))
    assert _xobject_streams(base.get_page(1))


def test_adjust_rotation_sets_rotated_default_form_matrix() -> None:
    base = _doc_with_pages(1)
    base.get_page(0).set_rotation(90)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_overlay_doc(width=100.0, height=120.0))
    overlay.set_adjust_rotation(True)

    overlay.overlay({})

    form_stream = _xobject_streams(base.get_page(0))[0]
    form = PDFormXObject(form_stream)
    assert form.get_matrix() == [0.0, 1.0, -1.0, 0.0, 120.0, 0.0]


def test_adjust_rotation_is_not_used_for_specific_page_overlay() -> None:
    base = _doc_with_pages(1)
    base.get_page(0).set_rotation(90)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_adjust_rotation(True)

    overlay.overlay_documents({1: _overlay_doc(rotation=0)})

    form_stream = _xobject_streams(base.get_page(0))[0]
    form = PDFormXObject(form_stream)
    assert form.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_overlay_clones_page_resources_without_aliasing_source_dict() -> None:
    base = _doc_with_pages(1)
    source = _overlay_doc()
    source_page = source.get_page(0)
    source_resources = source_page.get_resources()
    assert source_resources is not None

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(source)
    overlay.overlay({})

    form_stream = _xobject_streams(base.get_page(0))[0]
    form = PDFormXObject(form_stream)
    cloned_resources = form.get_resources()
    assert cloned_resources is not None
    assert cloned_resources.get_cos_object() is not source_resources.get_cos_object()


def test_overlay_reuses_specific_page_documents_on_repeated_calls() -> None:
    base = _doc_with_pages(1)
    specific = _overlay_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_specific_page_overlay_pdf({1: specific})

    first = overlay.overlay({})
    second = overlay.overlay({})

    assert first is second is base
    layout = cast(dict[int, object], overlay._specific_page_overlay_layout)  # noqa: SLF001
    assert 1 in layout
