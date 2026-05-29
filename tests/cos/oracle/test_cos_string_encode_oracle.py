"""Live PDFBox differential parity for COSString text→bytes ENCODING.

Surface: the ``new COSString(String)`` constructor (PDF 32000-1 §7.9.2.2) —
how a text string is encoded to the underlying byte payload:

* every char representable in PDFDocEncoding  → PDFDocEncoding bytes;
* any char outside PDFDocEncoding              → UTF-16BE with a ``FE FF`` BOM.

This is the *encode* direction and is complementary to the prior wave's
*decode* coverage (``parseHex(...).getString()``); we do not repeat decode here.

The Java probe ``CosStrEncodeProbe`` takes the input string as the UTF-16BE
hex of its UTF-16 code units (so the exact ``char[]`` is unambiguous across
the shell / argv boundary) and emits, per mode:

* ``enc`` — hex of ``new COSString(text).getBytes()``;
* ``rt``  — space-separated hex of each code point of
  ``new COSString(text).getString()`` (for the construct→read round-trip).

We assert pypdfbox's ``COSString(s).get_bytes()`` is byte-identical to Java
and that ``COSString(s).get_string()`` round-trips back to ``s``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_string import COSString
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Encode battery — (id, python str)
# --------------------------------------------------------------------------- #

_STRINGS: tuple[tuple[str, str], ...] = (
    # Pure ASCII → PDFDocEncoding (identity in this range)
    ("empty", ""),
    ("hello", "Hello"),
    ("ascii_space", "A B C"),
    ("digits", "0123456789"),
    ("punct", "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"),
    ("with_nul", "A\x00B"),
    ("tab", "A\tB"),
    ("newline", "line1\nline2"),
    # Latin-1 chars that ARE in PDFDocEncoding → single-byte PDFDocEncoding
    ("e_acute", "café"),  # café
    ("u_uml", "Müller"),  # Müller
    ("n_tilde", "mañana"),  # mañana
    ("a_ring", "Ångström"),  # Ångström
    ("latin1_high", "¡¿ÿ"),  # ¡¿ÿ
    # PDFDocEncoding deviation chars (high block 0x80-0xA0) → single byte
    ("bullet", "•"),  # • → 0x80
    ("dagger", "†"),  # † → 0x81
    ("ellipsis", "…"),  # … → 0x83
    ("emdash", "a—b"),  # em dash → 0x84
    ("euro", "€"),  # € → 0xA0
    ("trademark", "™"),  # ™ → 0x92
    ("fi_ligature", "ﬁ"),  # ﬁ → 0x93
    ("quotes", "“quoted”"),  # “quoted” → 0x8D..0x8E
    ("mixed_pde", "Price: ’85‰"),  # ’ + ‰ → still PDFDocEncoding
    # Chars OUTSIDE PDFDocEncoding → UTF-16BE + FE FF BOM
    ("cjk", "日本語"),  # 日本語
    ("cyrillic", "Привет"),  # Привет
    ("greek", "αβγ"),  # αβγ
    ("hebrew", "שלום"),  # שלום
    ("arabic", "مرحبا"),  # مرحبا
    # Mixed: one out-of-PDFDocEncoding char forces the WHOLE string to UTF-16BE
    ("mixed_ascii_cjk", "Hi 你好"),  # "Hi 你好"
    ("ascii_then_emoji", "ok\U0001f600"),  # supplementary (astral) emoji
    ("emoji_only", "\U0001f4a9"),  # pile of poo (supplementary)
    ("supp_pair", "\U0001f600\U0001f601"),  # two astral code points
    # A char in the Latin-1 byte range but NOT in PDFDocEncoding: 0xAD SOFT
    # HYPHEN is undefined in PDFDocEncoding, so the string goes UTF-16BE.
    ("soft_hyphen", "a­b"),
    # 0x7F / 0x9F undefined slots map to U+FFFD in the table → not containable
    # so a literal U+007F still IS representable (control retained as identity)
    ("del_control", "\x7f"),
)


def _utf16be_hex(s: str) -> str:
    """The probe's input encoding: lower-hex of the string's UTF-16BE bytes."""
    return s.encode("utf-16-be").hex()


@requires_oracle
@pytest.mark.parametrize("name,text", _STRINGS, ids=[n for n, _ in _STRINGS])
def test_cos_string_constructor_bytes_match_pdfbox(name: str, text: str) -> None:
    """``new COSString(text).getBytes()`` parity, byte-for-byte."""
    java = run_probe_text("CosStrEncodeProbe", "enc", _utf16be_hex(text))
    py = COSString(text).get_bytes().hex()
    assert py == java


@requires_oracle
@pytest.mark.parametrize("name,text", _STRINGS, ids=[n for n, _ in _STRINGS])
def test_cos_string_round_trip_matches_pdfbox(name: str, text: str) -> None:
    """``getString(new COSString(s))`` round-trips to ``s`` and agrees with
    PDFBox's own round-trip (compared as space-separated code-point hex)."""
    java = run_probe_text("CosStrEncodeProbe", "rt", _utf16be_hex(text))
    s = COSString(text).get_string()
    py = " ".join(format(ord(ch), "x") for ch in s)
    assert py == java
    # And the Python-native round-trip identity holds.
    assert s == text


@requires_oracle
def test_pdfdoc_vs_utf16_selection_boundary() -> None:
    """Confirm the selection rule directly: a pure-PDFDocEncoding string has no
    BOM and is single-byte; adding one out-of-range char flips the whole
    payload to UTF-16BE + FE FF, matching PDFBox."""
    pde = COSString("café").get_bytes()
    assert not pde.startswith(b"\xfe\xff")
    assert pde == bytes([0x63, 0x61, 0x66, 0xe9])  # 'c','a','f',0xe9
    assert run_probe_text("CosStrEncodeProbe", "enc", _utf16be_hex("café")) == pde.hex()

    u16 = COSString("café日").get_bytes()  # café + 日
    assert u16.startswith(b"\xfe\xff")
    assert u16 == b"\xfe\xff" + "café日".encode("utf-16-be")
    assert run_probe_text("CosStrEncodeProbe", "enc", _utf16be_hex("café日")) == u16.hex()
