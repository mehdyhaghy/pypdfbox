from __future__ import annotations

from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import Type1Parser

_HEADER = b"""
%!PS-AdobeFont-1.0: Wave359 001.000
12 dict begin
/FontName /Wave359 def
/FontType 1 def
/FontMatrix [0.001 0 0 0.001 0 0] readonly def
/Encoding StandardEncoding def
"""


def _hex_eexec(plain: bytes) -> bytes:
    cipher = Type1FontUtil.eexec_encrypt(plain)
    text = Type1FontUtil.hex_encode(cipher)
    return (text[:10] + "\n\t" + text[10:26] + "\r\n" + text[26:]).encode("ascii")


def test_wave359_parser_decrypts_ascii_hex_eexec_segment() -> None:
    plain = b"dup /Private 2 dict dup begin /lenIV 4 def end\n"
    parser = Type1Parser()

    parser.parse(_HEADER, _hex_eexec(plain))

    assert parser.decrypted_binary == plain
    assert parser.font_dict["Private"]["lenIV"] == 4


def test_wave359_create_with_segments_accepts_ascii_hex_eexec_segment() -> None:
    plain = b"dup /Private 2 dict dup begin /lenIV 0 def end\n"

    font = Type1Font.create_with_segments(_HEADER, _hex_eexec(plain))

    assert font.decrypted_binary == plain
    assert font.get_len_iv() == 0
