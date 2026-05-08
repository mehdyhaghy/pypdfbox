from __future__ import annotations

from pypdfbox.cos import COSString


def test_wave322_get_ascii_camelcase_alias_matches_pdfbox_name() -> None:
    cos_string = COSString(b"D:20260508090000\xff")

    assert cos_string.getASCII() == cos_string.get_ascii()
    assert cos_string.getASCII() == "D:20260508090000?"
