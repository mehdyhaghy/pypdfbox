"""``Overlay._get_layout_page`` rotation-source parity (perf fix).

``_process_pages`` already holds the current :class:`PDPage`, so it now passes
that page's rotation into ``_get_layout_page`` instead of having the helper
re-fetch the page by index (an O(n) ``get_page(i)`` per page → O(n²) over the
document). The public ``get_layout_page(page_number, number_of_pages)`` delegate
keeps its two-argument signature and falls back to the by-index lookup.
"""

from __future__ import annotations

from collections.abc import Generator

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


def _overlay_doc(*, width: float = 100.0, height: float = 120.0) -> PDDocument:
    doc = PDDocument()
    _OPEN_DOCS.append(doc)
    doc.add_page(PDPage(PDRectangle.from_width_height(width, height)))
    return doc


def _xobject_stream(page: PDPage) -> COSStream:
    resources = page.get_resources()
    assert resources is not None
    xobjects = resources.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("XObject")
    )
    assert isinstance(xobjects, COSDictionary)
    key = next(iter(xobjects.key_set()))
    value = xobjects.get_dictionary_object(key)
    assert isinstance(value, COSStream)
    return value


def test_passed_rotation_selects_adjusted_layout() -> None:
    """Passing a non-zero rotation yields the rotated default layout."""
    overlay = Overlay()
    base = _doc_with_pages(1)
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_overlay_doc(width=100.0, height=120.0))
    overlay.set_adjust_rotation(True)
    overlay.load_pd_fs()

    layout = overlay._get_layout_page(1, 1, 90)  # noqa: SLF001
    assert layout is not None
    # 90° rotation swaps into the adjusted overlay layout (rotation applied).
    assert layout.overlay_rotation == (0 - 90 + 360) % 360


def test_passed_zero_rotation_keeps_default_layout() -> None:
    overlay = Overlay()
    base = _doc_with_pages(1)
    overlay.set_input_pdf(base)
    default = _overlay_doc()
    overlay.set_default_overlay_pdf(default)
    overlay.set_adjust_rotation(True)
    overlay.load_pd_fs()

    layout = overlay._get_layout_page(1, 1, 0)  # noqa: SLF001
    assert layout is overlay._default_overlay_page  # noqa: SLF001


def test_public_delegate_two_arg_signature_falls_back_to_index() -> None:
    """The public ``get_layout_page(page_number, number_of_pages)`` keeps its
    signature; with no rotation supplied it resolves the page by index."""
    overlay = Overlay()
    base = _doc_with_pages(2)
    base.get_page(1).set_rotation(90)
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_overlay_doc(width=100.0, height=120.0))
    overlay.set_adjust_rotation(True)
    overlay.load_pd_fs()

    # Page 2 (index 1) is rotated 90° -> by-index fallback must find it.
    layout = overlay.get_layout_page(2, 2)
    assert layout is not None
    assert layout.overlay_rotation == (0 - 90 + 360) % 360


def test_process_pages_uses_current_page_rotation_end_to_end() -> None:
    base = _doc_with_pages(1)
    base.get_page(0).set_rotation(90)
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(_overlay_doc(width=100.0, height=120.0))
    overlay.set_adjust_rotation(True)

    overlay.overlay({})

    form = PDFormXObject(_xobject_stream(base.get_page(0)))
    # Rotated default overlay -> non-identity matrix (matches wave639 parity).
    assert form.get_matrix() == [0.0, 1.0, -1.0, 0.0, 120.0, 0.0]
