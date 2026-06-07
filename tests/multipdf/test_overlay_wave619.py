from __future__ import annotations

from types import MethodType
from typing import cast

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import Overlay, Position
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle

_CONTENTS = COSName.get_pdf_name("Contents")
_RESOURCES = COSName.get_pdf_name("Resources")


def _doc_with_blank_pages(count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(count):
        doc.add_page(PDPage(PDRectangle.from_width_height(300.0, 400.0)))
    return doc


def test_position_value_of_accepts_background_and_rejects_unknown() -> None:
    assert Position.value_of("BACKGROUND") is Position.BACKGROUND

    with pytest.raises(ValueError, match="No Position constant"):
        Position.value_of("SIDEWAYS")


def test_overlay_rejects_empty_default_overlay_document() -> None:
    base = _doc_with_blank_pages(1)
    empty_overlay = PDDocument()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(empty_overlay)

    with pytest.raises(ValueError, match="at least one page"):
        overlay.overlay({})


def test_overlay_documents_ignores_none_specific_overlay() -> None:
    base = _doc_with_blank_pages(1)
    original_contents = base.get_page(0).get_cos_object().get_dictionary_object(
        _CONTENTS
    )
    overlay = Overlay()
    overlay.set_input_pdf(base)

    result = overlay.overlay_documents({1: cast(PDDocument, None)})

    assert result is base
    assert (
        base.get_page(0).get_cos_object().get_dictionary_object(_CONTENTS)
        is original_contents
    )


def test_overlay_creates_explicit_resources_when_page_has_only_lazy_resources() -> None:
    base = _doc_with_blank_pages(1)
    overlay_doc = _doc_with_blank_pages(1)
    page = base.get_page(0)
    assert not page.get_cos_object().contains_key(_RESOURCES)

    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    overlay.overlay({})

    resources = page.get_cos_object().get_dictionary_object(_RESOURCES)
    assert isinstance(resources, COSDictionary)
    xobjects = resources.get_dictionary_object(COSName.get_pdf_name("XObject"))
    assert isinstance(xobjects, COSDictionary)
    assert [name.get_name() for name in xobjects.key_set()] == ["OL1"]


def test_load_pdfs_filename_configuration_replaces_staged_documents() -> None:
    staged_input = _doc_with_blank_pages(1)
    staged_overlay = _doc_with_blank_pages(1)
    file_input = _doc_with_blank_pages(1)
    file_overlay = _doc_with_blank_pages(1)
    overlay = Overlay()
    overlay.set_input_pdf(staged_input)
    overlay.set_input_file("input-from-file.pdf")
    overlay.set_default_overlay_pdf(staged_overlay)
    overlay.set_default_overlay_file("overlay-from-file.pdf")

    loaded: list[str] = []

    def fake_load_owned_pdf(self: Overlay, path: str) -> PDDocument:
        loaded.append(path)
        if path == "input-from-file.pdf":
            return file_input
        if path == "overlay-from-file.pdf":
            return file_overlay
        raise AssertionError(path)

    overlay._load_owned_pdf = MethodType(fake_load_owned_pdf, overlay)  # type: ignore[method-assign]  # noqa: SLF001

    overlay._load_pdfs()  # noqa: SLF001

    assert loaded == ["input-from-file.pdf", "overlay-from-file.pdf"]
    assert overlay._input_pdf is file_input  # noqa: SLF001
    assert overlay._default_overlay_document is file_overlay  # noqa: SLF001
    assert overlay._default_overlay_page is not None  # noqa: SLF001


def test_create_page_overlay_layout_map_uses_zero_based_page_indexes() -> None:
    base = _doc_with_blank_pages(1)
    overlay_doc = _doc_with_blank_pages(3)
    overlay = Overlay()
    overlay.set_input_pdf(base)

    layout_map = overlay._create_page_overlay_layout_map(overlay_doc)  # noqa: SLF001

    assert list(layout_map) == [0, 1, 2]
    assert all(layout.overlay_media_box.get_width() == 300.0 for layout in layout_map.values())


def test_close_suppresses_document_close_errors_and_clears_caches() -> None:
    class BadCloseDocument:
        def close(self) -> None:
            raise OSError("close failed")

    overlay = Overlay()
    overlay.set_input_pdf(_doc_with_blank_pages(1))
    overlay._open_documents.append(cast(PDDocument, BadCloseDocument()))  # noqa: SLF001
    overlay._specific_page_overlay_layout[1] = overlay._create_layout_page(  # noqa: SLF001
        _doc_with_blank_pages(1).get_page(0)
    )
    overlay._rotated_default_overlay_pages[90] = overlay._specific_page_overlay_layout[1]  # noqa: SLF001

    overlay.close()

    assert overlay._open_documents == []  # noqa: SLF001
    assert overlay._specific_page_overlay_layout == {}  # noqa: SLF001
    assert overlay._rotated_default_overlay_pages == {}  # noqa: SLF001


def test_add_original_content_ignores_missing_contents() -> None:
    target = COSArray()

    Overlay._add_original_content(None, target)  # noqa: SLF001

    assert len(target) == 0
