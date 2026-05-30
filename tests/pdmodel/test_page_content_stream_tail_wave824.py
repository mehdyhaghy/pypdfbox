from __future__ import annotations

from pypdfbox.pdmodel import pd_page_content_stream as content_stream_module


def test_wave824_format_number_preserves_negative_zero() -> None:
    # A value whose float32 fraction truncates to zero under formatFloatFast
    # but is negative keeps the leading '-' on the zero integer part, exactly
    # as PDFBox's buffer writer leaves it (e.g. -0.000005f -> "-0").
    assert content_stream_module._format_number(-0.000005) == b"-0"
