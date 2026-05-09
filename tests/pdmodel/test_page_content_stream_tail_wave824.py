from __future__ import annotations

import pytest

from pypdfbox.pdmodel import pd_page_content_stream as content_stream_module


def test_wave824_format_number_normalizes_degenerate_minus_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        content_stream_module,
        "format",
        lambda _value, _spec: "-",
        raising=False,
    )

    assert content_stream_module._format_number(0.125) == b"0"
