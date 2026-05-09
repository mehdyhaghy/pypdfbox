"""Coverage for defensive branches in ``test_cmap_enrichment``."""

from __future__ import annotations

import pytest

from tests.fontbox.cmap import test_cmap_enrichment as target


class _ZeroTailCMap:
    def __init__(self) -> None:
        self._reads = iter(
            [
                (0x1234, 1),
                (0x5678, 1),
                (0x9ABC, 1),
                (0, 0),
            ]
        )

    def add_codespace_range(self, _start: bytes, _end: bytes) -> None:
        return None

    def read_code(self, _buf: bytes, *, offset: int = 0) -> tuple[int, int]:
        return next(self._reads)


def test_offset_walk_breaks_on_zero_length_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "CMap", _ZeroTailCMap)

    target.test_read_code_bytes_offset_walk()
