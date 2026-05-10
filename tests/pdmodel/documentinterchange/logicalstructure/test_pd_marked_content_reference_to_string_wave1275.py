"""Wave 1275 round-out: ``PDMarkedContentReference.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)


def test_to_string_default_is_sentinel_mcid() -> None:
    mcr = PDMarkedContentReference()
    # ``/MCID`` absent → :meth:`get_mcid` returns the ``-1`` sentinel.
    # Mirrors upstream ``PDMarkedContentReference.toString()``
    # (PDMarkedContentReference.java line 110): ``mcid=<n>``.
    assert mcr.to_string() == "mcid=-1"


def test_to_string_after_set_mcid() -> None:
    mcr = PDMarkedContentReference()
    mcr.set_mcid(42)
    assert mcr.to_string() == "mcid=42"


def test_to_string_matches_str() -> None:
    mcr = PDMarkedContentReference()
    mcr.set_mcid(7)
    assert mcr.to_string() == str(mcr)
