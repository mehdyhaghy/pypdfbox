from __future__ import annotations

import pytest

import tests.multipdf.test_overlay_wave619 as wave619
from pypdfbox.multipdf import Overlay


def test_wave619_fake_loader_rejects_unexpected_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def load_unexpected_path(self: Overlay) -> None:
        self._load_owned_pdf("unexpected.pdf")

    monkeypatch.setattr(Overlay, "_load_pdfs", load_unexpected_path)

    with pytest.raises(AssertionError, match="unexpected.pdf"):
        wave619.test_load_pdfs_filename_configuration_replaces_staged_documents()
