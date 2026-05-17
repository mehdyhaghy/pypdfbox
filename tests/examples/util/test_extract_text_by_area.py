"""Smoke test for :class:`ExtractTextByArea`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.extract_text_by_area import ExtractTextByArea


def test_extract_region_runs(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("area.pdf")
    text = ExtractTextByArea.extract_region(str(src))
    # Blank pages produce empty text — the call must still complete.
    assert isinstance(text, str)


def test_constructor_is_callable() -> None:
    """Cover the no-op ``__init__`` (line 25)."""
    instance = ExtractTextByArea()
    assert isinstance(instance, ExtractTextByArea)


def test_main_without_args_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cover the ``argv != 1`` branch (lines 33-35) and ``usage`` (line 69)."""
    result = ExtractTextByArea.main(None)
    captured = capsys.readouterr()
    assert result == ""
    assert "Usage:" in captured.err


def test_main_with_one_arg_calls_extract(
    make_pdf: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cover the ``argv == 1`` branch (line 37 — return ``extract_region``)."""
    src = make_pdf("area-main.pdf")
    result = ExtractTextByArea.main([str(src)])
    assert isinstance(result, str)
    capsys.readouterr()  # drain stdout


def test_extract_region_falls_back_on_type_error(
    make_pdf: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover lines 55-58: when ``add_region`` rejects ``PDRectangle`` with
    ``TypeError`` we fall back to a tuple."""
    from pypdfbox.examples.util import extract_text_by_area as mod

    real_stripper_cls = mod.PDFTextStripperByArea
    real_rect = mod.PDRectangle

    class _PickyStripper(real_stripper_cls):
        def add_region(self, name, rect):  # type: ignore[override]
            if isinstance(rect, real_rect):
                raise TypeError("PDRectangle is not accepted in this stub")
            return super().add_region(name, rect)

    monkeypatch.setattr(mod, "PDFTextStripperByArea", _PickyStripper)

    src = make_pdf("area-fallback.pdf")
    text = ExtractTextByArea.extract_region(str(src))
    assert isinstance(text, str)
