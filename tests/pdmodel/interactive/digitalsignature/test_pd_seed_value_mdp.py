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
