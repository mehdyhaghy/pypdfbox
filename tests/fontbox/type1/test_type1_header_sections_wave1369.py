"""Wave 1369 — Type 1 parser header / encoding / charstring section tests.

Covers the three top-level cleartext sections separately:

* the FontInfo header (FontName / FontInfo dict / FontMatrix / FontBBox);
* the Encoding section (predefined-name vs ``[ ... ]`` array vs the
  PostScript-built ``256 array ... dup K /name put`` form);
* the CharStrings section in the eexec-decrypted half (``/CharStrings N
  dict dup begin ... end``).

These are parser-shape tests, not full Type1Font round-trip tests — they
hit the dispatch entries in ``Type1Parser._parse_ascii`` /
``_parse_binary`` and the upstream-parity ``parse_ascii`` / ``parse_binary``
helpers directly so a future refactor can't drop a branch silently.
"""
from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.type1_font_util import Type1FontUtil
from pypdfbox.fontbox.type1.type1_parser import (
    Type1Parser,
)

_HEADER_BASE = """%!PS-AdobeFont-1.0: TestFont 001.000
11 dict begin
/FontInfo 6 dict dup begin
/version (001.000) def
/Notice (Test notice) def
/FullName (Test Regular) def
/FamilyName (Test) def
/Weight (Roman) def
/ItalicAngle 0 def
end def
/FontName /TestFont def
/FontType 1 def
/PaintType 0 def
/FontMatrix [0.001 0 0 0.001 0 0] readonly def
/FontBBox {-100 -200 1000 900} readonly def
"""


# ---------- header ----------


def test_header_emits_font_name_and_matrix_and_bbox() -> None:
    body = _HEADER_BASE + "/Encoding StandardEncoding def\ncurrentdict end\ncurrentfile eexec\n"
    parser = Type1Parser()
    parser.parse_ascii(body.encode("latin-1"))
    fd = parser.font_dict
    assert fd["FontName"] == "TestFont"
    assert fd["FontType"] == 1
    assert fd["PaintType"] == 0
    assert fd["FontMatrix"] == [0.001, 0, 0, 0.001, 0, 0]
    assert fd["FontBBox"] == [-100, -200, 1000, 900]
    # FontInfo hoists into its own sub-dict.
    info = fd["FontInfo"]
    assert info["FullName"] == "Test Regular"
    assert info["FamilyName"] == "Test"
    assert info["Weight"] == "Roman"
    assert info["Notice"] == "Test notice"


def test_header_parse_ascii_rejects_garbage_start() -> None:
    parser = Type1Parser()
    with pytest.raises(OSError, match="Invalid start"):
        parser.parse_ascii(b"garbage segment\n")


# ---------- encoding dispatch ----------


def test_encoding_standard_encoding_shortcut() -> None:
    # ``/Encoding StandardEncoding def`` — the upstream parity reader
    # stores the name verbatim as a string.
    src = (
        "%!PS\n3 dict dup begin\n"
        "/Encoding StandardEncoding def\n"
        "currentdict end\ncurrentfile eexec\n"
    )
    parser = Type1Parser()
    parser.parse_ascii(src.encode("latin-1"))
    assert parser.font_dict["Encoding"] == "StandardEncoding"


def test_encoding_array_dup_puts_into_dict() -> None:
    # ``/Encoding 256 array ... dup K /name put ... readonly def`` is the
    # explicit form — read_encoding stores a ``code -> name`` dict.
    src = (
        "%!PS\n3 dict dup begin\n"
        "/Encoding 256 array\n"
        "0 1 255 {1 index exch /.notdef put} for\n"
        "dup 65 /A put\n"
        "dup 66 /B put\n"
        "dup 67 /C put\n"
        "readonly def\n"
        "currentdict end\n"
        "currentfile eexec\n"
    )
    parser = Type1Parser()
    parser.parse_ascii(src.encode("latin-1"))
    enc = parser.font_dict["Encoding"]
    assert isinstance(enc, dict)
    assert enc[65] == "A"
    assert enc[66] == "B"
    assert enc[67] == "C"


def test_encoding_unknown_predefined_name_raises() -> None:
    # ``/Encoding TotallyMadeUp def`` — upstream raises IOException.
    src = (
        "%!PS\n3 dict dup begin\n"
        "/Encoding TotallyMadeUp def\n"
        "currentdict end\ncurrentfile eexec\n"
    )
    parser = Type1Parser()
    with pytest.raises(OSError, match="Unknown encoding"):
        parser.parse_ascii(src.encode("latin-1"))


def test_streaming_encoding_dup_into_positional_list() -> None:
    # The streaming parser path (``parse()``) builds a positional list
    # for custom encodings, NOT a dict — verify the two parsers really
    # use different representations.
    src = (
        "%!PS-AdobeFont-1.0: TestFont 001.000\n"
        "11 dict begin\n"
        "/FontName /TestFont def\n"
        "/Encoding 256 array\n"
        "  0 1 255 {1 index exch /.notdef put} for\n"
        "  dup 65 /A put\n"
        "  dup 90 /Z put\n"
        "readonly def\n"
    )
    parser = Type1Parser()
    parser.parse(src.encode("latin-1"), Type1FontUtil.eexec_encrypt(b""))
    enc = parser.font_dict["Encoding"]
    assert isinstance(enc, list)
    assert len(enc) == 256
    assert enc[65] == "A"
    assert enc[90] == "Z"
    # Unset slots default to ``.notdef``.
    assert enc[0] == ".notdef"


# ---------- CharStrings (eexec'd) ----------


def _build_charstrings_segment(entries: dict[str, bytes]) -> bytes:
    """Build a decrypted Type 1 Private dict containing the given
    glyph -> charstring map. Returns the eexec ciphertext."""
    pieces: list[bytes] = [b"dup /Private 6 dict dup begin\n/lenIV 4 def\n"]
    pieces.append(f"/CharStrings {len(entries)} dict dup begin\n".encode("latin-1"))
    for name, payload in entries.items():
        cipher = Type1FontUtil.charstring_encrypt(payload, len_iv=4)
        pieces.append(f"/{name} {len(cipher)} RD ".encode("latin-1"))
        pieces.append(cipher)
        pieces.append(b" ND\n")
    pieces.append(b"end\nend\n")
    plain = b"".join(pieces)
    return Type1FontUtil.eexec_encrypt(plain)


def test_charstrings_section_decrypts_each_entry() -> None:
    expected = {
        ".notdef": b"\x0e",                       # endchar
        "A":      b"\x0d\x0e",                    # closepath, endchar
        "B":      b"\x80\x90hsbw\x0e",            # arbitrary opaque bytes
    }
    parser = Type1Parser()
    parser.parse(_HEADER_BASE.encode("latin-1"), _build_charstrings_segment(expected))
    cs = parser.font_dict["CharStrings"]
    for name, payload in expected.items():
        assert cs[name] == payload, f"glyph {name} mismatch"


def test_charstrings_section_empty_dict() -> None:
    # ``/CharStrings 0 dict dup begin end`` — zero glyphs. Should not raise.
    parser = Type1Parser()
    parser.parse(_HEADER_BASE.encode("latin-1"), _build_charstrings_segment({}))
    # Empty charstrings: the parser may omit the key or set it to {}.
    cs = parser.font_dict.get("CharStrings", {})
    assert cs == {}


# ---------- Wrong-key detection ----------


def test_parser_decrypted_binary_matches_eexec_plaintext() -> None:
    # Sanity: ``decrypted_binary`` is the recovered plaintext, not the
    # raw ciphertext. Mismatching it would mean the eexec_decrypt
    # plumbing in ``parse()`` is wrong.
    plain = b"<encrypted body sentinel>"
    cipher = Type1FontUtil.eexec_encrypt(plain)
    parser = Type1Parser()
    parser.parse(_HEADER_BASE.encode("latin-1"), cipher)
    assert parser.decrypted_binary == plain
