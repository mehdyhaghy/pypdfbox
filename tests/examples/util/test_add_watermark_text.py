"""Smoke test for :class:`AddWatermarkText`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.add_watermark_text import AddWatermarkText


def test_watermark_runs(make_pdf: Callable[..., Path], tmp_path: Path) -> None:
    src = make_pdf("water.pdf", page_count=2)
    dst = tmp_path / "wm.pdf"
    AddWatermarkText.main([str(src), str(dst), "DRAFT"])
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_constructor_is_callable() -> None:
    """Cover the no-op ``__init__`` (line 27)."""
    instance = AddWatermarkText()
    assert isinstance(instance, AddWatermarkText)


def test_main_without_args_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cover the ``argv != 3`` branch (lines 33-35) and ``usage`` (line 95)."""
    AddWatermarkText.main(None)
    captured = capsys.readouterr()
    assert "Usage:" in captured.err


def test_main_with_wrong_arg_count_prints_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Cover the same branch for the non-empty / wrong-length case."""
    AddWatermarkText.main(["only-one"])
    captured = capsys.readouterr()
    assert "Usage:" in captured.err


def test_add_watermark_falls_back_when_append_mode_missing(
    make_pdf: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover lines 54-55: ``AttributeError`` on ``PDPageContentStream.AppendMode``.

    Patch the class attribute lookup with a stand-in object that raises
    ``AttributeError`` on ``.AppendMode``."""
    from pypdfbox.examples.util import add_watermark_text as mod

    real_pcs = mod.PDPageContentStream

    class _ShimNoAppendMode:
        def __init__(self, *a, **kw):  # noqa: ANN001, ANN002, ANN003
            # Only the two-arg form is used after the fallback.
            assert len(a) == 2
            self._inner = real_pcs(*a, **kw)

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

    # Strip the class-level AppendMode attribute so the lookup raises.
    def _no_append_mode(*a, **kw):  # noqa: ANN002, ANN003
        return _ShimNoAppendMode(*a, **kw)

    # Replace the AppendMode property with one that raises AttributeError.
    class _ShimClass:
        def __getattr__(self, name: str):
            if name == "AppendMode":
                raise AttributeError(name)
            return getattr(real_pcs, name)

        def __call__(self, *a, **kw):  # noqa: ANN002, ANN003
            return _no_append_mode(*a, **kw)

    monkeypatch.setattr(mod, "PDPageContentStream", _ShimClass())

    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.pd_document import PDDocument

    src = make_pdf("watermark-noappend.pdf")
    with PDDocument.load(str(src)) as doc:
        page = doc.get_page(0)
        AddWatermarkText.add_watermark_text(doc, page, PDType1Font(), "DRAFT")


def test_add_watermark_falls_back_on_type_error(
    make_pdf: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover lines 60-62: ``TypeError`` from the multi-arg constructor."""
    from pypdfbox.examples.util import add_watermark_text as mod

    real_pcs = mod.PDPageContentStream

    class _ShimPicky:
        # Mirror the class attribute so the first branch is taken.
        AppendMode = real_pcs.AppendMode

        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            if len(args) > 2:
                raise TypeError("multi-arg form is unavailable in this stub")
            self._inner = real_pcs(*args, **kwargs)

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

    monkeypatch.setattr(mod, "PDPageContentStream", _ShimPicky)

    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
    from pypdfbox.pdmodel.pd_document import PDDocument

    src = make_pdf("watermark-typeerr.pdf")
    with PDDocument.load(str(src)) as doc:
        page = doc.get_page(0)
        AddWatermarkText.add_watermark_text(doc, page, PDType1Font(), "DRAFT")
