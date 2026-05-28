"""Live Apache PDFBox differential parity for the FontBox **Type 2
char-string parser** (``org.apache.fontbox.cff.Type2CharStringParser``) — the
byte-level decoder that turns a raw Type 2 char-string program (plus its
global / local /Subrs indexes) into the flat ``List<Object>`` of operands and
``CharStringCommand``s that ``Type2CharString`` then interprets.

This is upstream-distinct from the existing glyph-PATH / advance-width oracles
(``GlyphPathProbe`` / ``GlyphAdvanceProbe``): those pin the *rendered* outcome
(a ``GeneralPath`` / a width), while this one pins the decoder's *intermediate
token stream* directly. A divergence here is invisible to a path comparison
when it happens to cancel out, so the token stream is the sharper regression
pin for the parser branches:

* operand decoding for every Type 2 number encoding fontTools emits — the
  1-byte form (32-246), the 2-byte forms (247-254 / 251-254), the ``28``
  short-int, and the ``255`` 16.16 fixed (fractional operand);
* subroutine unrolling: ``callsubr`` inlines the local /Subrs bytes, biased
  via ``calculateSubrNumber``, with the trailing ``RET`` trimmed;
* hint operators (``hstem`` / ``hstemhm`` / ``vstemhm``) feeding the
  stem-count -> ``getMaskLength`` -> mask-byte-skip path for ``hintmask`` /
  ``cntrmask`` (including the implicit ``vstem`` count from operands left on
  the stack ahead of a mask).

Fixture
-------
``type2_parse.cff`` — a synthetic *name-keyed* (Type1C) CFF whose glyphs are
hand-designed so their compiled Type 2 programs cover, between them, every
decoder branch above. Generated deterministically by
``tests/fixtures/fontbox/cff/make_type2_parse_fixture.py`` (fontTools
``CFFFontSet.compile``, MIT) — the existing synthetic CFFs in that directory
carry only trivial ``100 endchar`` glyphs and never exercise the parser.

Both engines parse the *same* CFF bytes through their respective
``Type2CharStringParser``; any divergence in the emitted token stream is a
real decoder bug, not a byte-layout artifact.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"
_PARSE_CFF = _CFF_FIXTURES / "type2_parse.cff"


def _token(obj: object) -> str:
    """Canonical token for one parsed-sequence entry — mirrors the probe's
    ``CffType2ParseProbe.token`` field-for-field."""
    if isinstance(obj, CharStringCommand):
        # str(CharStringCommand) is "<keyword>|"; the keyword is the stable
        # mnemonic both engines share. Strip the trailing '|'.
        return str(obj).rstrip("|")
    if isinstance(obj, bool):  # pragma: no cover - guard; bool is not a token
        raise TypeError("unexpected bool token")
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return f"{obj:.4f}"
    return str(obj)  # pragma: no cover - defensive


def _parse_probe(text: str) -> tuple[int, bool, dict[int, tuple[int, list[str]]]]:
    """Parse ``CffType2ParseProbe read`` output.

    Returns ``(num_glyphs, is_type1, {gid: (token_count, tokens)})``.
    """
    num_glyphs = 0
    is_type1 = False
    glyphs: dict[int, tuple[int, list[str]]] = {}
    for line in text.splitlines():
        cols = line.split("\t")
        if cols[0] == "META" and len(cols) >= 3:
            num_glyphs = int(cols[1])
            is_type1 = cols[2] == "true"
        elif cols[0] == "GLY" and len(cols) >= 4:
            gid = int(cols[1])
            count = int(cols[2])
            tokens = cols[3].split("|") if cols[3] else []
            glyphs[gid] = (count, tokens)
        elif cols[0] == "GLY" and len(cols) == 3:
            # An empty-token glyph would not occur for this fixture, but keep
            # the parse total — a glyph with zero tokens still has a count.
            glyphs[int(cols[1])] = (int(cols[2]), [])
    return num_glyphs, is_type1, glyphs


def _py_glyphs(
    font: CFFType1Font,
) -> tuple[int, bool, dict[int, tuple[int, list[str]]]]:
    """pypdfbox-side token extraction — feeds the *same* inputs the probe does:
    the raw per-GID charstring bytes plus the global / local /Subrs indexes."""
    num_glyphs = font.get_num_char_strings()
    char_strings = font.get_char_string_bytes()
    gsubr = font.get_global_subr_index()
    lsubr = font.get_local_subr_index()
    parser = Type2CharStringParser(font.get_name())
    glyphs: dict[int, tuple[int, list[str]]] = {}
    for gid in range(num_glyphs):
        seq = parser.parse(char_strings[gid], gsubr, lsubr, f"gid{gid}")
        glyphs[gid] = (len(seq), [_token(x) for x in seq])
    return num_glyphs, True, glyphs


@requires_oracle
def test_type2_parser_token_stream_matches_pdfbox() -> None:
    assert _PARSE_CFF.is_file(), f"missing fixture: {_PARSE_CFF}"
    data = _PARSE_CFF.read_bytes()
    font = CFFParser().parse(data)[0]
    assert isinstance(font, CFFType1Font), "fixture must be a name-keyed CFF"

    probe_text = run_probe_text("CffType2ParseProbe", "read", str(_PARSE_CFF))
    java_num, java_is_t1, java_glyphs = _parse_probe(probe_text)
    py_num, py_is_t1, py_glyphs = _py_glyphs(font)

    assert py_num == java_num, ("num_glyphs", py_num, java_num)
    assert py_is_t1 == java_is_t1, ("is_type1", py_is_t1, java_is_t1)
    assert set(py_glyphs) == set(java_glyphs), (
        "gid set",
        sorted(py_glyphs),
        sorted(java_glyphs),
    )

    diffs: list[str] = []
    for gid in sorted(java_glyphs):
        j_count, j_tokens = java_glyphs[gid]
        p_count, p_tokens = py_glyphs[gid]
        if p_count != j_count:
            diffs.append(f"gid {gid}: token-count py={p_count} java={j_count}")
        if p_tokens != j_tokens:
            diffs.append(
                f"gid {gid}:\n  java={j_tokens}\n  py  ={p_tokens}"
            )
    assert not diffs, "Type2 parser token-stream parity broken:\n" + "\n".join(diffs)
