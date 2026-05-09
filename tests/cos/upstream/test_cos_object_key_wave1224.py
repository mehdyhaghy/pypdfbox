from __future__ import annotations

from tests.cos.upstream import test_cos_object_key as target


def test_wave1224_executes_skipped_pdfbox5742_body() -> None:
    target.test_pdfbox5742()
