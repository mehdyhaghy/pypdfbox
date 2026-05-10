"""Wave 233 — round-out :class:`PDOptionalContentMembershipDictionary`
with the membership counterparts that complete the OCG-management surface:

- ``remove_ocg`` — symmetric counterpart to :meth:`add_ocg`, identity-based,
  handles all three /OCGs storage shapes (missing / single-dict / array)
  and prunes the key when the array becomes empty.
- ``clear_ocgs`` — wipe /OCGs entirely.
- ``get_ocg_count`` + ``__len__`` + ``has_ocgs`` — size and presence
  predicates over /OCGs without forcing the wrap into
  ``PDOptionalContentGroup``.
- ``is_visibility_policy`` predicate — spec-default-aware comparison
  against /P, accepting either a string or the typed enum.

These additions are pypdfbox enrichment — Apache PDFBox 3.0 leaves
callers to manipulate the underlying ``COSArray`` themselves.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    MembershipDictionaryVisibilityPolicy,
    PDOptionalContentMembershipDictionary,
)

_OCGS = COSName.get_pdf_name("OCGs")


# ---------- remove_ocg ----------------------------------------------------


def test_remove_ocg_returns_false_when_ocgs_missing() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    assert ocmd.remove_ocg(a) is False
    # No /OCGs key materialized as a side effect.
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None


def test_remove_ocg_strips_single_dict_form() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs(a)  # writes /OCGs as a single dict
    assert ocmd.remove_ocg(a) is True
    # /OCGs key removed entirely (no empty husk left behind).
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None
    assert ocmd.contains_ocg(a) is False


def test_remove_ocg_single_dict_no_match_returns_false() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    other = PDOptionalContentGroup("Other")
    ocmd.set_ocgs(a)
    assert ocmd.remove_ocg(other) is False
    # /OCGs is preserved as the single dict.
    raw = ocmd.get_cos_object().get_dictionary_object(_OCGS)
    assert raw is a.get_cos_object()


def test_remove_ocg_from_array_preserves_others() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    c = PDOptionalContentGroup("C")
    ocmd.set_ocgs([a, b, c])
    assert ocmd.remove_ocg(b) is True
    names = [g.get_name() for g in ocmd.get_ocgs()]
    assert names == ["A", "C"]


def test_remove_ocg_drops_key_when_array_becomes_empty() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs([a])
    assert ocmd.remove_ocg(a) is True
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None
    assert ocmd.get_ocg_count() == 0


def test_remove_ocg_returns_false_when_not_present() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    other = PDOptionalContentGroup("Other")
    ocmd.set_ocgs([a])
    assert ocmd.remove_ocg(other) is False
    assert ocmd.get_ocg_count() == 1


def test_remove_ocg_idempotent_after_first_removal() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs([a, b])
    assert ocmd.remove_ocg(a) is True
    # Second call: already gone -> False, no mutation of the remaining entry.
    assert ocmd.remove_ocg(a) is False
    assert [g.get_name() for g in ocmd.get_ocgs()] == ["B"]


def test_remove_ocg_identity_match_not_name_match() -> None:
    """Two OCGs sharing a /Name must not be conflated — removal is by
    identity of the wrapped ``COSDictionary``."""
    ocmd = PDOptionalContentMembershipDictionary()
    a1 = PDOptionalContentGroup("Same")
    a2 = PDOptionalContentGroup("Same")
    ocmd.set_ocgs([a1])
    assert ocmd.remove_ocg(a2) is False
    assert ocmd.contains_ocg(a1) is True


def test_remove_ocg_accepts_raw_cos_dictionary() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs([a])
    assert ocmd.remove_ocg(a.get_cos_object()) is True
    assert ocmd.contains_ocg(a) is False


def test_remove_ocg_rejects_invalid_type() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(TypeError):
        ocmd.remove_ocg(42)  # type: ignore[arg-type]


def test_remove_ocg_handles_duplicate_entries_in_array() -> None:
    """If a malformed file has the same OCG dict twice in /OCGs,
    ``remove_ocg`` strips every occurrence."""
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    # Bypass set_ocgs duplicate guards by writing the array directly.
    arr = COSArray()
    arr.add(a.get_cos_object())
    arr.add(a.get_cos_object())
    arr.add(a.get_cos_object())
    ocmd.get_cos_object().set_item(_OCGS, arr)
    assert ocmd.get_ocg_count() == 3
    assert ocmd.remove_ocg(a) is True
    # All three identity matches stripped → /OCGs key removed.
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None


# ---------- clear_ocgs ----------------------------------------------------


def test_clear_ocgs_removes_array() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs([a, b])
    ocmd.clear_ocgs()
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None
    assert ocmd.get_ocgs() == []


def test_clear_ocgs_removes_single_dict_form() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs(a)
    ocmd.clear_ocgs()
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None


def test_clear_ocgs_when_already_absent_is_noop() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    # Should not raise.
    ocmd.clear_ocgs()
    assert ocmd.get_cos_object().get_dictionary_object(_OCGS) is None


def test_clear_ocgs_preserves_visibility_policy_and_type() -> None:
    """Clearing /OCGs must not perturb /P or /Type."""
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AllOn")
    ocmd.set_ocgs([PDOptionalContentGroup("A")])
    ocmd.clear_ocgs()
    assert ocmd.get_visibility_policy() == "AllOn"
    assert ocmd.get_type() == COSName.get_pdf_name("OCMD")


# ---------- get_ocg_count / __len__ / has_ocgs ----------------------------


def test_get_ocg_count_zero_when_missing() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.get_ocg_count() == 0
    assert len(ocmd) == 0
    assert ocmd.has_ocgs() is False


def test_get_ocg_count_one_when_single_dict() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_ocgs(PDOptionalContentGroup("A"))
    assert ocmd.get_ocg_count() == 1
    assert len(ocmd) == 1
    assert ocmd.has_ocgs() is True


def test_get_ocg_count_matches_array_size() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    c = PDOptionalContentGroup("C")
    ocmd.set_ocgs([a, b, c])
    assert ocmd.get_ocg_count() == 3
    assert len(ocmd) == 3
    assert ocmd.has_ocgs() is True


def test_get_ocg_count_empty_array_is_zero() -> None:
    """An explicit empty /OCGs array contributes zero — ``has_ocgs``
    reports ``False`` so callers don't fall into the "non-None but empty"
    trap."""
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.get_cos_object().set_item(_OCGS, COSArray())
    assert ocmd.get_ocg_count() == 0
    assert len(ocmd) == 0
    assert ocmd.has_ocgs() is False


def test_get_ocg_count_with_unexpected_value_type() -> None:
    """A malformed /OCGs (neither a COSArray nor a COSDictionary) is
    treated as zero entries."""
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.get_cos_object().set_item(_OCGS, COSName.get_pdf_name("Bogus"))
    assert ocmd.get_ocg_count() == 0
    assert ocmd.has_ocgs() is False


def test_len_round_trips_with_add_ocg_promotion() -> None:
    """``len`` should track the array-promotion path (single-dict then
    add_ocg → 2-element array)."""
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs(a)
    assert len(ocmd) == 1
    ocmd.add_ocg(b)
    assert len(ocmd) == 2


# ---------- is_visibility_policy ------------------------------------------


def test_is_visibility_policy_default_any_on() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    # Default per PDF 32000-1 §8.11.2.2 is AnyOn.
    assert ocmd.is_visibility_policy("AnyOn") is True
    assert ocmd.is_visibility_policy("AllOn") is False


def test_is_visibility_policy_after_set() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AllOff")
    assert ocmd.is_visibility_policy("AllOff") is True
    assert ocmd.is_visibility_policy("AnyOn") is False


def test_is_visibility_policy_accepts_enum() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AnyOff")
    assert (
        ocmd.is_visibility_policy(
            MembershipDictionaryVisibilityPolicy.ANY_OFF
        )
        is True
    )
    assert (
        ocmd.is_visibility_policy(
            MembershipDictionaryVisibilityPolicy.ALL_ON
        )
        is False
    )


def test_is_visibility_policy_rejects_invalid_type() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    with pytest.raises(TypeError):
        ocmd.is_visibility_policy(42)  # type: ignore[arg-type]


def test_is_visibility_policy_unknown_string_returns_false() -> None:
    """An unknown string isn't rejected — it just doesn't match (parallels
    :meth:`is_intent` which is also string-equality-based)."""
    ocmd = PDOptionalContentMembershipDictionary()
    assert ocmd.is_visibility_policy("Bogus") is False


# ---------- cross-cutting: round trip add → remove → clear ----------------


def test_add_remove_clear_round_trip() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    c = PDOptionalContentGroup("C")
    ocmd.add_ocg(a)
    ocmd.add_ocg(b)
    ocmd.add_ocg(c)
    assert len(ocmd) == 3
    assert ocmd.remove_ocg(b) is True
    assert len(ocmd) == 2
    assert ocmd.contains_ocg(a) is True
    assert ocmd.contains_ocg(b) is False
    assert ocmd.contains_ocg(c) is True
    ocmd.clear_ocgs()
    assert len(ocmd) == 0
    assert ocmd.has_ocgs() is False
    # /P unchanged at the default — clear only touches /OCGs.
    assert ocmd.is_visibility_policy("AnyOn") is True


def test_remove_then_add_back_uses_array_form() -> None:
    """After a single-dict removal the /OCGs key is gone; adding the
    same OCG back must fall through the "missing /OCGs" path and create
    a fresh single-element array (not resurrect the pre-removal shape)."""
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    ocmd.set_ocgs(a)
    ocmd.remove_ocg(a)
    ocmd.add_ocg(a)
    raw = ocmd.get_cos_object().get_dictionary_object(_OCGS)
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    assert raw.get_object(0) is a.get_cos_object()


def test_pruned_dict_has_no_empty_ocgs_husk() -> None:
    """After draining /OCGs via ``remove_ocg`` the underlying COSDictionary
    must not retain an empty array — assertion serializers rely on this
    to avoid emitting empty husks in /Configs."""
    ocmd = PDOptionalContentMembershipDictionary()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    ocmd.set_ocgs([a, b])
    assert ocmd.remove_ocg(a) is True
    assert ocmd.remove_ocg(b) is True
    keys = list(ocmd.get_cos_object().key_set())
    assert COSName.get_pdf_name("OCGs") not in keys
