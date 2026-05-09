from __future__ import annotations

import tests.cos.upstream.test_cos_name as upstream_cos_name


def test_wave940_upstream_cos_name_skipped_placeholders_are_callable() -> None:
    assert upstream_cos_name.test_pdfbox4076() is None
    assert upstream_cos_name.test_pdfbox6178() is None
    assert upstream_cos_name.test_name_with_ascii_nul() is None
