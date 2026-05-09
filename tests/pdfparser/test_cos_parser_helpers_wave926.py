from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from tests.pdfparser import test_cos_parser_wave515 as wave515


def test_wave926_xref_stream_dict_helper_accepts_float_and_name_widths() -> None:
    dictionary = wave515._xref_stream_dict([1, 2.5, "bad"])  # noqa: SLF001

    widths = dictionary.get_dictionary_object("W")

    assert isinstance(widths, COSArray)
    assert widths.size() == 3
    assert widths.get(0) is COSInteger.get(1)
    assert isinstance(widths.get(1), COSFloat)
    assert widths.get_object(1).float_value() == 2.5  # type: ignore[union-attr]
    assert widths.get(2) is COSName.get_pdf_name("bad")
