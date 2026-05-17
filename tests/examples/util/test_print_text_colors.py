"""Tests for :class:`PrintTextColors`."""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from pypdfbox.examples.util.print_text_colors import PrintTextColors


def test_run_runs(make_pdf: Callable[..., Path]) -> None:
    src = make_pdf("colors.pdf")
    PrintTextColors.run(str(src))


def test_main_with_zero_args_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PrintTextColors.main([])
    err = capsys.readouterr().err
    assert "Usage" in err
    assert "PrintTextColors" in err


def test_main_with_two_args_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PrintTextColors.main(["a.pdf", "b.pdf"])
    err = capsys.readouterr().err
    assert "Usage" in err


def test_main_with_none_argv_emits_usage(capsys: pytest.CaptureFixture[str]) -> None:
    PrintTextColors.main(None)
    err = capsys.readouterr().err
    assert "Usage" in err


def test_main_with_one_arg_drives_run(
    make_pdf: Callable[..., Path],
) -> None:
    src = make_pdf("colors-main.pdf")
    PrintTextColors.main([str(src)])


def test_usage_message_targets_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    PrintTextColors.usage()
    out = capsys.readouterr()
    assert "PrintTextColors" in out.err
    assert out.out == ""


def test_constructor_is_a_text_stripper() -> None:
    from pypdfbox.text.pdf_text_stripper import PDFTextStripper

    obj = PrintTextColors()
    assert isinstance(obj, PDFTextStripper)


class _StubTextPos:
    """Minimal ``TextPosition`` surrogate exposing ``get_unicode``."""

    def __init__(self, ch: str) -> None:
        self._ch = ch

    def get_unicode(self) -> str:
        return self._ch


class _StubTextState:
    def get_rendering_mode(self) -> int:
        return 3


class _StubGraphicsState:
    def __init__(
        self,
        *,
        stroking: object = "RGB(1,0,0)",
        non_stroking: object = "RGB(0,1,0)",
        text_state: object | None = None,
    ) -> None:
        self._stroking = stroking
        self._non_stroking = non_stroking
        self._text_state = text_state

    def get_stroking_color(self) -> object:
        return self._stroking

    def get_non_stroking_color(self) -> object:
        return self._non_stroking

    def get_text_state(self) -> object | None:
        return self._text_state


def test_process_text_position_writes_all_attributes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stripper = PrintTextColors()
    state = _StubGraphicsState(text_state=_StubTextState())
    stripper.get_graphics_state = lambda: state  # type: ignore[attr-defined]
    stripper.process_text_position(_StubTextPos("A"))
    out = capsys.readouterr().out
    assert "Unicode:            A" in out
    assert "Rendering mode:     3" in out
    assert "RGB(1,0,0)" in out
    assert "RGB(0,1,0)" in out


def test_process_text_position_handles_missing_graphics_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stripper = PrintTextColors()

    def _raise() -> object:
        raise RuntimeError("no state")

    stripper.get_graphics_state = _raise  # type: ignore[attr-defined]
    stripper.process_text_position(_StubTextPos("B"))
    out = capsys.readouterr().out
    assert "Stroking color:     None" in out
    assert "Non-Stroking color: None" in out


def test_process_text_position_handles_state_without_text_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stripper = PrintTextColors()
    state = _StubGraphicsState(text_state=None)
    stripper.get_graphics_state = lambda: state  # type: ignore[attr-defined]
    stripper.process_text_position(_StubTextPos("C"))
    out = capsys.readouterr().out
    assert "Rendering mode:     None" in out


def test_process_text_position_handles_none_gs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stripper = PrintTextColors()
    stripper.get_graphics_state = lambda: None  # type: ignore[attr-defined]
    stripper.process_text_position(_StubTextPos("D"))
    out = capsys.readouterr().out
    assert "Unicode:            D" in out
    assert "Stroking color:     None" in out


def test_module_entry_point_invokable() -> None:
    """The ``__main__`` guard is covered by ``main`` itself; ensure both
    sides of the ``argv`` ternary are exercised."""
    # argv None -> argv = []
    sink = io.StringIO()
    old_err, sys.stderr = sys.stderr, sink
    try:
        PrintTextColors.main(None)
    finally:
        sys.stderr = old_err
    assert "Usage" in sink.getvalue()
