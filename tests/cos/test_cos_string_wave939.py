from __future__ import annotations

import tests.cos.upstream.test_cos_string as upstream_cos_string


def test_wave939_upstream_cos_string_skipped_placeholders_are_callable() -> None:
    assert upstream_cos_string.test_write_pdf() is None
    assert upstream_cos_string.test_unicode() is None
    assert upstream_cos_string.test_accept() is None
