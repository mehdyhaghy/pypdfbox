"""Wave 1347 coverage boost for ``pypdfbox.printing.pdf_pageable``.

Targets the residual getter/setter branches not exercised by
``test_printing_wave1281`` (the printable-level tests cover the
``PDFPrintable`` mirror surface but never call the equivalent
``PDFPageable.*`` accessors):

- ``get_rendering_hints`` (line 50) — default ``None`` then post-set
  round-trip.
- ``set_rendering_hints`` (line 53).
- ``is_subsampling_allowed`` (line 56) — default ``False`` then post-set
  round-trip.
- ``set_subsampling_allowed`` (line 59).

Pre-wave the module sat at 89.7 % (4 missing); this set takes it to
100 %.
"""

from __future__ import annotations

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.printing.pdf_pageable import Orientation, PDFPageable


def _make_doc_with_pages(n: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n):
        doc.add_page(PDPage())
    return doc


# ---------------------------------------------------------------------------
# ``get_rendering_hints`` / ``set_rendering_hints``
# ---------------------------------------------------------------------------
def test_get_rendering_hints_default_is_none() -> None:
    pageable = PDFPageable(_make_doc_with_pages(1))
    assert pageable.get_rendering_hints() is None


def test_set_rendering_hints_round_trips() -> None:
    pageable = PDFPageable(_make_doc_with_pages(1))
    hints = {"KEY_RENDERING": "VALUE_RENDER_QUALITY"}
    pageable.set_rendering_hints(hints)
    assert pageable.get_rendering_hints() is hints


def test_set_rendering_hints_back_to_none() -> None:
    pageable = PDFPageable(_make_doc_with_pages(1))
    pageable.set_rendering_hints({"a": 1})
    pageable.set_rendering_hints(None)
    assert pageable.get_rendering_hints() is None


# ---------------------------------------------------------------------------
# ``is_subsampling_allowed`` / ``set_subsampling_allowed``
# ---------------------------------------------------------------------------
def test_is_subsampling_allowed_default_false() -> None:
    pageable = PDFPageable(_make_doc_with_pages(1))
    assert pageable.is_subsampling_allowed() is False


def test_set_subsampling_allowed_toggle() -> None:
    pageable = PDFPageable(_make_doc_with_pages(1))
    pageable.set_subsampling_allowed(True)
    assert pageable.is_subsampling_allowed() is True
    pageable.set_subsampling_allowed(False)
    assert pageable.is_subsampling_allowed() is False


# ---------------------------------------------------------------------------
# Rendering-hints / subsampling propagate into the per-page ``PDFPrintable``
# ---------------------------------------------------------------------------
def test_per_page_printable_inherits_rendering_hints_and_subsampling() -> None:
    pageable = PDFPageable(_make_doc_with_pages(2))
    pageable.set_rendering_hints({"hint": "value"})
    pageable.set_subsampling_allowed(True)

    printable = pageable.get_printable(1)

    # Internal mirroring per upstream PDFPageable.getPrintable.
    assert printable._rendering_hints == {"hint": "value"}  # type: ignore[attr-defined]
    assert printable._subsampling_allowed is True  # type: ignore[attr-defined]
    assert printable._page_index == 1  # type: ignore[attr-defined]


def test_get_page_format_with_auto_orientation() -> None:
    """Smoke-cover the default-orientation branch — ``AUTO`` is the
    default and previously only ``LANDSCAPE`` was asserted on."""
    pageable = PDFPageable(_make_doc_with_pages(1))
    fmt = pageable.get_page_format(0)
    assert fmt["orientation"] == Orientation.AUTO.value
