"""Wave 1023 coverage for pdfdebugger wave384 test helpers."""
from __future__ import annotations

import tests.tools.test_pdfdebugger_wave384 as wave384


def test_wave1023_unknown_cos_accept_returns_none() -> None:
    assert wave384._UnknownCOS().accept(object()) is None
