"""Hand-written tests for newly added predicate / typed-accessor surface in
the digital-signature cluster:

* :class:`PDSeedValueMDP` — P value class constants + ``has_p`` /
  ``is_author_signature`` / ``is_certification_signature``.
* :class:`PDSeedValueTimeStamp` — ``has_url`` and ``clear_ff``.
* :class:`PDPropBuildDataDict` — ``has_revision`` / ``has_minimum_revision``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDPropBuildDataDict,
    PDSeedValue,
    PDSeedValueMDP,
    PDSeedValueTimeStamp,
)

_FF: COSName = COSName.get_pdf_name("Ff")
_P: COSName = COSName.get_pdf_name("P")
_R: COSName = COSName.get_pdf_name("R")
_V: COSName = COSName.get_pdf_name("V")
_URL: COSName = COSName.get_pdf_name("URL")


# ---------------------------------------------------------------------------
# PDSeedValueMDP — /P value constants
# ---------------------------------------------------------------------------


def test_mdp_p_value_constants_match_pdf_spec() -> None:
    """PDF 32000-1 §12.8.2.2.2 / DocMDP transform parameters table."""
    assert PDSeedValueMDP.P_AUTHOR_SIGNATURE == 0
    assert PDSeedValueMDP.P_NO_CHANGES == 1
    assert PDSeedValueMDP.P_FORM_FILL_AND_SIGN == 2
    assert PDSeedValueMDP.P_FORM_FILL_ANNOTATE_AND_SIGN == 3


def test_mdp_p_value_constants_round_trip_through_setter() -> None:
    mdp = PDSeedValueMDP()
    mdp.set_p(PDSeedValueMDP.P_AUTHOR_SIGNATURE)
    assert mdp.get_p() == 0
    mdp.set_p(PDSeedValueMDP.P_NO_CHANGES)
    assert mdp.get_p() == 1
    mdp.set_p(PDSeedValueMDP.P_FORM_FILL_AND_SIGN)
    assert mdp.get_p() == 2
    mdp.set_p(PDSeedValueMDP.P_FORM_FILL_ANNOTATE_AND_SIGN)
    assert mdp.get_p() == 3


# ---------------------------------------------------------------------------
# PDSeedValueMDP — has_p() / is_author_signature() / is_certification_signature()
# ---------------------------------------------------------------------------


def test_mdp_has_p_false_when_absent() -> None:
    mdp = PDSeedValueMDP()
    assert mdp.has_p() is False
    # get_p still returns -1 (COSDictionary default), but has_p disambiguates.
    assert mdp.get_p() == -1


@pytest.mark.parametrize("p", [0, 1, 2, 3])
def test_mdp_has_p_true_after_set(p: int) -> None:
    mdp = PDSeedValueMDP()
    mdp.set_p(p)
    assert mdp.has_p() is True


def test_mdp_is_author_signature_only_when_p_is_zero() -> None:
    mdp = PDSeedValueMDP()
    # Absent — neither author nor certification.
    assert mdp.is_author_signature() is False
    assert mdp.is_certification_signature() is False

    mdp.set_p(0)
    assert mdp.is_author_signature() is True
    assert mdp.is_certification_signature() is False


@pytest.mark.parametrize("p", [1, 2, 3])
def test_mdp_is_certification_signature_for_p_one_through_three(p: int) -> None:
    mdp = PDSeedValueMDP()
    mdp.set_p(p)
    assert mdp.is_certification_signature() is True
    assert mdp.is_author_signature() is False


def test_mdp_predicates_false_when_p_absent_even_if_get_p_returns_minus_one() -> None:
    """The ``/P`` absent case returns ``-1`` from ``get_p`` but neither
    predicate should fire (no rules apply per spec)."""
    mdp = PDSeedValueMDP()
    assert mdp.get_p() == -1
    assert mdp.is_author_signature() is False
    assert mdp.is_certification_signature() is False


# ---------------------------------------------------------------------------
# PDSeedValueTimeStamp — has_url / clear_ff
# ---------------------------------------------------------------------------


def test_time_stamp_has_url_default_false() -> None:
    ts = PDSeedValueTimeStamp()
    assert ts.has_url() is False


def test_time_stamp_has_url_true_after_set_then_false_after_clear() -> None:
    ts = PDSeedValueTimeStamp()
    ts.set_url("https://tsa.example.org/sign")
    assert ts.has_url() is True
    ts.set_url(None)
    assert ts.has_url() is False


def test_time_stamp_has_url_true_for_empty_string() -> None:
    """``has_url`` reports presence, not non-emptiness; an empty-string
    value still counts as present."""
    ts = PDSeedValueTimeStamp()
    ts.set_url("")
    assert ts.has_url() is True
    # get_url still returns the (empty) string.
    assert ts.get_url() == ""


def test_time_stamp_clear_ff_removes_entry() -> None:
    ts = PDSeedValueTimeStamp()
    ts.set_url_required(True)
    assert _FF in ts.get_cos_object()
    ts.clear_ff()
    assert _FF not in ts.get_cos_object()
    assert ts.is_url_required() is False
    assert ts.is_timestamp_required() is False


def test_time_stamp_clear_ff_distinct_from_set_url_required_false() -> None:
    """``set_url_required(False)`` writes 0; ``clear_ff`` removes the key."""
    ts1 = PDSeedValueTimeStamp()
    ts1.set_url_required(True)
    ts1.set_url_required(False)
    assert _FF in ts1.get_cos_object()
    assert ts1.get_cos_object().get_int(_FF) == 0

    ts2 = PDSeedValueTimeStamp()
    ts2.set_url_required(True)
    ts2.clear_ff()
    assert _FF not in ts2.get_cos_object()


def test_time_stamp_clear_ff_safe_when_already_absent() -> None:
    """No-op when /Ff is already absent — must not raise."""
    ts = PDSeedValueTimeStamp()
    assert _FF not in ts.get_cos_object()
    ts.clear_ff()
    assert _FF not in ts.get_cos_object()


# ---------------------------------------------------------------------------
# PDPropBuildDataDict — has_revision / has_minimum_revision
# ---------------------------------------------------------------------------


def test_data_dict_has_revision_default_false() -> None:
    d = PDPropBuildDataDict()
    assert d.has_revision() is False
    # get_revision returns -1 by default; has_revision disambiguates.
    assert d.get_revision() == -1


def test_data_dict_has_revision_true_after_set() -> None:
    d = PDPropBuildDataDict()
    d.set_revision(7)
    assert d.has_revision() is True


def test_data_dict_has_revision_true_even_for_minus_one() -> None:
    """A stored value of ``-1`` is indistinguishable from "absent" via the
    typed accessor; ``has_revision`` is the disambiguation hook."""
    d = PDPropBuildDataDict()
    d.set_revision(-1)
    assert d.get_revision() == -1
    assert d.has_revision() is True


def test_data_dict_has_minimum_revision_default_false() -> None:
    d = PDPropBuildDataDict()
    assert d.has_minimum_revision() is False
    assert d.get_minimum_revision() == -1


def test_data_dict_has_minimum_revision_true_after_set() -> None:
    d = PDPropBuildDataDict()
    d.set_minimum_revision(5)
    assert d.has_minimum_revision() is True


def test_data_dict_has_minimum_revision_disambiguates_minus_one() -> None:
    d = PDPropBuildDataDict()
    d.set_minimum_revision(-1)
    assert d.get_minimum_revision() == -1
    assert d.has_minimum_revision() is True


# ---------------------------------------------------------------------------
# Integration: predicates wired through PDSeedValue
# ---------------------------------------------------------------------------


def test_seed_value_get_mdp_predicates_propagate() -> None:
    sv = PDSeedValue()
    mdp = PDSeedValueMDP()
    mdp.set_p(2)
    sv.set_mdp(mdp)

    got = sv.get_mdp()
    assert got is not None
    assert got.has_p() is True
    assert got.is_certification_signature() is True
    assert got.is_author_signature() is False


def test_seed_value_mdp_loaded_from_existing_dict_predicates() -> None:
    """A pre-existing /MDP dict (e.g. parsed from a PDF) should expose the
    same predicates as one constructed via the wrapper."""
    cos = COSDictionary()
    cos.set_int("P", 0)
    mdp = PDSeedValueMDP(cos)
    assert mdp.has_p() is True
    assert mdp.is_author_signature() is True
    assert mdp.is_certification_signature() is False
