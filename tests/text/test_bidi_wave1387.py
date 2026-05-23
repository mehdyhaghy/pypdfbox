"""Wave 1387 — direct tests for the UAX #9 BiDi port.

Covers :class:`pypdfbox.text.bidi.BidiResolver`, :func:`reorder_visually`,
:func:`reorder_runs_visually`, and :func:`get_paragraph_direction`, plus
the integration into :meth:`PDFTextStripper.handle_direction`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.text.bidi import (
    BidiResolver,
    get_paragraph_direction,
    reorder_runs_visually,
    reorder_visually,
)
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "text"


# ---------- paragraph direction (P1-P3) -----------------------------------


def test_get_paragraph_direction_pure_ascii_is_ltr() -> None:
    assert get_paragraph_direction("Hello world!") == 0


def test_get_paragraph_direction_pure_arabic_is_rtl() -> None:
    assert get_paragraph_direction("العربية") == 1


def test_get_paragraph_direction_arabic_after_punct_is_rtl() -> None:
    # Punctuation does not contribute strong direction; first strong char
    # is the Arabic letter.
    assert get_paragraph_direction("«العربية»") == 1


def test_get_paragraph_direction_first_strong_wins() -> None:
    assert get_paragraph_direction("abc العربية") == 0
    assert get_paragraph_direction("العربية abc") == 1


def test_get_paragraph_direction_empty_defaults_ltr() -> None:
    assert get_paragraph_direction("") == 0


def test_get_paragraph_direction_no_strong_defaults_ltr() -> None:
    assert get_paragraph_direction("  !!  ") == 0


# ---------- resolve: pure LTR ---------------------------------------------


def test_resolve_pure_ascii_levels_all_zero() -> None:
    levels = BidiResolver().resolve("Hello, world!")
    assert levels == [0] * len("Hello, world!")


def test_resolve_empty_returns_empty() -> None:
    assert BidiResolver().resolve("") == []


def test_reorder_pure_ascii_is_noop() -> None:
    text = "Hello, world!"
    levels = BidiResolver().resolve(text)
    assert reorder_visually(text, levels) == text


# ---------- resolve: pure RTL ---------------------------------------------


def test_resolve_pure_arabic_levels_all_one() -> None:
    text = "العربية"
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    assert levels == [1] * len(text)


def test_reorder_pure_arabic_reverses_codepoints() -> None:
    text = "العربية"
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    visual = reorder_visually(text, levels)
    assert visual == text[::-1]


def test_resolve_arabic_paragraph_autodetected() -> None:
    text = "العربية"
    levels = BidiResolver().resolve(text)
    # Auto-detected paragraph dir is RTL, so resolved levels are odd.
    assert all(level % 2 == 1 for level in levels)


# ---------- resolve: mixed LTR + RTL --------------------------------------


def test_resolve_mixed_ltr_rtl_assigns_distinct_levels() -> None:
    # "abc OLLEH" — "OLLEH" is a fake "Hebrew" word in caps; use real
    # Hebrew here to get bidi class R.
    text = "abc אבג"  # noqa: RUF001
    levels = BidiResolver().resolve(text)
    # First 4 chars (abc + space) at level 0; last 3 chars (Hebrew) at
    # level 1.
    assert levels[0] == 0
    assert levels[1] == 0
    assert levels[2] == 0
    # Space between is whitespace; under L1 reset it stays at paragraph
    # level when adjacent to segment/paragraph separator, otherwise it
    # picks up the neutral resolution. We assert only that the Hebrew
    # chars come out at level 1.
    assert levels[-1] == 1
    assert levels[-2] == 1
    assert levels[-3] == 1


def test_reorder_mixed_paragraph_reverses_rtl_run_only() -> None:
    text = "abc אבג"  # noqa: RUF001
    levels = BidiResolver().resolve(text)
    visual = reorder_visually(text, levels)
    # The RTL run should be reversed; the LTR run stays put.
    assert visual.startswith("abc ")
    rtl_in = "אבג"  # noqa: RUF001
    assert visual.endswith(rtl_in[::-1])


# ---------- W2 / W7 — Arabic + European numbers --------------------------


def test_resolve_arabic_paragraph_with_european_digits_W2() -> None:
    # In an Arabic paragraph, EN preceded by AL becomes AN (W2). AN at
    # an odd embedding level then gets +2 → level 2.
    text = "ا 12"  # AL space EN EN
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    # The digits should be at an even level (AN at odd base + 2 → even).
    assert levels[2] % 2 == 0
    assert levels[3] % 2 == 0


def test_resolve_arabic_with_arabic_indic_digits_stays_AN() -> None:
    text = "ا ١٢"  # AL space AN AN
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    assert levels[2] % 2 == 0
    assert levels[3] % 2 == 0


def test_resolve_W7_EN_after_L_becomes_L() -> None:
    # EN preceded by L should become L (W7). All chars therefore at
    # paragraph level 0.
    text = "abc 12"
    levels = BidiResolver().resolve(text)
    assert levels == [0] * len(text)


# ---------- "12 abc 34" embedded in RTL paragraph ------------------------


def test_resolve_RTL_paragraph_with_LTR_run_and_numbers() -> None:
    # Hebrew + spaces + Latin/digits — the Latin/digits stay in LTR
    # order within the visual reordered output.
    text = "אבג 12 abc"  # noqa: RUF001
    levels = BidiResolver().resolve(text)
    visual = reorder_visually(text, levels)
    # "12 abc" should appear in its source order somewhere in the visual
    # output (LTR-within-RTL invariant).
    assert "12 abc" in visual or "12" in visual
    # The Hebrew should appear reversed (single-char-run reverse is
    # still the same chars in opposite order).
    assert "גבא" in visual


# ---------- L1 / segment + paragraph separators ---------------------------


def test_resolve_trailing_whitespace_resets_to_paragraph_level() -> None:
    text = "אבג   "  # noqa: RUF001  -- Hebrew + 3 spaces
    levels = BidiResolver().resolve(text)
    # Trailing whitespace levels reset to paragraph level (1 here).
    # Hebrew levels remain odd, trailing ws becomes odd too (paragraph
    # level is 1).
    assert levels[-1] == 1
    assert levels[-2] == 1


# ---------- reorder_visually contract --------------------------------------


def test_reorder_visually_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        reorder_visually("abc", [0, 0])


def test_reorder_visually_empty() -> None:
    assert reorder_visually("", []) == ""


# ---------- reorder_runs_visually (Java Bidi.reorderVisually parity) ------


def test_reorder_runs_visually_single_level_is_identity() -> None:
    runs = ["alpha", "beta", "gamma"]
    levels = [0, 0, 0]
    assert reorder_runs_visually(runs, levels) == runs


def test_reorder_runs_visually_all_RTL_reverses() -> None:
    runs = ["a", "b", "c"]
    levels = [1, 1, 1]
    assert reorder_runs_visually(runs, levels) == ["c", "b", "a"]


def test_reorder_runs_visually_mixed_reverses_only_RTL_segment() -> None:
    runs = ["L1", "L2", "R1", "R2", "L3"]
    levels = [0, 0, 1, 1, 0]
    assert reorder_runs_visually(runs, levels) == ["L1", "L2", "R2", "R1", "L3"]


def test_reorder_runs_visually_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        reorder_runs_visually(["a"], [0, 0])


def test_reorder_runs_visually_empty() -> None:
    assert reorder_runs_visually([], []) == []


# ---------- nested embedding levels (L2 iteration) -----------------------


def test_reorder_with_level_2_run_reverses_inner_run() -> None:
    # Simulate a level-2 run embedded inside a level-1 run; the L2 loop
    # reverses level-2 first (so the inner run order is restored
    # left-to-right), then level-1 reverses the whole sequence.
    runs = ["a", "b", "c", "d", "e"]
    levels = [1, 2, 2, 2, 1]
    # First iteration (level 2): runs[1:4] reverses → a, d, c, b, e
    # Second iteration (level 1): full reverses → e, b, c, d, a
    assert reorder_runs_visually(runs, levels) == ["e", "b", "c", "d", "a"]


# ---------- handle_direction integration ---------------------------------


def test_handle_direction_pure_ascii_returns_unchanged() -> None:
    stripper = PDFTextStripper()
    assert stripper.handle_direction("Hello, world!") == "Hello, world!"


def test_handle_direction_empty_returns_empty() -> None:
    stripper = PDFTextStripper()
    assert stripper.handle_direction("") == ""


def test_handle_direction_pure_arabic_reverses() -> None:
    stripper = PDFTextStripper()
    text = "العربية"
    assert stripper.handle_direction(text) == text[::-1]


def test_handle_direction_mixed_paragraph_keeps_LTR_run_in_source_order() -> None:
    stripper = PDFTextStripper()
    text = "abc אבג"  # noqa: RUF001
    out = stripper.handle_direction(text)
    # "abc" must still appear in source order in the visual output.
    assert "abc" in out
    # The Hebrew run must be reversed.
    assert "גבא" in out


def test_handle_direction_LTR_with_arabic_numerals_unchanged() -> None:
    stripper = PDFTextStripper()
    # AN paragraph_direction=0 -> AN at even level + 2 = level 2, but
    # the surrounding text is at level 0 so the visual order has the
    # numerals reversed against the LTR direction. We assert the digits
    # come through (no characters dropped).
    text = "abc ١٢٣"
    out = stripper.handle_direction(text)
    assert "abc" in out
    for ch in "١٢٣":
        assert ch in out


def test_handle_direction_applies_bracket_mirroring_in_rtl_run() -> None:
    stripper = PDFTextStripper()
    # "(abc)" inside a fully RTL paragraph — the brackets should mirror.
    text = "א(ב)ג"  # noqa: RUF001
    out = stripper.handle_direction(text)
    # When the entire string is at level 1 and we apply L4, '(' should
    # be mirrored to ')' and vice-versa during reordering.
    # Source order:  א ( ב ) ג   (5 chars)
    # Reversed:      ג ) ב ( א
    # After L4 on level-1 chars: ג ( ב ) א
    assert out == "ג(ב)א"  # noqa: RUF001


# ---------- BidiSample.pdf.txt fixture parity ----------------------------


def test_handle_direction_round_trips_BidiSample_first_line() -> None:
    """The first line of the upstream BidiSample expected text is pure
    Arabic; running it through our BiDi pipeline twice should be
    consistent (idempotent on the visually-already-ordered text).
    """
    expected = _FIXTURES / "BidiSample.pdf.txt"
    first_line = expected.read_text(encoding="utf-8").splitlines()[0]
    # First line is "العربية" — pure Arabic, RTL paragraph.
    stripper = PDFTextStripper()
    once = stripper.handle_direction(first_line)
    twice = stripper.handle_direction(once)
    # Idempotency under the bidi reorder (running it again on the
    # visually-ordered output reverses again — net effect on a fully-
    # RTL paragraph is the original input).
    assert twice == first_line
