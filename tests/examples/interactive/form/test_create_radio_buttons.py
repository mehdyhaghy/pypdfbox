"""Smoke + coverage tests for :class:`CreateRadioButtons`."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from pypdfbox.examples.interactive.form.create_radio_buttons import CreateRadioButtons
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)

# ---------------------------------------------------------------------------
# End-to-end smoke
# ---------------------------------------------------------------------------


def test_create_radio_buttons_runs(tmp_path: Path) -> None:
    out = tmp_path / "radio.pdf"
    CreateRadioButtons.main([str(out)])
    assert out.exists()
    assert out.stat().st_size > 0


def test_create_radio_buttons_main_with_no_args(tmp_path: Path, monkeypatch) -> None:
    """``main(None)`` falls back to ``DEFAULT_FILENAME``."""
    monkeypatch.chdir(tmp_path)
    Path("target").mkdir(exist_ok=True)
    CreateRadioButtons.main(None)
    assert Path(CreateRadioButtons.DEFAULT_FILENAME).exists()


def test_create_radio_buttons_main_with_empty_argv(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("target").mkdir(exist_ok=True)
    CreateRadioButtons.main([])
    assert Path(CreateRadioButtons.DEFAULT_FILENAME).exists()


# ---------------------------------------------------------------------------
# Constructor — covers line 46
# ---------------------------------------------------------------------------


def test_constructor_is_no_op() -> None:
    instance = CreateRadioButtons()
    assert instance is not None


def test_class_exposes_default_filename() -> None:
    assert CreateRadioButtons.DEFAULT_FILENAME.endswith(".pdf")


# ---------------------------------------------------------------------------
# create_appearance_stream / draw_circle — covers 143-149
# ---------------------------------------------------------------------------


def test_create_appearance_stream_lite() -> None:
    assert CreateRadioButtons.create_appearance_stream(None, None, True) is None
    assert CreateRadioButtons.create_appearance_stream(None, None, False) is None


def test_draw_circle_emits_four_beziers() -> None:
    cs = mock.MagicMock()
    CreateRadioButtons.draw_circle(cs, x=10.0, y=20.0, r=5.0)
    cs.move_to.assert_called_once_with(10.0, 25.0)
    assert cs.curve_to.call_count == 4
    cs.close_path.assert_called_once()


# ---------------------------------------------------------------------------
# get_line_width — covers 113-116
# ---------------------------------------------------------------------------


class _StubWidgetWithBorder:
    def __init__(self, width: float) -> None:
        self._width = width

    def get_border_style(self):
        return _StubBorder(self._width)


class _StubWidgetNoBorder:
    def get_border_style(self):
        return None


class _StubBorder:
    def __init__(self, width: float) -> None:
        self._width = width

    def get_width(self) -> float:
        return self._width


def test_get_line_width_uses_border_style_when_present() -> None:
    widget = _StubWidgetWithBorder(2.5)
    assert CreateRadioButtons.get_line_width(widget) == 2.5


def test_get_line_width_defaults_to_one_when_no_border_style() -> None:
    widget = _StubWidgetNoBorder()
    assert CreateRadioButtons.get_line_width(widget) == 1.0


def test_get_line_width_uses_real_border_style_dictionary() -> None:
    """End-to-end with a real ``PDBorderStyleDictionary`` (mirrors the
    in-create code path)."""
    bs = PDBorderStyleDictionary()
    bs.set_width(4)

    class _RealWidget:
        def get_border_style(self):
            return bs

    assert CreateRadioButtons.get_line_width(_RealWidget()) == 4


# ---------------------------------------------------------------------------
# Fallback when set_widgets raises — covers 99-100
# ---------------------------------------------------------------------------


def test_create_falls_back_when_set_widgets_raises(
    tmp_path: Path, monkeypatch
) -> None:
    """If ``PDRadioButton.set_widgets`` raises, the workload extends the
    existing widgets list. We patch ``set_widgets`` to raise on every
    instance so the except branch executes."""
    from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

    original_set_widgets = PDRadioButton.set_widgets

    def _explode(self, widgets):
        raise RuntimeError("forced for branch coverage")

    monkeypatch.setattr(PDRadioButton, "set_widgets", _explode)
    out = tmp_path / "radio-fallback.pdf"
    try:
        CreateRadioButtons.create(str(out))
    finally:
        monkeypatch.setattr(PDRadioButton, "set_widgets", original_set_widgets)
    assert out.exists()
    assert out.stat().st_size > 0
