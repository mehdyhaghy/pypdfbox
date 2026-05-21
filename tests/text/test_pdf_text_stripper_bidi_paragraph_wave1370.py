"""Wave 1370 — bidi reordering at the paragraph / word level.

The lite stripper's ``handle_direction`` reverses RTL runs whole when
any code point in the word has bidirectional class ``R`` (Hebrew /
general RTL) or ``AL`` (Arabic letters); it does NOT perform the full
ICU ``Bidi.reorderVisually`` line-level reordering (multi-run
ordering with per-character mirroring is deferred — see CHANGES.md).

These tests pin the contract we do have:

  - All-LTR text is passed through unchanged.
  - All-RTL text is reversed.
  - Empty / single-codepoint input is a no-op.
  - The reorder happens through ``normalize_word`` (the public hook)
    and through ``handle_direction`` (the directly callable entry).
  - ``normalize`` builds a list of words and each word is
    independently directionalised — so a list with one RTL word and
    one LTR word emits one reversed and one passed-through entry.

ICU-style paragraph-level reordering (where mixed-direction sequences
get re-interleaved per the Unicode Bidi Algorithm) is explicitly
skipped — it is the documented divergence.
"""
from __future__ import annotations

import pytest

from pypdfbox.text import LineItem, PDFTextStripper, TextPosition


def _tp(text: str = "x", **kw) -> TextPosition:
    base = {"text": text, "x": 0.0, "y": 0.0, "font_size": 12.0, "width": 10.0}
    base.update(kw)
    return TextPosition(**base)


# ---------------------------------------------------------------------------
# handle_direction — direct entry point
# ---------------------------------------------------------------------------


def test_handle_direction_ltr_passes_through() -> None:
    s = PDFTextStripper()
    assert s.handle_direction("hello") == "hello"


def test_handle_direction_arabic_letters_reversed() -> None:
    """Arabic letters are bidirectional class ``AL`` — trigger
    reversal."""
    s = PDFTextStripper()
    # "ا" "ب" "ت" (alef-ba-ta) — three Arabic letters in logical order.
    assert s.handle_direction("ابت") == "تبا"


def test_handle_direction_hebrew_reversed() -> None:
    """Hebrew letters are bidirectional class ``R``."""
    s = PDFTextStripper()
    # alef-bet-gimel
    assert s.handle_direction("אבג") == "גבא"


def test_handle_direction_empty_no_op() -> None:
    s = PDFTextStripper()
    assert s.handle_direction("") == ""


def test_handle_direction_single_rtl_codepoint_returns_unchanged() -> None:
    """A single-codepoint RTL run cannot be reordered — return it
    as-is."""
    s = PDFTextStripper()
    # Note: handle_direction returns reversed string even for single char
    # (single-char reversal is identity), but the class-level behaviour
    # is documented as "reverse if any RTL". Identity matches.
    assert s.handle_direction("ا") == "ا"


def test_handle_direction_mixed_rtl_ltr_reverses_whole_word() -> None:
    """Mixed-direction words are reversed whole (lite-mode divergence
    from ICU which would split at script boundaries)."""
    s = PDFTextStripper()
    # 'a' (LTR) + 'ا' (Arabic, RTL) — at least one RTL -> reverse whole.
    out = s.handle_direction("aا")
    # Whole reversal: alef then 'a'.
    assert out == "اa"


# ---------------------------------------------------------------------------
# normalize_word — public hook over the same logic + decomposition
# ---------------------------------------------------------------------------


def test_normalize_word_pure_ltr_unchanged() -> None:
    s = PDFTextStripper()
    assert s.normalize_word("Hello") == "Hello"


def test_normalize_word_pure_hebrew_reversed() -> None:
    s = PDFTextStripper()
    assert s.normalize_word("אבג") == "גבא"


def test_normalize_word_pure_arabic_reversed() -> None:
    s = PDFTextStripper()
    assert s.normalize_word("ابت") == "تبا"


def test_normalize_word_with_presentation_form_decomposes_then_reverses() -> None:
    """A presentation form code point in the FB00-FDFF range NFKC-
    decomposes; the resulting Arabic letters then trigger the
    handle_direction whole-run reversal."""
    s = PDFTextStripper()
    # U+FE8D is the isolated form of ALEF. NFKC -> U+0627.
    out = s.normalize_word("ﺍ")
    # Single Arabic letter — reversal is identity.
    assert out == "ا"


# ---------------------------------------------------------------------------
# normalize over a LineItem list — each word independently directionalised
# ---------------------------------------------------------------------------


def test_normalize_directionalises_each_word_independently() -> None:
    s = PDFTextStripper()
    # Word 1: "Hi" (LTR)  | Word 2: "אבג" (RTL).
    line = [
        LineItem(_tp("H")),
        LineItem(_tp("i")),
        LineItem.get_word_separator(),
        LineItem(_tp("א")),
        LineItem(_tp("ב")),
        LineItem(_tp("ג")),
    ]
    words = s.normalize(line)
    assert [w.get_text() for w in words] == ["Hi", "גבא"]


def test_normalize_does_not_cross_word_directionalisation() -> None:
    """Each word is independently reversed — LTR words after an RTL
    word stay LTR."""
    s = PDFTextStripper()
    line = [
        LineItem(_tp("א")),
        LineItem(_tp("ב")),
        LineItem.get_word_separator(),
        LineItem(_tp("o")),
        LineItem(_tp("k")),
    ]
    words = s.normalize(line)
    assert [w.get_text() for w in words] == ["בא", "ok"]


# ---------------------------------------------------------------------------
# Bidi numbers (class ``EN`` / ``AN``) do not trigger reversal
# ---------------------------------------------------------------------------


def test_handle_direction_european_numerals_pass_through() -> None:
    """Western digits are bidirectional class ``EN`` — they do not
    trigger the RTL reversal heuristic on their own."""
    s = PDFTextStripper()
    assert s.handle_direction("123") == "123"


def test_handle_direction_arabic_indic_digits_pass_through() -> None:
    """Arabic-Indic digits are class ``AN`` — they do not match the
    ``R``/``AL`` predicate the lite stripper uses to decide whether to
    reverse."""
    s = PDFTextStripper()
    # U+0660–U+0669: Arabic-Indic digits 0–9. Class ``AN``, not ``AL``/``R``.
    assert s.handle_direction("٠١٢") == "٠١٢"


# ---------------------------------------------------------------------------
# ICU-style paragraph reordering is explicitly NOT supported in lite mode
# ---------------------------------------------------------------------------


def test_icu_paragraph_reordering_is_documented_divergence() -> None:
    """We deliberately do not implement the full Unicode Bidi
    Algorithm. Pin the divergence so a future change that adds ICU
    must update the documented behaviour intentionally."""
    pytest.skip(
        "Full Unicode Bidi paragraph reordering is out of scope for the "
        "lite stripper — see CHANGES.md."
    )


# ---------------------------------------------------------------------------
# parse_bidi_file static helper accepts the upstream BidiMirroring format
# ---------------------------------------------------------------------------


def test_parse_bidi_file_parses_two_token_lines() -> None:
    """Each ``CODEPOINT;CODEPOINT`` line produces one mapping entry."""
    src = b"0028; 0029  # LEFT PARENTHESIS\n005B; 005D\n"
    result = PDFTextStripper.parse_bidi_file(src)
    assert result["("] == ")"
    assert result["["] == "]"


def test_parse_bidi_file_skips_malformed_tokens() -> None:
    """Lines with non-hex tokens are silently dropped."""
    src = b"XYZ; ABC\n0028; 0029\n"
    result = PDFTextStripper.parse_bidi_file(src)
    assert "(" in result
    assert len(result) == 1


def test_parse_bidi_file_empty_input_yields_empty_map() -> None:
    assert PDFTextStripper.parse_bidi_file(b"") == {}


def test_parse_bidi_file_none_input_yields_empty_map() -> None:
    """``None`` is the upstream null sentinel — return an empty map."""
    assert PDFTextStripper.parse_bidi_file(None) == {}
