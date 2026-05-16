"""Coverage backfill for :class:`pypdfbox.pdmodel.encryption.sasl_prep.SaslPrep`.

Targets the parity wrapper classmethods that expose the RFC 3454 codepoint
predicates, plus the bidi / unassigned / prohibited error paths in
``_sasl_prep``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.encryption.sasl_prep import SaslPrep


def test_constructor_raises_type_error() -> None:
    with pytest.raises(TypeError, match="utility class"):
        SaslPrep()


# --- Wrapper classmethod parity --------------------------------------------


def test_tagging_classmethod() -> None:
    assert SaslPrep.tagging(0xE0001) is True
    assert SaslPrep.tagging(0xE0030) is True
    assert SaslPrep.tagging(0xE0080) is False


def test_change_display_properties_classmethod() -> None:
    assert SaslPrep.change_display_properties(0x200E) is True
    assert SaslPrep.change_display_properties(0x202E) is True
    assert SaslPrep.change_display_properties(0x0041) is False


def test_inappropriate_for_canonical_classmethod() -> None:
    assert SaslPrep.inappropriate_for_canonical(0x2FF0) is True
    assert SaslPrep.inappropriate_for_canonical(0x2FFB) is True
    assert SaslPrep.inappropriate_for_canonical(0x2FFC) is False


def test_inappropriate_for_plain_text_classmethod() -> None:
    assert SaslPrep.inappropriate_for_plain_text(0xFFFD) is True
    assert SaslPrep.inappropriate_for_plain_text(0xFFF8) is False


def test_surrogate_code_point_classmethod() -> None:
    assert SaslPrep.surrogate_code_point(0xD800) is True
    assert SaslPrep.surrogate_code_point(0xDFFF) is True
    assert SaslPrep.surrogate_code_point(0xD7FF) is False


def test_non_character_code_point_classmethod() -> None:
    assert SaslPrep.non_character_code_point(0xFDD0) is True
    assert SaslPrep.non_character_code_point(0xFDEF) is True
    assert SaslPrep.non_character_code_point(0xFFFE) is True
    assert SaslPrep.non_character_code_point(0xFFFF) is True
    assert SaslPrep.non_character_code_point(0x10FFFE) is True
    assert SaslPrep.non_character_code_point(0x0041) is False


def test_private_use_classmethod() -> None:
    assert SaslPrep.private_use(0xE000) is True
    assert SaslPrep.private_use(0xF8FF) is True
    assert SaslPrep.private_use(0xF0000) is True
    assert SaslPrep.private_use(0x100000) is True
    assert SaslPrep.private_use(0x0041) is False


def test_non_ascii_control_classmethod() -> None:
    assert SaslPrep.non_ascii_control(0x0080) is True
    assert SaslPrep.non_ascii_control(0x009F) is True
    assert SaslPrep.non_ascii_control(0xFEFF) is True
    assert SaslPrep.non_ascii_control(0x06DD) is True
    assert SaslPrep.non_ascii_control(0x206B) is True
    assert SaslPrep.non_ascii_control(0x1D175) is True
    assert SaslPrep.non_ascii_control(0x0041) is False


def test_ascii_control_classmethod() -> None:
    assert SaslPrep.ascii_control(0x00) is True
    assert SaslPrep.ascii_control(0x1F) is True
    assert SaslPrep.ascii_control(0x7F) is True
    assert SaslPrep.ascii_control(0x20) is False
    assert SaslPrep.ascii_control(0x41) is False


def test_non_ascii_space_classmethod() -> None:
    assert SaslPrep.non_ascii_space(0x00A0) is True
    assert SaslPrep.non_ascii_space(0x1680) is True
    assert SaslPrep.non_ascii_space(0x2000) is True
    assert SaslPrep.non_ascii_space(0x202F) is True
    assert SaslPrep.non_ascii_space(0x3000) is True
    assert SaslPrep.non_ascii_space(0x0041) is False


def test_mapped_to_nothing_classmethod() -> None:
    assert SaslPrep.mapped_to_nothing(0x00AD) is True
    assert SaslPrep.mapped_to_nothing(0xFE00) is True
    assert SaslPrep.mapped_to_nothing(0xFE0F) is True
    assert SaslPrep.mapped_to_nothing(0x0041) is False


# --- ``_sasl_prep`` error / boundary paths ---------------------------------


def test_sasl_prep_query_strips_mapped_to_nothing() -> None:
    # 0x00AD (SOFT HYPHEN) is "mapped to nothing".
    assert SaslPrep.sasl_prep_query("a­b") == "ab"


def test_sasl_prep_query_replaces_non_ascii_space() -> None:
    # 0x00A0 NO-BREAK SPACE → plain ASCII space.
    assert SaslPrep.sasl_prep_query("a b") == "a b"


def test_sasl_prep_rejects_prohibited_character() -> None:
    with pytest.raises(ValueError, match="Prohibited"):
        SaslPrep.sasl_prep_query("\x07")  # BEL — ASCII control


def test_sasl_prep_stored_rejects_unassigned_codepoint() -> None:
    # U+E0001 is technically a "tagging" character but is also prohibited;
    # use a known-unassigned codepoint that isn't otherwise prohibited.
    # U+0378 is unassigned and category Cn (Unicode 6+).
    with pytest.raises(ValueError):
        SaslPrep.sasl_prep_stored("a͸b")


def test_sasl_prep_query_allows_unassigned_codepoint() -> None:
    # Query mode permits unassigned (Cn) codepoints.
    out = SaslPrep.sasl_prep_query("a͸b")
    assert "͸" in out


def test_sasl_prep_bidi_initial_randalcat_with_non_matching_last() -> None:
    # Hebrew aleph (R) followed by Latin 'A' (L) ⇒ violates bidi.
    with pytest.raises(ValueError):
        SaslPrep.sasl_prep_query("אA")


def test_sasl_prep_bidi_mixed_l_and_randalcat() -> None:
    # Mix LCat and RandALCat without initial RandALCat ⇒ rejected.
    with pytest.raises(ValueError, match="RandALCat"):
        SaslPrep.sasl_prep_query("AאA")


def test_sasl_prep_pure_ascii_round_trips() -> None:
    assert SaslPrep.sasl_prep_query("Hello") == "Hello"
    assert SaslPrep.sasl_prep_stored("Hello") == "Hello"


def test_sasl_prep_query_allows_randalcat_initial_and_final() -> None:
    # Hebrew aleph at both ends ⇒ valid bidi.
    out = SaslPrep.sasl_prep_query("אא")
    assert out == "אא"


def test_prohibited_classmethod_dispatches_to_all_predicates() -> None:
    assert SaslPrep.prohibited(0x07) is True          # ascii control
    assert SaslPrep.prohibited(0x00A0) is True        # non-ascii space
    assert SaslPrep.prohibited(0xE000) is True        # private use
    assert SaslPrep.prohibited(0xFFFE) is True        # non-character
    assert SaslPrep.prohibited(0xD800) is True        # surrogate
    assert SaslPrep.prohibited(0x2FF0) is True        # inappropriate-for-canonical
    assert SaslPrep.prohibited(0xFFFD) is True        # inappropriate-for-plain-text
    assert SaslPrep.prohibited(0x200E) is True        # change display props
    assert SaslPrep.prohibited(0xE0001) is True       # tagging
    assert SaslPrep.prohibited(0x0041) is False       # plain 'A'
