from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

_CUSTOM_ENCODING_HEADER = b"""
%!PS-AdobeFont-1.0: Wave337 001.000
12 dict begin
/FontName /Wave337 def
/FontType 1 def
/FontMatrix [0.001 0 0 0.001 0 0] readonly def
/Encoding 256 array
0 1 255 {1 index exch /.notdef put} for
dup 32 /space put
dup 65 /A put
dup 196 /Adieresis put
readonly def
"""


def test_wave337_parser_reads_dup_put_encoding_array() -> None:
    parser = Type1Parser()
    parser.parse(_CUSTOM_ENCODING_HEADER, Type1FontUtil.eexec_encrypt(b""))

    encoding = parser.font_dict["Encoding"]
    assert encoding[32] == "space"
    assert encoding[65] == "A"
    assert encoding[196] == "Adieresis"
    assert encoding[66] == ".notdef"


def test_wave337_font_exposes_custom_dup_put_encoding() -> None:
    font = Type1Font.create_with_segments(
        _CUSTOM_ENCODING_HEADER,
        Type1FontUtil.eexec_encrypt(b""),
    )

    assert font.get_encoding() == {
        32: "space",
        65: "A",
        196: "Adieresis",
    }
