"""Parity tests for upstream-named accessor aliases on
:class:`pypdfbox.pdmodel.PDDocument`. Mirrors the surface that PDFBox
exposes from ``org.apache.pdfbox.pdmodel.PDDocument`` so direct ports
from Java land without naming churn."""

from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.pdmodel import PDPageTree


def test_get_number_of_pages_empty_then_grows() -> None:
    doc = PDDocument()
    assert doc.get_number_of_pages() == 0
    doc.add_page(PDPage())
    assert doc.get_number_of_pages() == 1
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    assert doc.get_number_of_pages() == 3


def test_get_page_returns_pdpage_at_index() -> None:
    doc = PDDocument()
    p0 = PDPage()
    p1 = PDPage()
    doc.add_page(p0)
    doc.add_page(p1)
    fetched = doc.get_page(0)
    assert isinstance(fetched, PDPage)
    # Same backing COSDictionary as the page we added.
    assert fetched.get_cos_object() is p0.get_cos_object()
    assert doc.get_page(1).get_cos_object() is p1.get_cos_object()


def test_get_pages_returns_pdpagetree() -> None:
    doc = PDDocument()
    pages = doc.get_pages()
    assert isinstance(pages, PDPageTree)
    # Stable across calls (cached).
    assert doc.get_pages() is pages


def test_get_set_version_round_trip() -> None:
    doc = PDDocument()
    # Default header version is 1.4 per _build_minimal_skeleton.
    assert doc.get_version() == 1.4
    doc.set_version(1.7)
    assert doc.get_version() == 1.7
    # Downgrades are no-ops (mirrors upstream).
    doc.set_version(1.3)
    assert doc.get_version() == 1.7


def test_get_signature_dictionaries_empty_on_fresh_doc() -> None:
    doc = PDDocument()
    assert doc.get_signature_dictionaries() == []
    assert doc.get_signature_fields() == []


def test_requires_full_save_true_on_fresh_doc() -> None:
    """Synthesised documents have no parsable source, so an incremental
    save would have nothing to append against — full save required."""
    doc = PDDocument()
    assert doc.requires_full_save() is True


def test_is_locked_by_outline_destinations_default_false() -> None:
    doc = PDDocument()
    assert doc.is_locked_by_outline_destinations() is False
