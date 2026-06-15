"""Wave 1523 — live PDFBox differential parity for the COSName ``#XX``
hex-escape decode + byte->String round-trip surface.

``ParseLiteralNameProbe`` / ``NameWriteEscapeProbe`` cover the literal-string
parse and the COSName *write* escape. This file targets the orthogonal *read*
round-trip: raw PDF name-token bytes (``#XX`` escapes and raw high bytes) are
fed through ``PDFStreamParser`` — which dispatches to
``BaseParser.parseCOSName()`` — and the resulting ``COSName.getName()`` is
projected as UTF-8 hex and compared byte-for-byte against Apache PDFBox 3.0.7.

The load-bearing decision this exercises is the **decode fallback** for name
bytes that are not valid UTF-8. Upstream's ``ALTERNATIVE_CHARSET`` is
``Windows-1252`` (cp1252), not ISO-8859-1: the two agree on 0x00-0x7F and
0xA0-0xFF but diverge across 0x80-0x9F, where cp1252 maps the printable C1
slots (0x80 -> euro U+20AC, 0x9F -> U+0178, ...) and decodes the five
undefined slots (0x81/0x8D/0x8F/0x90/0x9D) to U+FFFD. pypdfbox stores raw name
bytes and decodes lazily in ``COSName.get_name()``; before wave 1523 it used a
latin-1 fallback, which diverged across 0x80-0x9F. Now it uses cp1252 + replace
to match ``new String(bytes, Charset.forName("Windows-1252"))``.

Also covered: ``#XX`` decoding (upper/lowercase/mixed hex), multi-byte UTF-8 via
consecutive ``#XX`` escapes, lenient recovery (``#`` with < 2 hex digits kept
literally, premature-EOF drop), the empty name, and very long all-escaped names.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------------- #
# Each case is (short_id, raw PDF name-token syntax bytes). The oracle supplies
# the expected decoded name. Tokens that would otherwise run to EOF carry a
# trailing space (0x20) name-delimiter so the decode terminates cleanly.
# --------------------------------------------------------------------------- #

_CASES: tuple[tuple[str, bytes], ...] = (
    # ---- plain + basic #XX hex-escape decode ----
    ("plain", b"/Type"),
    ("esc_A", b"/A#41B"),  # '#41' -> 'A'
    ("esc_lower", b"/A#6aB"),  # lowercase hex
    ("esc_mixed", b"/A#aFB"),  # mixed-case hex
    ("esc_hash", b"/A#23B"),  # '#23' -> '#'
    ("esc_slash", b"/A#2FB"),  # '#2F' -> '/'
    ("esc_lparen", b"/A#28B"),  # '#28' -> '('
    ("esc_space", b"/A#20B"),  # '#20' -> ' '
    ("esc_null", b"/A#00B"),  # '#00' -> NUL byte in name
    # ---- 0x80-0x9F cp1252 vs latin-1 fallback (the wave-1523 fix) ----
    ("hi_80_esc", b"/X#80 "),  # cp1252: euro U+20AC
    ("hi_9f_esc", b"/X#9F "),  # cp1252: U+0178
    ("hi_82_esc", b"/X#82 "),  # cp1252: U+201A
    ("hi_95_esc", b"/X#95 "),  # cp1252: bullet U+2022
    ("hi_8d_esc", b"/X#8D "),  # undefined slot -> U+FFFD
    ("hi_81_esc", b"/X#81 "),  # undefined slot -> U+FFFD
    ("hi_80_raw", b"/X\x80 "),  # raw high byte, same as #80
    ("hi_9f_raw", b"/X\x9f "),
    ("hi_8d_raw", b"/X\x8d "),
    # ---- 0xA0-0xFF agree across cp1252 / latin-1 ----
    ("hi_a9_esc", b"/X#A9 "),  # copyright U+00A9
    ("hi_ff_esc", b"/X#FF "),  # y-diaeresis U+00FF
    ("hi_ff_raw", b"/X\xff "),
    # ---- multi-byte UTF-8 via consecutive #XX (decodes to one codepoint) ----
    ("mb_eacute", b"/A#C3#A9 "),  # e-acute U+00E9
    ("mb_euro", b"/A#E2#82#AC "),  # euro U+20AC
    ("mb_emoji", b"/A#F0#9F#98#80 "),  # 4-byte emoji
    ("mb_raw_eacute", b"/A\xc3\xa9 "),
    # ---- invalid UTF-8 raw bytes -> cp1252 fallback ----
    ("lone_cont_80", b"/A\x80B "),  # lone continuation byte
    ("trunc_c3", b"/A\xc3B "),  # truncated 2-byte lead
    ("raw_81", b"/A\x81B "),  # undefined cp1252 slot mid-name
    # ---- lenient recovery: '#' with < 2 hex digits kept literally ----
    ("hash_nohex", b"/A#GB "),  # '#G' not hex -> literal '#'
    ("hash_4G", b"/A#4G "),  # second digit non-hex
    ("hash_G1", b"/A#G1 "),  # first digit non-hex
    ("hash_one_digit", b"/AB#4 "),  # '#4' then delimiter
    ("hash_at_end", b"/AB#"),  # trailing '#' then EOF
    ("hash_at_end_sp", b"/AB# "),  # trailing '#' then delimiter
    # ---- empty + boundary names ----
    ("empty_sp", b"/ "),  # empty name (slash then space)
    ("empty_bracket", b"/]"),  # empty name (delimiter terminates)
    ("empty_gt", b"/>"),
    # ---- very long all-escaped name ----
    ("long_escaped", b"/" + b"#41" * 40 + b" "),
)


def _py_render(syntax: bytes) -> str:
    """pypdfbox decode rendered like the Java probe's ``render``."""
    tok = PDFStreamParser.from_bytes(syntax).parse_next_token()
    if tok is None:
        return "NULL"
    if isinstance(tok, COSName):
        return "NAME:" + tok.get_name().encode("utf-8").hex()
    return "OTHER:" + type(tok).__name__


@requires_oracle
@pytest.mark.parametrize(("case_id", "syntax"), _CASES, ids=[c[0] for c in _CASES])
def test_cos_name_hex_escape_matches_pdfbox(case_id: str, syntax: bytes) -> None:
    java = run_probe_text("CosNameHexEscapeFuzzProbe", syntax.hex())
    py = _py_render(syntax)
    assert py == java
