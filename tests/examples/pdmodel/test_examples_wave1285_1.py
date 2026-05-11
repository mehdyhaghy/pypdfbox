"""Wave 1285.1 — round-trip tests for the newly-implemented examples.

Verifies that ``embedded_files``, ``add_javascript``, ``superimpose_page``,
and ``print_urls`` drive their public entry points end-to-end against
in-memory PDFs without relying on external fixtures.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.add_javascript import AddJavascript
from pypdfbox.examples.pdmodel.embedded_files import EmbeddedFiles
from pypdfbox.examples.pdmodel.print_urls import PrintURLs
from pypdfbox.examples.pdmodel.superimpose_page import SuperimposePage
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument


def _make_blank_pdf(path: Path) -> None:
    """Save a one-page blank PDF to ``path``."""
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(path)


def test_embedded_files_writes_attachment(tmp_path: Path) -> None:
    out = tmp_path / "embedded.pdf"
    EmbeddedFiles().do_it(str(out))
    assert out.exists()
    # Round-trip: the saved PDF should be parseable.
    with Loader.load_pdf(out) as cos_doc:
        doc = PDDocument(cos_doc)
        catalog = doc.get_document_catalog()
        # /Names entry was set with the embedded-files tree.
        assert catalog.get_names() is not None


def test_add_javascript_sets_open_action(tmp_path: Path) -> None:
    in_pdf = tmp_path / "in.pdf"
    out_pdf = tmp_path / "out.pdf"
    _make_blank_pdf(in_pdf)
    AddJavascript.main([str(in_pdf), str(out_pdf)])
    assert out_pdf.exists()
    with Loader.load_pdf(out_pdf) as cos_doc:
        doc = PDDocument(cos_doc)
        # /OpenAction is present after the example runs.
        catalog = doc.get_document_catalog()
        assert catalog.get_open_action() is not None


def test_superimpose_page_writes_dest(tmp_path: Path) -> None:
    src = tmp_path / "src.pdf"
    dst = tmp_path / "dst.pdf"
    _make_blank_pdf(src)
    SuperimposePage.main([str(src), str(dst)])
    assert dst.exists()
    # The output should be a valid PDF — open round-trip.
    with Loader.load_pdf(dst) as cos_doc:
        doc = PDDocument(cos_doc)
        assert doc.get_number_of_pages() >= 1


def test_print_urls_handles_blank_pdf(tmp_path: Path, capsys) -> None:
    pdf = tmp_path / "blank.pdf"
    _make_blank_pdf(pdf)
    PrintURLs.main([str(pdf)])
    # No URI annotations on a blank page → no output.
    assert capsys.readouterr().out == ""
