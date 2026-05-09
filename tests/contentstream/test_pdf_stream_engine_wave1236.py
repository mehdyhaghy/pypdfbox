from __future__ import annotations

import pytest

from tests.contentstream import test_pdf_stream_engine_wave1228 as wave1228


def test_wave1236_find_nested_code_raises_when_name_is_missing() -> None:
    with pytest.raises(AssertionError, match="definitely_missing not found"):
        wave1228._find_nested_code(  # noqa: SLF001
            test_wave1236_find_nested_code_raises_when_name_is_missing.__code__,
            "definitely_missing",
        )
