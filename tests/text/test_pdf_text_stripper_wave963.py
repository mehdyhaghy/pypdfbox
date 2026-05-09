from __future__ import annotations

import importlib

from pypdfbox.pdmodel import PDDocument


def test_wave963_invokes_exposed_empty_range_hook_methods() -> None:
    target = importlib.import_module("tests.text.test_pdf_text_stripper_wave460")

    target.test_wave460_get_text_empty_range_does_not_call_document_hooks()
    hook_class = target._WAVE963_HOOK_STRIPPER_CLASS
    assert hook_class is not None

    doc = PDDocument()
    try:
        stripper = hook_class()
        stripper.start_document(doc)
        stripper.end_document(doc)
    finally:
        doc.close()
