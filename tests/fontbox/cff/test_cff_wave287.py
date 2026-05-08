from __future__ import annotations

import io

from pypdfbox.fontbox.cff.cff_font import CFFFont, read_charset
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.fd_array import FDArray


def test_read_charset_non_positive_glyph_count_returns_empty_without_reading() -> None:
    stream = io.BytesIO(b"\x05\x00\x01")

    assert read_charset(stream, 0) == []
    assert stream.tell() == 0

    assert read_charset(stream, -3) == []
    assert stream.tell() == 0


def test_cff_font_properties_tolerate_untyped_standard_strings() -> None:
    font = CFFFont()

    assert font.get_sid("A") == 34
    assert font.get_string(34) == "A"


def test_type1_encoding_predicates_return_real_bools() -> None:
    class _Top:
        Encoding = "StandardEncoding"

    font = CFFType1Font()
    font._top = _Top()  # noqa: SLF001

    assert font.is_standard_encoding() is True
    assert font.is_expert_encoding() is False


def test_fd_array_iterates_dict_snapshots() -> None:
    class _Font:
        rawDict = {"FontName": "Demo"}  # noqa: N815
        Private = None

    array = FDArray.from_fonttools([_Font()])

    assert list(array) == [{"FontName": "Demo"}]
