from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.pd_document_catalog import PDDocumentCatalog
from pypdfbox.pdmodel.pd_page import PDPage
from tests.pdmodel.interactive.pagenavigation import test_pd_thread_integration


def test_wave976_catalog_rejects_test_fails_when_set_threads_allows_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def accept_any_threads(
        self: PDDocumentCatalog,
        threads: list[Any] | None,
    ) -> None:
        return None

    monkeypatch.setattr(PDDocumentCatalog, "set_threads", accept_any_threads)

    with pytest.raises(
        AssertionError,
        match="expected TypeError for non-PDThread element",
    ):
        test_pd_thread_integration.test_document_catalog_set_threads_rejects_non_thread()


def test_wave976_page_rejects_test_fails_when_set_thread_beads_allows_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def accept_any_beads(self: PDPage, beads: list[Any] | None) -> None:
        return None

    monkeypatch.setattr(PDPage, "set_thread_beads", accept_any_beads)

    with pytest.raises(
        AssertionError,
        match="expected TypeError for non-PDThreadBead element",
    ):
        test_pd_thread_integration.test_pd_page_set_thread_beads_rejects_non_bead()
