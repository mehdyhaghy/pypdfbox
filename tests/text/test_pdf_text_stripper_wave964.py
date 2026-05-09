from __future__ import annotations

import importlib

from pypdfbox.pdmodel import PDDocument


def test_wave964_invokes_exposed_empty_range_hook_methods() -> None:
    target = importlib.import_module("tests.text.test_pdf_text_stripper")

    target.test_end_document_runs_even_on_empty_range()
    bracketed_class = target._WAVE964_BRACKETED_CLASS
    assert bracketed_class is not None

    doc = PDDocument()
    try:
        stripper = bracketed_class()
        stripper.start_document(doc)
        stripper.end_document(doc)
    finally:
        doc.close()
