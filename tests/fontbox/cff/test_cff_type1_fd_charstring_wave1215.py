from __future__ import annotations

import pytest

from tests.fontbox.cff import test_cff_type1_fd_charstring_wave700 as wave700_mod


def test_wave1215_fd_array_bad_lookup_len_branch_is_executed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_fd_array = wave700_mod.FDArray

    class _FDArrayProxy:
        @staticmethod
        def from_fonttools(fdarray: object) -> object:
            assert len(fdarray) == 1  # type: ignore[arg-type]
            return real_fd_array.from_fonttools(fdarray)

    monkeypatch.setattr(wave700_mod, "FDArray", _FDArrayProxy)

    wave700_mod.test_wave700_fd_array_raw_lookup_exceptions_are_safe()
