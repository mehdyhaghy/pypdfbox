"""Wave 1391 — coverage round-out for :mod:`pypdfbox.text.bidi`."""

from __future__ import annotations

from pypdfbox.text.bidi import (
    BidiResolver,
    get_paragraph_direction,
    reorder_visually,
)

LRE = "‪"
RLE = "‫"
PDF = "‬"
LRO = "‭"
RLO = "‮"
LRI = "⁦"
RLI = "⁧"
FSI = "⁨"
PDI = "⁩"
NSM = "́"
HEB = "א"
ARA = "ا"
AN_DIGIT = "٠"


def test_paragraph_direction_skips_chars_inside_lri_isolate() -> None:
    assert get_paragraph_direction(LRI + "ABC" + PDI + HEB) == 1


def test_paragraph_direction_skips_chars_inside_rli_isolate() -> None:
    assert get_paragraph_direction(RLI + HEB + PDI + "abc") == 0


def test_paragraph_direction_skips_chars_inside_fsi_isolate() -> None:
    assert get_paragraph_direction(FSI + HEB + PDI + "abc") == 0


def test_paragraph_direction_pdi_without_matching_isolate_is_ignored() -> None:
    assert get_paragraph_direction(PDI + "abc") == 0


def test_paragraph_direction_pdi_pops_then_uses_outer_strong() -> None:
    assert get_paragraph_direction(LRI + "A" + PDI + HEB) == 1


def test_resolve_lre_pushes_even_level_around_ltr_chars() -> None:
    text = LRE + "abc" + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[1] == 2
    assert levels[2] == 2
    assert levels[3] == 2


def test_resolve_rle_pushes_odd_level_around_rtl_chars() -> None:
    text = RLE + HEB + HEB + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[1] == 1
    assert levels[2] == 1


def test_resolve_lro_overrides_to_l() -> None:
    text = LRO + HEB + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[1] == 2


def test_resolve_rlo_overrides_to_r() -> None:
    text = RLO + "a" + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[1] == 1


def test_resolve_lri_pushes_isolate_frame() -> None:
    text = LRI + HEB + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[0] == 0
    assert levels[1] == 3


def test_resolve_rli_pushes_isolate_frame_with_odd_level() -> None:
    text = RLI + "a" + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[0] == 0
    assert levels[1] == 2


def test_resolve_fsi_picks_rtl_when_first_strong_is_arabic() -> None:
    text = FSI + ARA + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[0] == 0
    assert levels[1] == 1


def test_resolve_fsi_picks_ltr_when_first_strong_is_latin() -> None:
    text = FSI + "a" + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[1] == 2


def test_resolve_fsi_with_no_strong_inside_defaults_to_ltr() -> None:
    text = FSI + " " + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[0] == 0


def test_resolve_pdf_pops_embedding_stack() -> None:
    text = LRE + "a" + PDF + "b"
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[3] == 0


def test_resolve_unmatched_pdf_is_harmless() -> None:
    text = "a" + PDF + "b"
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels == [0, 0, 0]


def test_resolve_unmatched_pdi_is_harmless() -> None:
    text = "a" + PDI + "b"
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels == [0, 0, 0]


def test_resolve_paragraph_separator_resets_to_paragraph_level() -> None:
    text = "a\nb"
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    assert levels[1] == 1


def test_resolve_nested_overrides_take_inner_override() -> None:
    text = LRO + "a" + RLO + "b" + PDF + "c" + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[3] == 3
    assert levels[1] == 2
    assert levels[5] == 2


def test_fsi_substring_scan_handles_nested_isolates() -> None:
    text = FSI + LRI + "abc" + PDI + HEB + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels[0] == 0


def test_w1_nsm_after_lri_becomes_on() -> None:
    text = LRI + NSM + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 3


def test_w1_nsm_at_start_takes_sos_direction() -> None:
    levels = BidiResolver().resolve(NSM + "abc", paragraph_direction=0)
    assert levels == [0, 0, 0, 0]


def test_w4_es_between_en_becomes_en() -> None:
    levels = BidiResolver().resolve(HEB + "1+2", paragraph_direction=1)
    assert levels == [1, 2, 2, 2]


def test_w4_cs_between_en_becomes_en() -> None:
    levels = BidiResolver().resolve(HEB + "1,2", paragraph_direction=1)
    assert levels == [1, 2, 2, 2]


def test_w4_cs_between_an_becomes_an() -> None:
    text = HEB + AN_DIGIT + "," + AN_DIGIT
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    assert levels == [1, 2, 2, 2]


def test_w5_et_before_en_becomes_en() -> None:
    levels = BidiResolver().resolve(HEB + "$$1", paragraph_direction=1)
    assert levels == [1, 2, 2, 2]


def test_w5_et_after_en_becomes_en() -> None:
    levels = BidiResolver().resolve(HEB + "1$$", paragraph_direction=1)
    assert levels == [1, 2, 2, 2]


def test_w5_et_run_without_adjacent_en_stays_neutral() -> None:
    levels = BidiResolver().resolve("a$b", paragraph_direction=0)
    assert levels == [0, 0, 0]


def test_w5_et_only_run_with_no_adjacent_en_stays_neutral() -> None:
    levels = BidiResolver().resolve("$$$", paragraph_direction=0)
    assert levels == [0, 0, 0]


def test_l1_tab_segment_separator_resets_to_paragraph_level() -> None:
    text = HEB + "\t " + HEB
    levels = BidiResolver().resolve(text)
    assert levels[1] == 1
    assert levels[2] == 1


def test_l1_trailing_whitespace_resets_to_paragraph_level() -> None:
    text = HEB + "  "
    levels = BidiResolver().resolve(text)
    assert levels[1] == 1
    assert levels[2] == 1


def test_l1_trailing_isolate_format_chars_also_reset() -> None:
    text = HEB + LRI + PDI
    levels = BidiResolver().resolve(text)
    assert levels[-1] == 1


def test_reorder_visually_with_all_level_zero_is_identity() -> None:
    assert reorder_visually("abc", [0, 0, 0]) == "abc"


def test_reorder_visually_with_level_2_inner_run_reverses_inner_and_outer() -> None:
    assert reorder_visually("abcd", [1, 2, 2, 1]) == "dbca"


def test_reorder_visually_mixed_levels_iterates_high_to_low() -> None:
    assert reorder_visually("abcde", [0, 1, 2, 1, 0]) == "adcbe"


def test_resolve_empty_skipping() -> None:
    assert BidiResolver().resolve("") == []


def test_w1_nsm_after_strong_takes_previous_type() -> None:
    # NSM (combining acute) after a letter — should take the letter's type.
    text = HEB + NSM + HEB
    levels = BidiResolver().resolve(text)
    assert levels == [1, 1, 1]


def test_w1_nsm_after_ascii_takes_l_in_ltr_paragraph() -> None:
    text = "a" + NSM + "b"
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels == [0, 0, 0]


def test_w1_nsm_after_pdi_becomes_on() -> None:
    # NSM following PDI in the same level run — W1 turns NSM into ON
    # because prev is an isolate-format char.
    text = LRI + "a" + PDI + NSM
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 4


def test_resolve_lri_inside_override_takes_override_type() -> None:
    # When an LRI initiator appears inside an LRO/RLO scope, line 187-188
    # sets the LRI's resolved type to the override before computing its
    # new isolate level.
    text = LRO + LRI + "a" + PDI + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 5


def test_resolve_lre_overflow_increments_overflow_embedding() -> None:
    # Pushing more LREs than MAX_DEPTH=125 allows triggers overflow.
    # Each LRE adds 2 to the level, so 63 LREs reach level 126 > MAX_DEPTH.
    text = LRE * 64 + PDF * 64
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 128


def test_resolve_rli_overflow_increments_overflow_isolate() -> None:
    # Stack overflows on the 64th RLI (level 127 > MAX_DEPTH 125).
    text = RLI * 64 + PDI * 64
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 128


def test_resolve_pdf_with_overflow_embedding_decrements_overflow() -> None:
    # After an overflow LRE, a PDF decrements overflow_embedding.
    text = LRE * 64 + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 65


def test_resolve_pdi_with_overflow_isolate_decrements_overflow() -> None:
    # After an overflow RLI, a PDI decrements overflow_isolate.
    text = RLI * 64 + PDI
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 65


def test_resolve_bn_takes_top_level() -> None:
    # BN (boundary-neutral) class — Unicode chars like U+00AD soft hyphen.
    text = "a­b"
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert levels == [0, 0, 0]


def test_resolve_pdi_pops_through_intermediate_embedding_levels() -> None:
    # An LRE inside an LRI scope. The PDI pops back through the LRE frame.
    text = LRI + LRE + "a" + PDI + "b"
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    # After PDI we're back to outer level 0; "b" is at outer level.
    assert levels[-1] == 0


def test_resolve_pdf_inside_isolate_overflow_is_passthrough() -> None:
    # PDF inside an overflow-isolate scope is silently passed (line 222).
    text = RLI * 64 + PDF + PDF
    levels = BidiResolver().resolve(text, paragraph_direction=0)
    assert len(levels) == 66


def test_l1_walks_back_over_ws_preceding_segment_separator() -> None:
    # A space before a tab (segment separator) — L1 resets the space
    # to paragraph level along with the tab.
    text = "a \tb"
    levels = BidiResolver().resolve(text, paragraph_direction=1)
    # Indices 1 (space) and 2 (tab) both at paragraph level 1.
    assert levels[1] == 1
    assert levels[2] == 1
