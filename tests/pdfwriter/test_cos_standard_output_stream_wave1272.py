"""Wave 1272: parity coverage for ``COSStandardOutputStream`` snake-case
``is_on_new_line`` / ``set_on_new_line`` spellings (matching upstream's
``isOnNewLine`` / ``setOnNewLine`` word boundaries)."""

from __future__ import annotations

from io import BytesIO

from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream


def test_is_on_new_line_starts_false() -> None:
    out = COSStandardOutputStream(BytesIO())
    assert out.is_on_new_line() is False


def test_is_on_new_line_after_eol() -> None:
    out = COSStandardOutputStream(BytesIO())
    out.write(b"abc")
    out.write_eol()
    assert out.is_on_new_line() is True


def test_set_on_new_line_round_trips() -> None:
    out = COSStandardOutputStream(BytesIO())
    out.set_on_new_line(True)
    assert out.is_on_new_line() is True
    assert out.is_on_newline() is True  # both spellings agree
    out.set_on_new_line(False)
    assert out.is_on_new_line() is False
