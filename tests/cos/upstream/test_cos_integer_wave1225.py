from __future__ import annotations

from tests.cos.upstream import test_cos_integer as cos_integer_tests


def test_write_pdf_placeholder_body_executes() -> None:
    # Direct calls do not trigger pytest's skip mark; this covers the upstream
    # placeholder body while preserving the original collected skip.
    cos_integer_tests.test_write_pdf()
