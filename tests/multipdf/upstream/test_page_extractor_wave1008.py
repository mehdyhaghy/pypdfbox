from __future__ import annotations

from tests.multipdf.upstream.test_page_extractor import _close_doc


class _CloseRaises:
    def close(self) -> None:
        raise RuntimeError("close failed")


def test_wave1008_close_doc_swallows_close_errors() -> None:
    _close_doc(_CloseRaises())  # type: ignore[arg-type]
