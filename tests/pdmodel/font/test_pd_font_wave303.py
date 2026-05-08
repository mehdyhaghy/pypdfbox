from __future__ import annotations

from pypdfbox.cos import COSName, COSNull, COSString
from pypdfbox.pdmodel.font import PDFont


class _BarePDFont(PDFont):
    SUB_TYPE = None


def test_wave303_has_to_unicode_reports_explicit_null_entry() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), COSNull.NULL)

    assert font.has_to_unicode() is True
    assert font.get_to_unicode_cmap() is None


def test_wave303_has_to_unicode_reports_malformed_entry() -> None:
    font = _BarePDFont()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("ToUnicode"), COSString("not a cmap")
    )

    assert font.has_to_unicode() is True
    assert font.get_to_unicode_cmap() is None


def test_wave303_has_to_unicode_false_when_key_absent() -> None:
    assert _BarePDFont().has_to_unicode() is False
