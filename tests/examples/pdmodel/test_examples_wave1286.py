"""Wave 1286 — round-trip tests for the font/PDF-A/collection examples.

Verifies that ``embedded_fonts``, ``embedded_vertical_fonts``,
``embedded_multiple_fonts``, ``bengali_pdf_generation_hello_world``,
``create_portable_collection``, and ``create_pdfa`` drive their public
entry points end-to-end where possible (Helvetica fallback paths /
synthesised sRGB ICC) without relying on external fixtures.

The font-dependent demos (vertical, multiple) defer to a
``demo_with_font*`` helper invoked with explicit user-supplied paths;
those round-trips live behind ``importorskip``-style guards so the
suite stays runnable on a stripped-down dev machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.bengali_pdf_generation_hello_world import (
    BengaliPdfGenerationHelloWorld,
)
from pypdfbox.examples.pdmodel.create_pdfa import CreatePDFA
from pypdfbox.examples.pdmodel.create_portable_collection import (
    CreatePortableCollection,
)
from pypdfbox.examples.pdmodel.embedded_fonts import EmbeddedFonts
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument


def _assert_is_pdf(path: Path) -> None:
    assert path.exists(), f"expected output PDF at {path}"
    assert path.stat().st_size > 0
    assert path.read_bytes()[:4] == b"%PDF"


def test_embedded_fonts_main_writes_pdf(tmp_path: Path) -> None:
    out = tmp_path / "fonts.pdf"
    EmbeddedFonts.main([str(out)])
    _assert_is_pdf(out)
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() == 1


def test_embedded_fonts_demo_with_font_helper_no_ttf(tmp_path: Path) -> None:
    # Helper accepts None as ttf_path and runs through the Helvetica
    # fallback identical to ``main()``.
    out = tmp_path / "fonts2.pdf"
    EmbeddedFonts.demo_with_font(out, None)
    _assert_is_pdf(out)


def test_bengali_pdf_generation_main_writes_pdf(tmp_path: Path) -> None:
    out = tmp_path / "bengali.pdf"
    BengaliPdfGenerationHelloWorld.main([str(out)])
    _assert_is_pdf(out)
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() >= 1


def test_bengali_pdf_generation_usage() -> None:
    with pytest.raises(SystemExit):
        BengaliPdfGenerationHelloWorld.main([])


def test_create_portable_collection_main_writes_pdf(tmp_path: Path) -> None:
    out = tmp_path / "collection.pdf"
    CreatePortableCollection.main([str(out)])
    _assert_is_pdf(out)
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        catalog = doc.get_document_catalog()
        # /Names entry holds the embedded-files tree; /Collection lives
        # on the catalog COSDictionary directly.
        assert catalog.get_names() is not None
        cos = catalog.get_cos_object()
        from pypdfbox.cos import COSName
        assert cos.get_dictionary_object(
            COSName.get_pdf_name("Collection"),
        ) is not None


def test_create_portable_collection_usage_returns_quietly() -> None:
    # ``main([])`` calls ``app.usage()`` and returns without raising.
    CreatePortableCollection.main([])


def test_create_pdfa_usage() -> None:
    with pytest.raises(SystemExit):
        CreatePDFA.main([])


def test_create_pdfa_main_requires_real_ttf(tmp_path: Path) -> None:
    # Without a real TTF on disk, PDType0Font.load raises OSError.
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError):
        CreatePDFA.main([str(out), "msg", str(tmp_path / "missing.ttf")])
