from __future__ import annotations

import builtins
from collections.abc import Callable
from typing import Any

from pypdfbox.rendering.pdf_renderer import PDFRenderer, _AggdrawPathPen


def test_hsl_clip_color_uses_luminance_when_low_denominator_zero(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        PDFRenderer,
        "_hsl_lum",
        staticmethod(lambda _r, _g, _b: -0.5),
    )

    assert PDFRenderer._hsl_clip_color(-0.5, 0.2, 0.4) == (  # noqa: SLF001
        -0.5,
        -0.5,
        -0.5,
    )


def test_hsl_clip_color_uses_luminance_when_high_denominator_zero(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        PDFRenderer,
        "_hsl_lum",
        staticmethod(lambda _r, _g, _b: 1.5),
    )

    assert PDFRenderer._hsl_clip_color(1.5, 0.1, 0.2) == (  # noqa: SLF001
        1.5,
        1.5,
        1.5,
    )


def test_hsl_set_sat_guard_returns_zero_when_min_index_is_missing(
    monkeypatch: Any,
) -> None:
    original_max: Callable[[object], object] = builtins.max
    original_min: Callable[[object], object] = builtins.min
    max_marker = object()
    min_marker = object()

    def fake_max(values: object) -> object:
        if isinstance(values, list) and values and values[0] is max_marker:
            return max_marker
        return original_max(values)

    def fake_min(values: object) -> object:
        if isinstance(values, list) and values and values[0] is max_marker:
            return min_marker
        return original_min(values)

    middle = object()
    high = object()
    monkeypatch.setattr(builtins, "max", fake_max)
    monkeypatch.setattr(builtins, "min", fake_min)

    assert PDFRenderer._hsl_set_sat(max_marker, middle, high, 0.5) == (  # type: ignore[arg-type]  # noqa: SLF001
        0.0,
        0.0,
        0.0,
    )


def test_aggdraw_path_pen_qcurve_handles_trailing_single_offcurve(
    monkeypatch: Any,
) -> None:
    original_len: Callable[[object], int] = builtins.len
    calls = 0

    def fake_len(value: object) -> int:
        nonlocal calls
        if (
            isinstance(value, list)
            and original_len(value) == 2
            and all(isinstance(item, tuple) and original_len(item) == 2 for item in value)
        ):
            calls += 1
            if calls > 1:
                return 1
        return original_len(value)

    pen = _AggdrawPathPen(scale=1.0)
    pen.move_to((0.0, 0.0))
    monkeypatch.setattr(builtins, "len", fake_len)

    pen.q_curve_to((1.0, 1.0), (2.0, 2.0))

    assert pen.has_segments is True
    assert pen._last == (1.0, 1.0)  # noqa: SLF001
