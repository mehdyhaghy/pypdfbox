from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.multipdf import PDFMergerUtility
from tests.multipdf import test_pdf_merger_utility as merger_tests


def test_wave1176_stream_cache_factory_body_executes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = PDFMergerUtility.set_stream_cache_create_function

    def call_then_store(self: PDFMergerUtility, fn: Callable[[], object]) -> None:
        fn()
        original(self, fn)

    monkeypatch.setattr(
        PDFMergerUtility,
        "set_stream_cache_create_function",
        call_then_store,
    )

    merger_tests.test_stream_cache_create_function_setter_round_trip()
