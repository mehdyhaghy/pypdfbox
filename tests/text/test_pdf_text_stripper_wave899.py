from __future__ import annotations

import pytest

import tests.text.test_pdf_text_stripper_wave550 as wave550


def test_wave899_empty_range_local_hook_methods_are_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def get_text(self, document):  # noqa: ANN001
        page = next(iter(document.get_pages()))
        self.start_document(document)
        self.start_page(page)
        self.end_document(document)
        return ""

    monkeypatch.setattr(wave550.PDFTextStripper, "get_text", get_text)

    with pytest.raises(AssertionError):
        wave550.test_wave550_empty_or_inverted_page_ranges_return_without_page_hooks()
