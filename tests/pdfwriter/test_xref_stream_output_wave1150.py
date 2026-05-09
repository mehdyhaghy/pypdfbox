from __future__ import annotations

import pytest

from . import test_xref_stream_output_wave887 as wave887


def test_wave1150_startxref_helper_test_reports_unexpected_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wave887, "_with_correct_startxref", lambda payload: payload)

    with pytest.raises(AssertionError, match="expected missing-object assertion"):
        wave887.test_wave887_startxref_helper_reports_missing_object()
