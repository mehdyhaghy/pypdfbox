from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSeedValueMDP,
)

_P: COSName = COSName.get_pdf_name("P")


# ---------- defaults ----------


def test_default_constructor_creates_empty_direct_dict() -> None:
    mdp = PDSeedValueMDP()
    cos = mdp.get_cos_object()
    assert isinstance(cos, COSDictionary)
    # Default constructor sets direct on the dictionary; no /P entry yet.
    assert _P not in cos
    # get_int default mirrors COSDictionary -> -1 when absent.
    assert mdp.get_p() == -1


def test_constructor_accepts_existing_dict() -> None:
    cos = COSDictionary()
    cos.set_int("P", 2)
    mdp = PDSeedValueMDP(cos)
    assert mdp.get_cos_object() is cos
    assert mdp.get_p() == 2


# ---------- /P round-trip ----------


@pytest.mark.parametrize("p", [0, 1, 2, 3])
def test_set_p_accepts_valid_values(p: int) -> None:
    mdp = PDSeedValueMDP()
    mdp.set_p(p)
    assert mdp.get_p() == p


@pytest.mark.parametrize("bad", [-1, 4, 5, 100])
def test_set_p_rejects_out_of_range(bad: int) -> None:
    mdp = PDSeedValueMDP()
    with pytest.raises(ValueError):
        mdp.set_p(bad)


# ---------- integration with PDSeedValue ----------


def test_pd_seed_value_get_mdp_returns_typed_wrapper() -> None:
    sv = PDSeedValue()
    assert sv.get_mdp() is None  # absent by default

    mdp = PDSeedValueMDP()
    mdp.set_p(1)
    sv.set_mdp(mdp)

    got = sv.get_mdp()
    assert isinstance(got, PDSeedValueMDP)
    assert got.get_p() == 1
    # Underlying COSDictionary identity preserved.
    assert got.get_cos_object() is mdp.get_cos_object()


def test_pd_seed_value_set_mdp_none_clears() -> None:
    sv = PDSeedValue()
    mdp = PDSeedValueMDP()
    mdp.set_p(2)
    sv.set_mdp(mdp)
    assert sv.get_mdp() is not None
    sv.set_mdp(None)
    assert sv.get_mdp() is None


def test_pd_seed_value_set_mdp_accepts_raw_dict() -> None:
    sv = PDSeedValue()
    cos = COSDictionary()
    cos.set_int("P", 3)
    sv.set_mdp(cos)
    got = sv.get_mdp()
    assert got is not None
    assert got.get_p() == 3
    assert got.get_cos_object() is cos


def test_set_mpd_typo_alias_works() -> None:
    """PDFBox upstream ships ``setMPD`` (a typo). We provide ``set_mpd``
    as a parity alias of :meth:`set_mdp`."""
    sv = PDSeedValue()
    mdp = PDSeedValueMDP()
    mdp.set_p(0)
    sv.set_mpd(mdp)
    got = sv.get_mdp()
    assert got is not None and got.get_p() == 0


# ---------- /P permission-level predicates ----------


def test_is_no_changes_only_true_for_p_one() -> None:
    mdp = PDSeedValueMDP()
    assert mdp.is_no_changes() is False  # absent
    mdp.set_p(0)
    assert mdp.is_no_changes() is False
    mdp.set_p(1)
    assert mdp.is_no_changes() is True
    mdp.set_p(2)
    assert mdp.is_no_changes() is False
    mdp.set_p(3)
    assert mdp.is_no_changes() is False


def test_is_form_fill_and_sign_only_true_for_p_two() -> None:
    mdp = PDSeedValueMDP()
    assert mdp.is_form_fill_and_sign() is False
    mdp.set_p(1)
    assert mdp.is_form_fill_and_sign() is False
    mdp.set_p(2)
    assert mdp.is_form_fill_and_sign() is True
    mdp.set_p(3)
    assert mdp.is_form_fill_and_sign() is False


def test_is_form_fill_annotate_and_sign_only_true_for_p_three() -> None:
    mdp = PDSeedValueMDP()
    assert mdp.is_form_fill_annotate_and_sign() is False
    mdp.set_p(2)
    assert mdp.is_form_fill_annotate_and_sign() is False
    mdp.set_p(3)
    assert mdp.is_form_fill_annotate_and_sign() is True


def test_permission_predicates_partition_certification_levels() -> None:
    """``is_certification_signature`` covers exactly /P in {1,2,3}; each of
    the three level predicates is mutually exclusive within that range.
    """
    mdp = PDSeedValueMDP()
    for p, expected in (
        (1, ("is_no_changes",)),
        (2, ("is_form_fill_and_sign",)),
        (3, ("is_form_fill_annotate_and_sign",)),
    ):
        mdp.set_p(p)
        assert mdp.is_certification_signature() is True
        for name in (
            "is_no_changes",
            "is_form_fill_and_sign",
            "is_form_fill_annotate_and_sign",
        ):
            actual = getattr(mdp, name)()
            assert actual is (name in expected), (
                f"/P={p}: {name} expected {name in expected}, got {actual}"
            )


# ---------- __str__ / __repr__ ----------


def test_str_empty_dict_is_marked_empty() -> None:
    mdp = PDSeedValueMDP()
    assert str(mdp) == "PDSeedValueMDP(<empty>)"
    assert repr(mdp) == str(mdp)


def test_str_labels_each_spec_p_value() -> None:
    """Every spec /P value must produce a human-readable label so debug
    output never collapses to a bare integer for spec-conformant dicts.
    """
    mdp = PDSeedValueMDP()
    mdp.set_p(0)
    assert "author" in str(mdp)
    mdp.set_p(1)
    assert "no_changes" in str(mdp)
    mdp.set_p(2)
    assert "form_fill_and_sign" in str(mdp)
    mdp.set_p(3)
    assert "form_fill_annotate_and_sign" in str(mdp)


def test_str_unknown_p_value_falls_back_to_int() -> None:
    """Out-of-spec /P values (e.g. read from a malformed PDF) must surface
    as the raw integer rather than crash or be hidden — useful for
    diagnostic logs.
    """
    cos = COSDictionary()
    cos.set_int("P", 99)  # not a spec value
    mdp = PDSeedValueMDP(cos)
    s = str(mdp)
    assert "p=99" in s
    assert "(99)" in s
