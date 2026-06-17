"""Diacritic / combining-character parity fuzz — wave 1587 (Agent D).

Hammers :class:`pypdfbox.text.text_position.TextPosition` diacritic logic
and :meth:`pypdfbox.text.pdf_text_stripper.PDFTextStripper.normalize_word`
against the behaviour of Apache PDFBox 3.0.7's ``TextPosition`` /
``PDFTextStripper``:

- ``isDiacritic`` — single-char, U+30FC exclusion (PDFBOX-3833), and the
  ``NON_SPACING_MARK``/``MODIFIER_SYMBOL``/``MODIFIER_LETTER`` (``Mn``/
  ``Sk``/``Lm``) category classification (``TextPosition.java:808``).
- ``combineDiacritic`` — the non-decomposing remap table plus the NFKC +
  trim fallback (``TextPosition.java:793``).
- ``insertDiacritic`` — combining mark goes *after* the base char
  (``TextPosition.java:753``).
- ``mergeDiacritic`` x-overlap (``contains`` driving which base the mark
  attaches to).
- ``normalizeWord`` — NFKC of presentation forms (``PDFTextStripper.java``).
"""

from __future__ import annotations

import unicodedata

import pytest

from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.text.text_position import _DIACRITICS, TextPosition


def _tp(text: str, x: float = 0.0, width: float = 10.0, **kw) -> TextPosition:
    base: dict = {
        "text": text,
        "x": x,
        "y": 0.0,
        "font_size": 12.0,
        "width": width,
    }
    base.update(kw)
    return TextPosition(**base)


# ---------------------------------------------------------------------------
# isDiacritic — category classification (Mn / Sk / Lm), length-1, U+30FC
# ---------------------------------------------------------------------------

# Single combining (Mn) marks across the U+0300..036F range -> diacritic.
@pytest.mark.parametrize(
    "cp",
    [0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x030A, 0x0327, 0x0359, 0x036F],
    ids=lambda c: f"Mn_{c:04X}",
)
def test_is_diacritic_true_for_single_combining_mark(cp: int) -> None:
    ch = chr(cp)
    assert unicodedata.category(ch) == "Mn"
    assert _tp(ch).is_diacritic() is True


# Modifier symbols (Sk) and modifier letters (Lm) -- the very characters that
# feed the DIACRITICS remap table. Upstream classifies these as diacritics;
# the old combining()-based check missed them (combining class 0).
@pytest.mark.parametrize(
    "cp",
    [0x005E, 0x0060, 0x02C6, 0x02DC, 0x00B0, 0x02CB, 0x02CA, 0x02C7, 0x02D4],
    ids=lambda c: f"Sk_{c:04X}",
)
def test_is_diacritic_true_for_modifier_symbol(cp: int) -> None:
    ch = chr(cp)
    cat = unicodedata.category(ch)
    assert cat in ("Sk", "So", "Lm")
    # Only the Sk / Lm ones are diacritics per upstream; So (e.g. U+00B0 in
    # some Python versions) is not. Assert against the actual category.
    expected = cat in ("Mn", "Sk", "Lm")
    assert _tp(ch).is_diacritic() is expected


@pytest.mark.parametrize(
    "cp",
    [0x02B9, 0x02C9, 0x02B2, 0x02B7, 0x02CC, 0x02CD],
    ids=lambda c: f"Lm_{c:04X}",
)
def test_is_diacritic_true_for_modifier_letter(cp: int) -> None:
    ch = chr(cp)
    assert unicodedata.category(ch) == "Lm"
    assert _tp(ch).is_diacritic() is True


def test_is_diacritic_false_for_prolonged_sound_mark() -> None:
    # PDFBOX-3833: U+30FC is a Lm but explicitly excluded.
    assert unicodedata.category("ー") == "Lm"
    assert _tp("ー").is_diacritic() is False


def test_is_diacritic_false_for_empty() -> None:
    assert _tp("").is_diacritic() is False


@pytest.mark.parametrize(
    "text",
    ["ab", "á", "́̂", "fi", "è́"],
    ids=["two_letters", "base_plus_mark", "two_marks", "ligature", "base_two"],
)
def test_is_diacritic_false_for_multi_char(text: str) -> None:
    # Upstream requires exactly one character regardless of category.
    assert _tp(text).is_diacritic() is False


@pytest.mark.parametrize(
    "ch", ["a", "Z", "5", " ", ".", "字", "ש"],
    ids=["lower", "upper", "digit", "space", "dot", "cjk", "hebrew"],
)
def test_is_diacritic_false_for_ordinary_glyph(ch: str) -> None:
    assert _tp(ch).is_diacritic() is False


def test_is_diacritic_false_for_combining_spacing_mark() -> None:
    # Mc (combining spacing mark) has combining()!=0 but is NOT a diacritic
    # per upstream (NON_SPACING_MARK only). U+0903 DEVANAGARI SIGN VISARGA.
    ch = "ः"
    assert unicodedata.category(ch) == "Mc"
    assert _tp(ch).is_diacritic() is False


# ---------------------------------------------------------------------------
# contains_diacritic (non-upstream helper) — first char is a combining mark
# ---------------------------------------------------------------------------


def test_contains_diacritic_true_when_starts_with_mark() -> None:
    assert _tp("́a").contains_diacritic() is True


def test_contains_diacritic_false_when_base_first() -> None:
    assert _tp("á").contains_diacritic() is False


def test_contains_diacritic_false_for_empty() -> None:
    assert _tp("").contains_diacritic() is False


# ---------------------------------------------------------------------------
# combineDiacritic — remap table + NFKC/trim fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cp", sorted(_DIACRITICS), ids=lambda c: f"{c:04X}")
def test_combine_diacritic_uses_remap_table(cp: int) -> None:
    src = chr(cp)
    out = TextPosition.combine_diacritic(src)
    assert out == _DIACRITICS[cp]
    # Every mapped target is a real combining mark.
    assert unicodedata.combining(out) != 0


def test_combine_diacritic_grave_to_combining() -> None:
    # U+0060 GRAVE ACCENT -> U+0300 COMBINING GRAVE.
    assert TextPosition.combine_diacritic("`") == "̀"


def test_combine_diacritic_circumflex_to_combining() -> None:
    # U+005E -> U+0302.
    assert TextPosition.combine_diacritic("^") == "̂"


def test_combine_diacritic_nfkc_fallback_trims() -> None:
    # A modifier-letter not in the table falls through to NFKC + strip.
    out = TextPosition.combine_diacritic("˘")  # breve
    assert out == unicodedata.normalize("NFKC", "˘").strip()


def test_combine_diacritic_empty_returns_empty() -> None:
    assert TextPosition.combine_diacritic("") == ""


def test_create_diacritics_returns_copy() -> None:
    d = TextPosition.create_diacritics()
    assert d == _DIACRITICS
    d[0x9999] = "x"
    assert 0x9999 not in _DIACRITICS  # mutation isolated


# ---------------------------------------------------------------------------
# insertDiacritic — combining mark goes AFTER the base character
# ---------------------------------------------------------------------------


def test_insert_diacritic_after_base() -> None:
    base = _tp("e")
    base.insert_diacritic(0, _tp("́"))
    assert base.text == "é"


def test_insert_diacritic_remaps_non_combining_form() -> None:
    # Inserting a grave accent (U+0060) maps to U+0300 before attaching.
    base = _tp("a")
    base.insert_diacritic(0, _tp("`"))
    assert base.text == "à"
    assert unicodedata.combining(base.text[1]) != 0


def test_insert_diacritic_at_middle_index() -> None:
    base = _tp("abc")
    base.insert_diacritic(1, _tp("̂"))
    # After char at index 1 ('b').
    assert base.text == "ab̂c"


def test_insert_diacritic_index_clamped_high() -> None:
    base = _tp("ab")
    base.insert_diacritic(99, _tp("̃"))
    assert base.text == "ab̃"


def test_insert_diacritic_index_clamped_low() -> None:
    base = _tp("xy")
    base.insert_diacritic(-5, _tp("̄"))
    assert base.text == "x̄y"


# ---------------------------------------------------------------------------
# mergeDiacritic — x-overlap (contains) drives attachment & width extension
# ---------------------------------------------------------------------------


def test_merge_diacritic_appends_text_and_width() -> None:
    base = _tp("e", x=0.0, width=10.0)
    mark = _tp("́", x=2.0, width=3.0)
    base.merge_diacritic(mark)
    assert base.text == "é"
    assert base.width == 13.0


def test_merge_diacritic_with_normalizer_precomposes() -> None:
    base = _tp("e", x=0.0, width=10.0)
    mark = _tp("́", x=1.0, width=2.0)
    base.merge_diacritic(mark, normalizer=lambda s: unicodedata.normalize("NFC", s))
    assert base.text == "é"  # é precomposed
    assert base.width == 12.0


def test_merge_diacritic_without_normalizer_keeps_decomposed() -> None:
    base = _tp("a")
    mark = _tp("̀")
    base.merge_diacritic(mark)
    assert base.text == "à"
    assert "à" not in base.text  # not precomposed


def test_contains_overlap_selects_base_for_diacritic() -> None:
    # A standalone diacritic that x-overlaps a base is attachable; one that
    # does not overlap is not. Drives the stripper's isDiacritic+contains.
    base = _tp("o", x=0.0, width=10.0)
    overlapping = _tp("̂", x=3.0, width=4.0)
    far = _tp("̂", x=50.0, width=4.0)
    assert base.is_diacritic() is False
    assert overlapping.is_diacritic() is True
    assert base.contains(overlapping) is True
    assert base.contains(far) is False


def test_contains_picks_nearer_of_two_bases() -> None:
    # Two adjacent base glyphs; the diacritic overlaps only the second.
    base1 = _tp("a", x=0.0, width=10.0)
    base2 = _tp("e", x=10.0, width=10.0)
    mark = _tp("́", x=11.0, width=4.0)
    assert base1.contains(mark) is False
    assert base2.contains(mark) is True


def test_full_merge_flow_overlapping_base() -> None:
    # Simulate the PDFTextStripper loop: diacritic that overlaps the
    # previous base merges onto it.
    base = _tp("c", x=0.0, width=10.0)
    cedilla = _tp("̧", x=2.0, width=3.0)
    assert cedilla.is_diacritic()
    if base.contains(cedilla):
        base.merge_diacritic(cedilla, normalizer=lambda s: unicodedata.normalize("NFC", s))
    assert base.text == "ç"  # ç


def test_multiple_diacritics_on_one_base() -> None:
    base = _tp("a", x=0.0, width=10.0)
    for cp, xoff in ((0x0300, 1.0), (0x0323, 2.0)):
        mark = _tp(chr(cp), x=xoff, width=2.0)
        assert mark.is_diacritic()
        assert base.contains(mark)
        base.merge_diacritic(mark)
    # Without a normalizer the marks accumulate in encounter order after the
    # base: a + U+0300 + U+0323.
    assert base.text == "a" + chr(0x0300) + chr(0x0323)


def test_diacritic_with_no_base_stays_standalone() -> None:
    # A diacritic TextPosition that overlaps nothing is simply emitted; the
    # stripper would still call is_diacritic() True but contains() False.
    mark = _tp("́", x=100.0, width=4.0)
    others = [_tp("a", x=0.0, width=10.0), _tp("b", x=10.0, width=10.0)]
    assert mark.is_diacritic()
    assert all(not o.contains(mark) for o in others)


# ---------------------------------------------------------------------------
# normalizeWord — NFKC of presentation forms
# ---------------------------------------------------------------------------


@pytest.fixture
def stripper() -> PDFTextStripper:
    return PDFTextStripper()


def test_normalize_word_decomposes_fi_ligature(stripper: PDFTextStripper) -> None:
    # U+FB01 (fi) is an Alphabetic Presentation Form -> "fi".
    assert stripper.normalize_word("ﬁne") == "fine"


def test_normalize_word_decomposes_ffi_ligature(stripper: PDFTextStripper) -> None:
    assert stripper.normalize_word("oﬃce") == "office"


def test_normalize_word_plain_ascii_unchanged(stripper: PDFTextStripper) -> None:
    assert stripper.normalize_word("Hello") == "Hello"


def test_normalize_word_keeps_precomposed_accent(stripper: PDFTextStripper) -> None:
    # Precomposed é is not a presentation form -> left untouched (NFKC of a
    # plain letter outside the presentation ranges is not applied per-char).
    assert stripper.normalize_word("café") == "café"


def test_normalize_word_empty(stripper: PDFTextStripper) -> None:
    assert stripper.normalize_word("") == ""


def test_normalize_word_allah_ligature_with_alif(stripper: PDFTextStripper) -> None:
    # U+FDF2 preceded by alif (U+0627) -> Allah-without-alif decomposition.
    out = stripper.normalize_word("اﷲ")
    # The FDF2 ligature is replaced by the lam-lam-heh decomposition; the raw
    # ligature codepoint must be gone and the lam (U+0644) must be present.
    assert "ﷲ" not in out
    assert chr(0x0644) in out


def test_normalize_word_multiple_ligatures(stripper: PDFTextStripper) -> None:
    # U+FB01 (fi) + U+FB02 (fl) -> "fifl".
    assert stripper.normalize_word("ﬁﬂ") == "fifl"


def test_normalize_word_idempotent_on_normalized(stripper: PDFTextStripper) -> None:
    once = stripper.normalize_word("ﬁx")
    assert stripper.normalize_word(once) == once
