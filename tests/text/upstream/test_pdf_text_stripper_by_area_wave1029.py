from __future__ import annotations

from pathlib import Path

import pytest

import tests.text.upstream.test_pdf_text_stripper_by_area as by_area


def test_wave1029_some_method_skips_when_upstream_fixture_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(by_area, "_FIXTURE", Path("/missing/eu-001.pdf"))

    with pytest.raises(pytest.skip.Exception):
        by_area.test_some_method()
