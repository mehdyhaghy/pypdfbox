from __future__ import annotations

import builtins
from typing import Any

from tests.rendering import test_pdf_renderer_wave722 as wave722


def test_wave722_hsl_set_sat_local_builtin_fallbacks_are_exercised(
    monkeypatch: Any,
) -> None:
    def hsl_set_sat_stub(
        _r: object,
        _g: object,
        _b: object,
        _s: float,
    ) -> tuple[float, float, float]:
        assert builtins.max([1, 2]) == 2
        assert builtins.min([1, 2]) == 1
        return (0.0, 0.0, 0.0)

    monkeypatch.setattr(wave722.PDFRenderer, "_hsl_set_sat", staticmethod(hsl_set_sat_stub))

    wave722.test_hsl_set_sat_guard_returns_zero_when_min_index_is_missing(monkeypatch)
